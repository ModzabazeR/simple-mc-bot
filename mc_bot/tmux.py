from __future__ import annotations

import logging
import subprocess

from .config import config

log = logging.getLogger(__name__)


def _tmux(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(["tmux", *args], capture_output=True, text=True, check=check)
    log.info(
        "tmux %s -> rc=%d stdout=%r stderr=%r",
        " ".join(args), result.returncode, result.stdout.strip(), result.stderr.strip(),
    )
    return result


def session_exists() -> bool:
    return subprocess.run(
        ["tmux", "has-session", "-t", config.tmux_session],
        capture_output=True,
    ).returncode == 0


def start_session() -> None:
    _tmux(
        "new-session", "-d",
        "-s", config.tmux_session,
        "-n", "server",
        "-c", str(config.server_dir),
        config.start_command,
    )
    if config.proxy_type:
        _tmux(
            "new-window",
            "-t", config.tmux_session,
            "-n", config.proxy_type,
            config.proxy_command,
        )


def send_console(line: str) -> None:
    _tmux("send-keys", "-t", f"{config.tmux_session}:server", line, "Enter")


def close_aux_windows() -> None:
    """Close every window in the session except `server`.

    Uses `kill-window -a` rather than targeting the proxy window by name because
    some proxies (e.g. playit) rewrite the terminal title at runtime, which
    tmux's automatic-rename picks up, so the window may no longer have its
    original name.
    """
    _tmux("kill-window", "-a", "-t", f"{config.tmux_session}:server", check=False)


def kill_session() -> None:
    _tmux("kill-session", "-t", config.tmux_session, check=False)
