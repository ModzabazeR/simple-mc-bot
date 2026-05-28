# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A small Discord bot for a friend-group's modded Minecraft server. Slash commands `/start` `/stop` `/status` drive a tmux session that runs the server (`./start.sh`) alongside an optional public tunnel (e.g. `playit.gg`). Notifications about lifecycle transitions (online / stopping / offline) post to a configured channel.

## Commands

```sh
# install/refresh deps
uv sync

# run the bot
uv run python -m mc_bot

# attach to the running game server (interactive console)
tmux attach -t mc-cisco       # Ctrl-b d to detach
```

There are no tests, lints, or build steps — this is a single ~150-line bot.

## Configuration

All config is environment variables loaded from `.env` at import time (`mc_bot/config.py`). `.env.example` is the source of truth for available keys. Misconfiguration crashes at import with a `SystemExit` — you cannot start the bot with a malformed `.env`.

Key consequence: importing `mc_bot.config` (transitively, importing anything in the package) requires a valid `.env` to be present. Tests/REPLs need `DISCORD_TOKEN` and `MC_SERVER_DIR` set, even if they're dummies.

## Architecture

Five tiny modules in `mc_bot/`, each with one job:

- **`config.py`** — frozen `Config` dataclass populated from `.env`. Module-level `config` singleton instantiated at import.
- **`tmux.py`** — thin `subprocess.run(["tmux", ...])` wrappers. `start_session` always creates a `server` window running `MC_START_COMMAND`. If `MC_PROXY_TYPE` is set, an extra window named after the proxy type (e.g. `playit`) runs `MC_PROXY_COMMAND`. With `MC_PROXY_TYPE` empty, the server runs without any tunnel window.
- **`minecraft.py`** — async Server List Ping via `mcstatus`, returns `None` on any failure.
- **`watchers.py`** — two long-running async tasks: `watch_log` tails `latest.log` for "Done" / "Stopping server" lines, `watch_session` polls `tmux has-session` to detect full session death.
- **`bot.py`** — discord.py client, slash commands, on_ready, force-kill safety net, task lifecycle.

### Concurrency model — non-obvious bits

`bot.py` has three pieces of shared state guarded by an `asyncio.Lock` (`_action_lock`):

1. **`_session_gen`** — integer that increments inside the lock on each successful `/start`. The force-kill watcher captures `gen` at schedule time and **bails if it's been bumped**. This prevents the scenario `/stop → /start (within MC_STOP_TIMEOUT) → force-kill clobbers the freshly restarted session`. Any code that distinguishes "this server lifetime" vs "a later one" must use this generation, not just `session_exists()`.
2. **`_background_tasks`** — strong-reference set for tasks created via `_track()`. `asyncio.create_task` returns a weak reference; without this set, fire-and-forget tasks (force-kill, watchers) can be GC'd mid-run. Always use `_track(coro)` instead of `asyncio.create_task(coro)` for non-awaited tasks.
3. **`_synced`** — slash command tree is synced exactly once on first `on_ready`. `on_ready` re-fires on reconnect; resyncing each time is rate-limit-prone and pointless.

### tmux as the lifecycle backbone

Every state question goes through tmux:
- "Is the server up?" → `tmux has-session -t mc-cisco`
- "Stop the server" → `tmux send-keys -t mc-cisco:server 'stop' Enter` (writes to Minecraft's stdin, **not** a shell)
- "Force-kill stuck shutdown" → `tmux kill-session -t mc-cisco`
- "Tear down the proxy tunnel" → `tmux kill-window -a -t mc-cisco:server` during `/stop` (kills every window except `server`)

The tmux session auto-destroys when its last window closes, so once `start.sh` exits and the proxy window (if any) is killed, the session disappears — which `watch_session` then announces.

`MC_START_COMMAND` and `MC_PROXY_COMMAND` go through `sh -c` (tmux invokes a shell). Operator-controlled today; **never wire user input into them**.

### Permissions

`MC_ALLOWED_USER_IDS` empty → anyone in the guild can `/start` and `/stop`. Non-empty → only those user IDs. `/status` is always open.

### Known shutdown gotcha (not a bug to fix in code)

The Forge 1.19.2 `NightConfigFixes` mod throws NPE stack traces during shutdown. Harmless — world data is saved before they fire. The real shutdown-hang risk used to be `WAIT_FOR_USER_INPUT=true` in the server's `variables.txt`, which left bash waiting on a keypress. The force-kill safety net (`MC_STOP_TIMEOUT`) covers any future variant of this.
