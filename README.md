# simple-mc-bot

A small Discord bot that starts, stops, and checks on a Minecraft server through slash commands. Built for a friend-group server, easy to host on the same box as the game.

## What you get

Three slash commands in Discord:

- `/start` boots the Minecraft server in a tmux session.
- `/stop` sends a graceful `stop` to the server console, then force-kills it after a timeout if it hangs.
- `/status` shows whether the server is online, who is on it, and current latency.

The bot also posts a message in a chosen channel when the server finishes booting, when it begins shutting down, and when it has fully stopped.

You can optionally run a public tunnel (like [playit.gg](https://playit.gg)) alongside the server so friends outside your LAN can connect, with no port-forwarding needed.

## Requirements

- A Linux box with `tmux` installed.
- Python 3.11 or newer.
- [uv](https://github.com/astral-sh/uv) for dependency management.
- A Discord bot application with a token. See [Discord's docs](https://discord.com/developers/docs/quick-start/getting-started) if you have never made one.
- The Minecraft server itself, already set up with a `start.sh` (or any other launcher) that runs the game in the foreground.

## Setup

1. Clone this repo onto the box that runs your Minecraft server:

   ```sh
   git clone https://github.com/ModzabazeR/simple-mc-bot.git
   cd simple-mc-bot
   ```

2. Install dependencies:

   ```sh
   uv sync
   ```

3. Copy the example config and fill in your values:

   ```sh
   cp .env.example .env
   ```

   Open `.env` and set at least:

   - `DISCORD_TOKEN`, your bot's token.
   - `MC_SERVER_DIR`, the absolute path to the folder containing your server's `start.sh`.

   Everything else has sensible defaults. The full list is documented in `.env.example`.

4. Invite the bot to your Discord server. It needs permission to read messages, send messages, and use application (slash) commands in the channel where you want to use it.

5. (Optional) Lock the commands down to specific people by setting `MC_ALLOWED_USER_IDS` to a comma-separated list of Discord user IDs. Leave it empty and anyone in the server can start and stop the game.

6. (Optional) Set `DISCORD_NOTIFY_CHANNEL_ID` to a channel ID so lifecycle messages (online, stopping, offline) post somewhere visible.

## Optional public tunnel

If you want friends to connect from outside your network without opening a port on your router, configure a tunnel:

```env
MC_PROXY_TYPE=playit
MC_PROXY_COMMAND=playit
```

`MC_PROXY_TYPE` tells the bot which kind of tunnel you are running. Today only `playit` is supported. `MC_PROXY_COMMAND` is the shell command that launches it.

Leave both empty and the bot just runs the server with no tunnel, perfect for LAN-only setups.

## Running the bot

```sh
uv run python -m mc_bot
```

The bot logs in, registers its slash commands, and waits. Use the slash commands in any channel where you invited it.

To peek at what the Minecraft server is actually doing, attach to the tmux session:

```sh
tmux attach -t minecraft-server       # press Ctrl-b then d to detach
```

(`minecraft-server` is the default session name. If you changed `MC_TMUX_SESSION` in your `.env`, use that.)

## Keeping it running

Run the bot under a process supervisor of your choice (systemd, a tmux session, screen, etc.) so it survives reboots and logouts. A minimal `systemd` user unit works well.

## Troubleshooting

**Bot says "Server is not running" right after I ran `/start`.** Give it a few seconds. `/start` returns as soon as tmux has launched the server process, but the game itself takes a while to finish booting. Use `/status` to check in.

**`/stop` hangs forever.** It should not, because `MC_STOP_TIMEOUT` triggers a force-kill (default: 60 seconds). If it does, raise an issue or set `MC_STOP_TIMEOUT` lower in your `.env`.

**The bot crashes immediately on launch.** Your `.env` is misconfigured. The error message says which variable is wrong. Fix it and try again.

**`/status` says "process is up but not responding".** The server is still booting, or it crashed without tearing down its tmux window. Attach to the tmux session and look at the console to confirm.

## License

No license attached. This is hobby software for a group of friends. Use it however you like, no warranty.
