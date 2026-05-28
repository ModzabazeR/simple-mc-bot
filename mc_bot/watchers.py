from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable

from .config import config
from .tmux import session_exists

log = logging.getLogger(__name__)

Notifier = Callable[[str], Awaitable[None]]

DONE_RE = re.compile(r'Done \([\d.]+s\)! For help, type "help"')
STOP_RE = re.compile(r"Stopping server")


async def watch_log(notify: Notifier) -> None:
    """Tail latest.log and notify on boot complete / shutdown begin."""
    last_inode: int | None = None
    last_size = 0
    while True:
        try:
            if config.log_path.exists():
                st = config.log_path.stat()
                if last_inode != st.st_ino:
                    # First attach or log rotation: skip backlog so we don't replay old events.
                    last_inode = st.st_ino
                    last_size = st.st_size
                elif st.st_size < last_size:
                    last_size = 0
                elif st.st_size > last_size:
                    with config.log_path.open("rb") as f:
                        f.seek(last_size)
                        chunk = f.read().decode("utf-8", errors="replace")
                    last_size = st.st_size
                    for line in chunk.splitlines():
                        if DONE_RE.search(line):
                            await notify(":green_circle: Server is **online**")
                        elif STOP_RE.search(line):
                            await notify(":yellow_circle: Server is **stopping**…")
        except Exception as e:
            log.warning("log watch error: %s", e)
        await asyncio.sleep(2)


async def watch_session(notify: Notifier) -> None:
    """Notify when the tmux session disappears (server fully exited)."""
    was_running = session_exists()
    while True:
        running = session_exists()
        if was_running and not running:
            await notify(":red_circle: Server is **offline**")
        was_running = running
        await asyncio.sleep(5)
