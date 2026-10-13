from pathlib import Path

import pytest

from safe_actions import create_daily_note, execute_action, list_workspace


def test_workspace_actions_are_confined(tmp_path: Path):
    assert create_daily_note(tmp_path).endswith(".md")
    assert "md" in list_workspace(tmp_path)


def test_unsupported_action_rejected(tmp_path):
    with pytest.raises(ValueError, match="Unsupported"):
        execute_action("run_shell", tmp_path)


def test_path_escape_rejected(tmp_path):
    from safe_actions import _safe_child
    with pytest.raises(ValueError):
        _safe_child(tmp_path.resolve(), "../outside.txt")
