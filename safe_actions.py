"""Fixed, non-shell computer actions confined to the workspace."""
from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import shutil


ALLOWED_ACTIONS = frozenset({"list_workspace", "create_daily_note", "disk_usage"})


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


def execute_action(action: str, path: str | Path) -> str:
    if action not in ALLOWED_ACTIONS:
        raise ValueError(f"Unsupported computer action: {action}")
    return {
        "list_workspace": list_workspace,
        "create_daily_note": create_daily_note,
        "disk_usage": disk_usage,
    }[action](path)
