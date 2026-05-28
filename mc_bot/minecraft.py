from __future__ import annotations

import asyncio

from mcstatus import JavaServer

from .config import config


async def ping():
    """Server List Ping. Returns status object on success, None on any failure."""
    try:
        server = JavaServer.lookup(f"{config.minecraft_host}:{config.minecraft_port}")
        return await asyncio.to_thread(server.status)
    except Exception:
        return None
