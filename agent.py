"""Email task orchestration and model-output validation."""
from __future__ import annotations

from dataclasses import dataclass
import json
import logging
from pathlib import Path
import re
from typing import Any

from config import Config
from gmail_client import EmailMessage, GmailClient
from ollama_client import OllamaClient
from prompts import CLASSIFICATION_SYSTEM, classification_prompt
from research import conduct_research
from safe_actions import execute_action
from storage import Storage


SUPPORTED_ACTIONS = frozenset(
    {"reply", "research", "create_file", "computer", "create_project"}
)
SUPPORTED_FORMATS = frozenset({"md", "txt", "csv", "json"})
SUPPORTED_COMPUTER_ACTIONS = frozenset(
    {"list_workspace", "create_daily_note", "disk_usage"}
)
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,100}$")
TASK_FIELDS = (
    "reply",
    "research_query",
    "file_name",
    "file_format",
    "file_content",
    "computer_action",
    "project_name",
    "project_files",
    "summary",
)


@dataclass(frozen=True)
class Task:
    action: str
    reply: str
    research_query: str
    file_name: str
    file_format: str
    file_content: str
    computer_action: str
    project_name: str
    project_files: str
    summary: str


class TaskValidationError(ValueError):
    """Raised when the model returns a task outside the supported contract."""


def validate_task(raw: dict[str, Any]) -> Task:
    values = {key: raw.get(key, "") for key in TASK_FIELDS}
    action = raw.get("action")
    if action not in SUPPORTED_ACTIONS:
        raise TaskValidationError(f"Unknown task action: {action!r}")
    if action == "create_project" and isinstance(values["project_files"], dict):
        values["project_files"] = json.dumps(values["project_files"])
    if not all(isinstance(value, str) for value in values.values()):
        raise TaskValidationError("Task fields must be strings")
    if action == "create_file":
        if values["file_format"] not in SUPPORTED_FORMATS:
            raise TaskValidationError("Unsupported file format")
        if (
            not SAFE_NAME.fullmatch(values["file_name"])
            or Path(values["file_name"]).name != values["file_name"]
        ):
            raise TaskValidationError("Unsafe file name")
    if action == "computer" and values["computer_action"] not in SUPPORTED_COMPUTER_ACTIONS:
        raise TaskValidationError("Unsupported computer action")
    if action == "create_project":
        if not SAFE_NAME.fullmatch(values["project_name"]):
            raise TaskValidationError("Unsafe project name")
        try:
            project_files = json.loads(values["project_files"])
        except json.JSONDecodeError as exc:
            raise TaskValidationError("project_files must be valid JSON") from exc
        if not isinstance(project_files, dict) or not project_files:
            raise TaskValidationError("project_files must be a non-empty JSON object")
    return Task(action, **values)


