from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

KNOWN_PROXY_TYPES = frozenset({"playit"})


def _int_or_none(name: str) -> int | None:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        raise SystemExit(f"{name} must be an integer, got: {raw!r}")


def _int_with_default(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return default
    try:
        return int(raw)
    except ValueError:
        raise SystemExit(f"{name} must be an integer, got: {raw!r}")


def _ids(name: str) -> frozenset[int]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return frozenset()
    try:
        return frozenset(int(x) for x in raw.split(",") if x.strip())
    except ValueError:
        raise SystemExit(f"{name} must be a comma-separated list of integers, got: {raw!r}")


@dataclass(frozen=True)
class Config:
    token: str
    guild_id: int | None
    notify_channel_id: int | None
    server_dir: Path
    tmux_session: str
    start_command: str
    proxy_type: str | None
    proxy_command: str | None
    minecraft_host: str
    minecraft_port: int
    log_path: Path
    stop_timeout: int
    allowed_user_ids: frozenset[int]


def _load() -> Config:
    token = os.environ.get("DISCORD_TOKEN", "").strip()
    if not token:
        raise SystemExit("DISCORD_TOKEN is not set. Copy .env.example → .env and fill it in.")

    server_dir_raw = os.environ.get("MC_SERVER_DIR", "").strip()
    if not server_dir_raw:
        raise SystemExit("MC_SERVER_DIR is required in .env")
    server_dir = Path(server_dir_raw).expanduser()

    proxy_type_raw = os.environ.get("MC_PROXY_TYPE", "").strip()
    proxy_command_raw = os.environ.get("MC_PROXY_COMMAND", "").strip()
    proxy_type: str | None = proxy_type_raw or None
    proxy_command: str | None = proxy_command_raw or None

    if proxy_type is not None and proxy_type not in KNOWN_PROXY_TYPES:
        known = ", ".join(sorted(KNOWN_PROXY_TYPES))
        raise SystemExit(
            f"MC_PROXY_TYPE must be one of: {known} (or unset). Got: {proxy_type!r}"
        )
    if proxy_type is not None and proxy_command is None:
        raise SystemExit(
            f"MC_PROXY_COMMAND is required when MC_PROXY_TYPE={proxy_type}"
        )
    if proxy_type is None and proxy_command is not None:
        raise SystemExit(
            "MC_PROXY_COMMAND is set but MC_PROXY_TYPE is empty — "
            "set MC_PROXY_TYPE or clear MC_PROXY_COMMAND"
        )

    return Config(
        token=token,
        guild_id=_int_or_none("DISCORD_GUILD_ID"),
        notify_channel_id=_int_or_none("DISCORD_NOTIFY_CHANNEL_ID"),
        server_dir=server_dir,
        tmux_session=os.environ.get("MC_TMUX_SESSION", "mc-cisco"),
        start_command=os.environ.get("MC_START_COMMAND", "./start.sh"),
        proxy_type=proxy_type,
        proxy_command=proxy_command,
        minecraft_host=os.environ.get("MC_HOST", "localhost"),
        minecraft_port=_int_with_default("MC_PORT", 25565),
        log_path=server_dir / os.environ.get("MC_LOG_PATH", "logs/latest.log"),
        stop_timeout=_int_with_default("MC_STOP_TIMEOUT", 60),
        allowed_user_ids=_ids("MC_ALLOWED_USER_IDS"),
    )


config: Config = _load()
