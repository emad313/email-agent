"""Fixed, non-shell computer actions confined to the workspace."""
from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import re
import shutil


ALLOWED_ACTIONS = frozenset(
    {"list_workspace", "create_daily_note", "disk_usage", "create_project"}
)
PROJECT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,80}$")
PROJECT_FILE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._ -]{0,100}\.(md|txt|csv|json)$")


def workspace_root(path: str | Path) -> Path:
    root = Path(path).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_child(root: Path, name: str) -> Path:
    candidate = (root / name).resolve()
    if candidate.parent != root or candidate == root:
        raise ValueError("Requested path must remain directly inside the workspace")
    return candidate


def list_workspace(path: str | Path) -> str:
    root = workspace_root(path)
    return json.dumps(sorted(item.name for item in root.iterdir()), ensure_ascii=False)


def create_daily_note(path: str | Path) -> str:
    root = workspace_root(path)
    target = _safe_child(root, f"{date.today().isoformat()}.md")
    if not target.exists():
        target.write_text(f"# Daily note: {date.today().isoformat()}\n\n", encoding="utf-8")
    return target.name


def disk_usage(path: str | Path) -> str:
    usage = shutil.disk_usage(workspace_root(path))
    return json.dumps({"total": usage.total, "used": usage.used, "free": usage.free})


def create_project(
    path: str | Path,
    project_name: str,
    files: dict[str, str],
    max_file_bytes: int,
) -> str:
    """Create a new workspace project from approved text files."""
    root = workspace_root(path)
    if not PROJECT_NAME.fullmatch(project_name):
        raise ValueError("Unsafe project name")
    if not files or len(files) > 20:
        raise ValueError("A project must contain between 1 and 20 files")

    project_root = (root / project_name).resolve()
    if root not in project_root.parents or project_root.exists():
        raise ValueError("Project path is invalid or already exists")

    validated: list[tuple[Path, bytes]] = []
    for name, content in files.items():
        if (
            not isinstance(name, str)
            or not isinstance(content, str)
            or not PROJECT_FILE.fullmatch(name)
            or Path(name).name != name
        ):
            raise ValueError("Project files must be safe .md, .txt, .csv, or .json names")
        data = content.encode("utf-8")
        if len(data) > max_file_bytes:
            raise ValueError(f"Project file is too large: {name}")
        if name.endswith(".json"):
            json.loads(content)
        validated.append((project_root / name, data))

    project_root.mkdir()
    try:
        for target, data in validated:
            target.write_bytes(data)
    except Exception:
        shutil.rmtree(project_root)
        raise
    return f"{project_name} ({len(validated)} files)"


def execute_action(
    action: str,
    path: str | Path,
    *,
    project_name: str = "",
    project_files: dict[str, str] | None = None,
    max_file_bytes: int = 1048576,
) -> str:
    if action not in ALLOWED_ACTIONS:
        raise ValueError(f"Unsupported computer action: {action}")
    return {
        "list_workspace": list_workspace,
        "create_daily_note": create_daily_note,
        "disk_usage": disk_usage,
        "create_project": lambda workspace: create_project(
            workspace, project_name, project_files or {}, max_file_bytes
        ),
    }[action](path)
