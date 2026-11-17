"""本地状态存储：Cookie、设备码、账号切换。

状态文件位于 %USERPROFILE%\\.coolapk-cli\\state.json，
只保存在本机，不上传任何第三方。
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

STATE_DIR = Path(os.environ.get("COOLAPK_CLI_HOME", Path.home() / ".coolapk-cli"))
STATE_FILE = STATE_DIR / "state.json"


def load() -> dict[str, Any]:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
    return {}


def save(state: dict[str, Any]) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _chmod_private(path: Path) -> None:
    """POSIX 下把凭据文件权限收紧到 0600。"""
    try:
        os.chmod(path, 0o600)
    except (OSError, NotImplementedError):
        pass


def get_cookie() -> str:
    return str(load().get("cookie", ""))


def set_cookie(cookie: str) -> None:
    state = load()
    state["cookie"] = cookie
    save(state)
    _chmod_private(STATE_FILE)


def get_device_code() -> str | None:
    code = load().get("deviceCode")
    return str(code) if code else None


def set_device_code(code: str) -> None:
    state = load()
    state["deviceCode"] = code
    save(state)


def clear() -> None:
    if STATE_FILE.exists():
        STATE_FILE.unlink()
