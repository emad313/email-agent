"""Configuration loading and validation."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

import yaml


EMAIL_RE = re.compile(r"^[^@\s<>]+@[^@\s<>]+\.[^@\s<>]+$")
DEFAULT_GMAIL_QUERY = "in:inbox -from:me"


@dataclass(frozen=True)
class AgentConfig:
    auto_reply: bool
    poll_interval_seconds: int
    max_messages_per_cycle: int
    gmail_query: str
    database_path: Path
    log_path: Path
    workspace_path: Path
    drafts_path: Path
    max_body_chars: int
    max_file_bytes: int


@dataclass(frozen=True)
class OllamaConfig:
    endpoint: str
    model: str
    timeout_seconds: int
    context_length: int
    max_output_tokens: int


@dataclass(frozen=True)
class ResearchConfig:
    max_results: int


@dataclass(frozen=True)
class Config:
    allowed_senders: tuple[str, ...]
    agent: AgentConfig
    ollama: OllamaConfig
    research: ResearchConfig


def _positive_int(section: dict[str, Any], key: str, default: int) -> int:
    value = section.get(key, default)
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{key} must be a positive integer")
    return value


def _path(value: Any, key: str) -> Path:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{key} must be a non-empty path")
    return Path(value).expanduser()


def _parse_allowed_senders(value: Any) -> tuple[str, ...]:
    """Parse and normalize the exact sender addresses allowed to trigger work."""
    if isinstance(value, str):
        senders = [item.strip() for item in value.split(",") if item.strip()]
    else:
        senders = value

    if not isinstance(senders, list) or not senders:
        raise ValueError(
            "allowed_senders must be a non-empty comma-separated string or list"
        )

    normalized: list[str] = []
    for sender in senders:
        if not isinstance(sender, str) or not EMAIL_RE.fullmatch(sender.strip()):
            raise ValueError(f"Invalid allowed sender: {sender!r}")
        normalized.append(sender.strip().casefold())
    return tuple(dict.fromkeys(normalized))


def _load_sections(raw: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    agent = raw.get("agent", {})
    ollama = raw.get("ollama", {})
    research = raw.get("research", {})
    if not all(isinstance(section, dict) for section in (agent, ollama, research)):
        raise ValueError("agent, ollama, and research must be mappings")
    return agent, ollama, research


def load_config(path: str | Path = "config.yaml") -> Config:
    config_path = Path(path)
    if not config_path.is_file():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    with config_path.open("r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}
    if not isinstance(raw, dict):
        raise ValueError("Configuration root must be a mapping")

    allowed_senders = _parse_allowed_senders(raw.get("allowed_senders", []))
    agent_raw, ollama_raw, research_raw = _load_sections(raw)

    agent = AgentConfig(
        auto_reply=agent_raw.get("auto_reply", False) is True,
        poll_interval_seconds=_positive_int(agent_raw, "poll_interval_seconds", 60),
        max_messages_per_cycle=_positive_int(agent_raw, "max_messages_per_cycle", 5),
        gmail_query=str(agent_raw.get("gmail_query", DEFAULT_GMAIL_QUERY)),
        database_path=_path(agent_raw.get("database_path", "agent.db"), "database_path"),
        log_path=_path(agent_raw.get("log_path", "agent.log"), "log_path"),
        workspace_path=_path(agent_raw.get("workspace_path", "workspace"), "workspace_path"),
        drafts_path=_path(agent_raw.get("drafts_path", "drafts"), "drafts_path"),
        max_body_chars=_positive_int(agent_raw, "max_body_chars", 12000),
        max_file_bytes=_positive_int(agent_raw, "max_file_bytes", 1048576),
    )
    ollama = OllamaConfig(
        endpoint=str(ollama_raw.get("endpoint", "http://127.0.0.1:11434")).rstrip("/"),
        model=str(ollama_raw.get("model", "qwen2.5:3b")),
        timeout_seconds=_positive_int(ollama_raw, "timeout_seconds", 120),
        context_length=_positive_int(ollama_raw, "context_length", 4096),
        max_output_tokens=_positive_int(ollama_raw, "max_output_tokens", 500),
    )
    research = ResearchConfig(max_results=_positive_int(research_raw, "max_results", 5))
    return Config(allowed_senders, agent, ollama, research)
