from pathlib import Path

import pytest

from config import load_config


def write_config(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "config.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_config_loads_and_normalizes_sender(tmp_path):
    config = load_config(write_config(tmp_path, 'allowed_senders:\n  - "Trusted@Example.com"\n'))
    assert config.allowed_senders == ("trusted@example.com",)


def test_config_loads_comma_separated_senders(tmp_path):
    config = load_config(write_config(
        tmp_path,
        'allowed_senders: " Alice@example.com, BOB@example.com , alice@example.com "\n',
    ))
    assert config.allowed_senders == ("alice@example.com", "bob@example.com")


def test_config_rejects_invalid_sender(tmp_path):
    with pytest.raises(ValueError, match="Invalid allowed sender"):
        load_config(write_config(tmp_path, "allowed_senders:\n  - nope\n"))


def test_config_requires_allowlist(tmp_path):
    with pytest.raises(ValueError, match="non-empty"):
        load_config(write_config(tmp_path, "{}\n"))


def test_config_rejects_empty_comma_separated_allowlist(tmp_path):
    with pytest.raises(ValueError, match="non-empty"):
        load_config(write_config(tmp_path, 'allowed_senders: " , "\n'))
