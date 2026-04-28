from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

APP_NAME = "AI Construction Drawing"
APP_FOLDER_NAME = "AI-Construction-Drawing"
DEFAULT_MODEL = "gemini-1.5-flash"
FALLBACK_MODELS = ["gemini-1.5-flash", "gemini-1.5-pro"]


def documents_dir() -> Path:
    user_profile = Path.home()
    return user_profile / "Documents"


def default_workspace_dir() -> Path:
    configured = os.environ.get("SKETCH_ASSISTANT_HOME")
    if configured:
        return Path(configured).expanduser().resolve()
    return documents_dir() / APP_FOLDER_NAME


def user_config_dir() -> Path:
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / APP_FOLDER_NAME
    return Path.home() / f".{APP_FOLDER_NAME}"


def settings_path() -> Path:
    return user_config_dir() / "settings.json"


def default_settings() -> dict[str, Any]:
    return {
        "workspace_dir": str(default_workspace_dir()),
        "gemini_api_key": "",
        "gemini_model": DEFAULT_MODEL,
    }


def read_settings() -> dict[str, Any]:
    settings = default_settings()
    path = settings_path()
    if path.exists():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                settings.update(loaded)
        except json.JSONDecodeError:
            pass
    return settings


def write_settings(settings: dict[str, Any]) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    safe_settings = default_settings()
    safe_settings.update(settings)
    path.write_text(json.dumps(safe_settings, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_workspace(settings: dict[str, Any] | None = None) -> Path:
    current_settings = settings or read_settings()
    workspace = Path(current_settings.get("workspace_dir") or default_workspace_dir()).expanduser().resolve()
    for child in ("Projects", "Templates", "Exports", "Backups"):
        (workspace / child).mkdir(parents=True, exist_ok=True)
    return workspace
