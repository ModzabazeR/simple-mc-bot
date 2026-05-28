from __future__ import annotations

import asyncio
import logging
import subprocess

import discord
from discord import app_commands

from .config import config
from .minecraft import ping
from .tmux import close_aux_windows, kill_session, send_console, session_exists, start_session
from .watchers import watch_log, watch_session

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("mc-bot")

intents = discord.Intents.default()
client = discord.Client(intents=intents)
tree = app_commands.CommandTree(client)

_action_lock = asyncio.Lock()
_session_gen = 0
_synced = False
_watchers_started = False
_background_tasks: set[asyncio.Task] = set()


def _track(coro) -> asyncio.Task:
    """Create a task and pin a strong reference so it isn't GC'd mid-flight."""
    task = asyncio.create_task(coro)
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task


def _is_allowed(user_id: int) -> bool:
    return not config.allowed_user_ids or user_id in config.allowed_user_ids


async def _notify(content: str) -> None:
    if not config.notify_channel_id:
        return
    channel = client.get_channel(config.notify_channel_id)
    if channel is None:
        return
    try:
        await channel.send(content)
    except Exception as e:
        log.warning("notify failed: %s", e)


async def _force_kill_after(timeout: int, gen: int) -> None:
    """Wait up to `timeout` seconds for the tmux session to die; kill it if it lingers.

    Bails out if a new /start has bumped the generation — we must not kill a freshly
    restarted session that happens to share the tmux name.
    """
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        await asyncio.sleep(2)
        if gen != _session_gen:
            return
        if not session_exists():
            return
    if gen != _session_gen or not session_exists():
        return
    await asyncio.to_thread(kill_session)
    await _notify(f":warning: Server didn't exit after {timeout}s — force-killed tmux session.")


@tree.command(name="start", description="Start the Minecraft server")
async def start_cmd(interaction: discord.Interaction) -> None:
    global _session_gen
    if not _is_allowed(interaction.user.id):
        await interaction.response.send_message("Not allowed.", ephemeral=True)
        return
    await interaction.response.defer()
    async with _action_lock:
        if session_exists():
            await interaction.followup.send("Server is already running.", ephemeral=True)
            return
        try:
            await asyncio.to_thread(start_session)
        except subprocess.CalledProcessError as e:
            await interaction.followup.send(
                f"Failed to start: ```{e.stderr or e}```", ephemeral=True
            )
            return
        _session_gen += 1
    await interaction.followup.send("Starting server… I'll post when it's ready.")


@tree.command(name="stop", description="Stop the Minecraft server gracefully")
async def stop_cmd(interaction: discord.Interaction) -> None:
    if not _is_allowed(interaction.user.id):
        await interaction.response.send_message("Not allowed.", ephemeral=True)
        return
    await interaction.response.defer()
    async with _action_lock:
        if not session_exists():
            await interaction.followup.send("Server is not running.", ephemeral=True)
            return
        try:
            await asyncio.to_thread(send_console, "stop")
        except subprocess.CalledProcessError as e:
            await interaction.followup.send(
                f"Failed to send stop: ```{e.stderr or e}```", ephemeral=True
            )
            return
        await asyncio.to_thread(close_aux_windows)
        gen = _session_gen
        timeout = config.stop_timeout
    if timeout > 0:
        _track(_force_kill_after(timeout, gen))
        await interaction.followup.send(
            f"Sent `stop`. Server will shut down shortly "
            f"(force-kill after {timeout}s if it lingers)."
        )
    else:
        await interaction.followup.send("Sent `stop`. Server will shut down shortly.")


@tree.command(name="status", description="Show Minecraft server status")
async def status_cmd(interaction: discord.Interaction) -> None:
    await interaction.response.defer()
    if not session_exists():
        await interaction.followup.send(":red_circle: Server is **offline**")
        return
    status = await ping()
    if status is None:
        await interaction.followup.send(
            ":yellow_circle: Server process is up but not responding yet (still booting?)"
        )
        return
    sample = ", ".join(p.name for p in (status.players.sample or []))
    extra = f" — {sample}" if sample else ""
    await interaction.followup.send(
        f":green_circle: **online** — {status.players.online}/{status.players.max} players{extra}"
        f" — {status.latency:.0f}ms"
    )


@client.event
async def on_ready() -> None:
    global _synced, _watchers_started
    log.info("logged in as %s", client.user)
    if not _synced:
        _synced = True
        if config.guild_id:
            guild = discord.Object(id=config.guild_id)
            tree.copy_global_to(guild=guild)
            await tree.sync(guild=guild)
        else:
            await tree.sync()
    if not _watchers_started:
        _watchers_started = True
        _track(watch_log(_notify))
        _track(watch_session(_notify))


def main() -> None:
    client.run(config.token)
