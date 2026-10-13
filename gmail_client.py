"""Gmail OAuth and API operations."""
from __future__ import annotations

from dataclasses import dataclass
from email import policy
from email.parser import BytesParser
from email.utils import parseaddr
import base64
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build


SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]


@dataclass(frozen=True)
class EmailMessage:
    message_id: str
    thread_id: str
    sender: str
    subject: str
    body: str
    received_at: str = ""


def normalize_sender(value: str) -> str:
    return parseaddr(value)[1].strip().casefold()


def authenticate(
    credentials_path: str | Path = "credentials.json",
    token_path: str | Path = "token.json",
) -> Credentials:
    credentials: Credentials | None = None
    token = Path(token_path)
    if token.is_file():
        credentials = Credentials.from_authorized_user_file(str(token), SCOPES)
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        else:
            if not Path(credentials_path).is_file():
                raise FileNotFoundError("credentials.json is required for Gmail OAuth")
            flow = InstalledAppFlow.from_client_secrets_file(str(credentials_path), SCOPES)
            credentials = flow.run_local_server(port=0)
        token.write_text(credentials.to_json(), encoding="utf-8")
    return credentials


class GmailClient:
    def __init__(self, service: Any):
        self.service = service

    @classmethod
    def from_oauth(
        cls,
        credentials_path: str | Path = "credentials.json",
        token_path: str | Path = "token.json",
    ) -> "GmailClient":
        credentials = authenticate(credentials_path, token_path)
        return cls(build("gmail", "v1", credentials=credentials))

    def list_messages(self, query: str, limit: int) -> list[EmailMessage]:
        result = self.service.users().messages().list(
            userId="me", q=query, maxResults=limit
        ).execute()
        return [self.get_message(item["id"]) for item in result.get("messages", [])]

    def get_message(self, message_id: str) -> EmailMessage:
        raw = self.service.users().messages().get(
            userId="me", id=message_id, format="raw"
        ).execute()
        data = base64.urlsafe_b64decode(raw["raw"] + "===")
        parsed = BytesParser(policy=policy.default).parsebytes(data)
        body = ""
        if parsed.is_multipart():
            for part in parsed.walk():
                if part.get_content_type() == "text/plain" and not part.get_filename():
                    body = part.get_content()
                    break
        else:
            body = parsed.get_content()
        return EmailMessage(
            message_id=message_id,
            thread_id=str(raw.get("threadId", "")),
            sender=normalize_sender(parsed.get("From", "")),
            subject=str(parsed.get("Subject", "")),
            body=body,
            received_at=str(raw.get("internalDate", "")),
        )

    def send_reply(self, message: EmailMessage, body: str) -> str:
        from email.message import EmailMessage as MimeMessage
        outgoing = MimeMessage()
        outgoing["To"] = message.sender
        subject = message.subject
        if not subject.lower().startswith("re:"):
            subject = f"Re: {subject}"
        outgoing["Subject"] = subject
        outgoing["In-Reply-To"] = message.message_id
        outgoing["References"] = message.message_id
        outgoing.set_content(body)
        encoded = base64.urlsafe_b64encode(outgoing.as_bytes()).decode()
        result = self.service.users().messages().send(
            userId="me", body={"raw": encoded, "threadId": message.thread_id}
        ).execute()
        return str(result["id"])

    def find_sent_reply(self, message: EmailMessage) -> str | None:
        query = f'in:sent subject:"{message.subject}"'
        result = self.service.users().messages().list(
            userId="me", q=query, maxResults=20
        ).execute()
        return next((str(item["id"]) for item in result.get("messages", [])), None)