class EmailAgent:
    def __init__(self, config: Config, gmail: GmailClient, ollama: OllamaClient,
                 storage: Storage, logger: logging.Logger | None = None):
        self.config = config
        self.gmail = gmail
        self.ollama = ollama
        self.storage = storage
        self.logger = logger or logging.getLogger(__name__)

    def _write_file(self, task: Task) -> str:
        root = self.config.agent.workspace_path.expanduser().resolve()
        root.mkdir(parents=True, exist_ok=True)
        target = (root / f"{task.file_name}.{task.file_format}").resolve()
        if root not in target.parents or target.exists():
            raise ValueError("File path is invalid or already exists")
        data = task.file_content.encode("utf-8")
        if len(data) > self.config.agent.max_file_bytes:
            raise ValueError("Generated file exceeds configured size limit")
        if task.file_format == "json":
            json.loads(task.file_content)
        elif task.file_format == "csv":
            if "\n" not in task.file_content and "," not in task.file_content:
                raise ValueError("CSV content is not valid")
        target.write_bytes(data)
        return target.name

    def _classify(self, message: EmailMessage) -> Task:
        raw = self.ollama.generate_json(
            classification_prompt(message.sender, message.subject,
                                   message.body[:self.config.agent.max_body_chars]),
            CLASSIFICATION_SYSTEM,
        )
        return validate_task(raw)

    def _save_draft(self, message_id: str, body: str) -> None:
        self.config.agent.drafts_path.mkdir(parents=True, exist_ok=True)
        draft = self.config.agent.drafts_path / f"{message_id}.txt"
        draft.write_text(body, encoding="utf-8")

    def process_message(self, message: EmailMessage) -> str:
        if message.sender not in self.config.allowed_senders:
            self.storage.record_message(
                message.message_id,
                message.sender,
                message.subject,
                "ignored",
                detail="sender not allowlisted",
                received_at=message.received_at,
            )
            return "ignored"
        if not self.storage.record_message(
            message.message_id, message.sender, message.subject, "processing",
            received_at=message.received_at,
        ):
            return "duplicate"
        try:
            task = self._classify(message)
            result = task.reply
            if task.action == "research":
                result = conduct_research(task.research_query, self.config.research, self.ollama)
            elif task.action == "create_file":
                result = f"Created {self._write_file(task)} in the workspace."
            elif task.action == "computer":
                result = execute_action(
                    task.computer_action,
                    self.config.agent.workspace_path,
                    max_file_bytes=self.config.agent.max_file_bytes,
                )
            elif task.action == "create_project":
                project_files = json.loads(task.project_files)
                result = (
                    "Created project "
                    + execute_action(
                        "create_project",
                        self.config.agent.workspace_path,
                        project_name=task.project_name,
                        project_files=project_files,
                        max_file_bytes=self.config.agent.max_file_bytes,
                    )
                    + " in the workspace."
                )
            if self.config.agent.auto_reply:
                try:
                    reply_id = self.gmail.send_reply(message, result)
                except Exception as send_error:
                    # A transport timeout can happen after Gmail accepted the message.
                    # Reconcile with Sent mail before allowing a future retry.
                    reply_id = self.gmail.find_sent_reply(message)
                    if reply_id:
                        self.storage.update_message(
                            message.message_id, "replied", "send confirmed during reconciliation",
                            reply_id,
                        )
                        return "replied"
                    self.storage.update_message(message.message_id, "send_uncertain", str(send_error))
                    self.storage.log_action(
                        message.message_id, task.action, "send_uncertain", str(send_error)
                    )
                    self.logger.error("Reply send status is uncertain for %s", message.message_id)
                    return "send_uncertain"
                self.storage.update_message(message.message_id, "replied", task.summary, reply_id)
                self.logger.info("Reply sent successfully for %s", message.message_id)
            else:
                self._save_draft(message.message_id, result)
                self.storage.update_message(message.message_id, "drafted", task.summary)
            self.storage.log_action(message.message_id, task.action, "success", task.summary)
            return task.action
        except TaskValidationError as exc:
            clarification = (
                "I could not safely classify this request. "
                "Please clarify the task. Supported file formats are md, txt, csv, "
                f"and json. Details: {exc}"
            )
            if self.config.agent.auto_reply:
                reply_id = self.gmail.send_reply(message, clarification)
                self.storage.update_message(
                    message.message_id, "replied", "sent classification clarification", reply_id
                )
            else:
                self._save_draft(message.message_id, clarification)
                self.storage.update_message(
                    message.message_id, "drafted", "saved classification clarification"
                )
            self.storage.log_action(
                message.message_id, "clarification", "success", str(exc)
            )
            self.logger.warning("Saved clarification for invalid model task: %s", exc)
            return "clarification"
        except Exception as exc:
            self.storage.update_message(message.message_id, "error", str(exc))
            self.storage.log_action(
                message.message_id, "error", "failed", str(exc)
            )
            self.logger.exception("Message processing failed for %s", message.message_id)
            return "error"

    def run_cycle(self) -> int:
        messages = self.gmail.list_messages(
            self.config.agent.gmail_query, self.config.agent.max_messages_per_cycle
        )
        for message in messages:
            self.process_message(message)
        return len(messages)
