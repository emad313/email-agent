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


def test_create_project_writes_files_inside_workspace(tmp_path: Path):
    result = execute_action(
        "create_project",
        tmp_path,
        project_name="hello-project",
        project_files={"README.md": "# Hello\n", "notes.txt": "Notes\n"},
    )
    assert result == "hello-project (2 files)"
    assert (tmp_path / "hello-project" / "README.md").read_text() == "# Hello\n"


def test_create_project_rejects_unsafe_file(tmp_path: Path):
    with pytest.raises(ValueError, match="safe"):
        execute_action(
            "create_project",
            tmp_path,
            project_name="project",
            project_files={"../secret.txt": "bad"},
        )
