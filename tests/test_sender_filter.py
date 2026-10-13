from pathlib import Path

from agent import EmailAgent
from config import load_config
from gmail_client import EmailMessage
from storage import Storage


class DummyGmail:
    pass


class DummyOllama:
    pass


def make_agent(tmp_path: Path) -> EmailAgent:
    config_path = tmp_path / "config.yaml"
    config_path.write_text("allowed_senders:\n - trusted@example.com\n", encoding="utf-8")
    config = load_config(config_path)
    return EmailAgent(config, DummyGmail(), DummyOllama(), Storage(tmp_path / "db.sqlite"))


def test_exact_allowlist_and_non_allowlisted_sender(tmp_path):
    agent = make_agent(tmp_path)
    approved = EmailMessage("1", "t", "trusted@example.com", "Hi", "hello")
    rejected = EmailMessage("2", "t", "trusted@example.com.evil", "Hi", "hello")
    assert agent.process_message(approved) == "error"
    assert agent.process_message(approved) == "error"
    assert agent.process_message(rejected) == "ignored"
