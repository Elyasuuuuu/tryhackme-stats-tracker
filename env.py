from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv, set_key

BASE_DIR = Path(__file__).parent
ENV_PATH = BASE_DIR / ".env"
ENV_EXAMPLE_PATH = BASE_DIR / ".env.example"
STORAGE_STATE = BASE_DIR / "storage_state.json"


def load_env() -> None:
    """Load .env into os.environ (without overriding existing vars)."""
    if ENV_PATH.exists():
        load_dotenv(ENV_PATH, override=False)


def _env_str(key: str, default: str = "") -> str:
    load_env()
    return os.environ.get(key, default).strip()


def _env_int(key: str, default: int) -> int:
    raw = _env_str(key)
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    username: str
    country: str
    catchup_weekly_max_days: int
    catchup_board_max_days: int
    connect_sid: str | None
    discord_webhook_url: str | None


def load_settings() -> Settings:
    username = _env_str("THM_USERNAME")
    if not username:
        raise SystemExit(
            f"THM_USERNAME is missing.\n"
            f"Copy {ENV_EXAMPLE_PATH.name} to .env and set your TryHackMe username."
        )
    return Settings(
        username=username,
        country=_env_str("THM_COUNTRY"),
        catchup_weekly_max_days=_env_int("CATCHUP_WEEKLY_MAX_DAYS", 2),
        catchup_board_max_days=_env_int("CATCHUP_BOARD_MAX_DAYS", 6),
        connect_sid=_env_str("THM_CONNECT_SID") or None,
        discord_webhook_url=_env_str("DISCORD_WEBHOOK_URL") or None,
    )


def get_connect_sid() -> str | None:
    return load_settings().connect_sid


def get_discord_webhook_url() -> str | None:
    return load_settings().discord_webhook_url


def get_catchup_weekly_max_days() -> int:
    return load_settings().catchup_weekly_max_days


def get_catchup_board_max_days() -> int:
    return load_settings().catchup_board_max_days


def save_connect_sid(value: str) -> None:
    if not value.strip():
        raise ValueError("THM_CONNECT_SID is empty")
    if not ENV_PATH.exists():
        ENV_PATH.write_text(
            "# Copy from .env.example and fill in the values.\n",
            encoding="utf-8",
        )
    set_key(str(ENV_PATH), "THM_CONNECT_SID", value.strip())
    os.environ["THM_CONNECT_SID"] = value.strip()


def sync_connect_sid_from_storage_state() -> bool:
    """Extract connect.sid from storage_state.json into .env."""
    if not STORAGE_STATE.exists():
        return False
    state = json.loads(STORAGE_STATE.read_text())
    for cookie in state.get("cookies", []):
        if cookie.get("name") != "connect.sid":
            continue
        domain = cookie.get("domain", "")
        if "tryhackme.com" not in domain:
            continue
        save_connect_sid(cookie["value"])
        return True
    return False
