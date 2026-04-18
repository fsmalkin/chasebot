# Telegram MCP

This repo includes a repo-local Telegram wait bridge for Codex MCP.

The runtime has two parts:

1. `telegram-daemon`: long-lived Docker service that sends prompts and long-polls Telegram for direct replies.
2. `telegram-mcp-stdio`: long-lived helper container that hosts on-demand stdio MCP sessions via `docker compose exec`.

## Required Env Vars

Add these to the repo-root `.env`:

- `TELEGRAM_BOT_TOKEN`
- `TELEGRAM_CHAT_ID`
- `ALLOWED_CHAT_IDS`

`TELEGRAM_CHAT_ID` is the default target chat. `ALLOWED_CHAT_IDS` is a comma-separated allowlist for inbound replies.

Optional wait-bridge tuning:

- `WAIT_DEFAULT_TIMEOUT_SEC`
- `WAIT_MAX_TIMEOUT_SEC`
- `WAIT_DAEMON_IDLE_POLL_TIMEOUT_SEC`
- `WAIT_STATUS_POLL_INTERVAL_SEC`
- `WAIT_SEND_POLL_INTERVAL_SEC`
- `WAIT_SEND_MAX_DELAY_SEC`

## Preflight

Check the bot credentials:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/telegram_preflight.ps1 -CheckBot
```

Find the latest chat id seen by the bot:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/telegram_preflight.ps1 -LatestChatId
```

Send a manual ping:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/telegram_preflight.ps1 -SendChatId <chat_id> -Text "UAT ping"
```

## Start The Bridge Services

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_telegram_wait_daemon.ps1 -Action up -Build
```

By default the wrapper uses compose project `chasecar_telegram`, so the runtime
shows up as `chasecar_telegram-*` containers instead of inheriting a more
generic repo-local compose prefix.

The wrapper starts both `telegram-daemon` and the reusable `telegram-mcp-stdio`
helper container. It also prunes legacy `telegram-mcp-stdio-run-*` leftovers
from the older `docker compose run` launch path before the services come up.

Other daemon actions:

- `-Action status`
- `-Action logs`
- `-Action down`
- `-Action cleanup`

## Register The MCP Server

This repo registers a repo-specific MCP name so it does not clobber a global `telegram-wait` install from another checkout.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/register_telegram_mcp.ps1
```

Default MCP server name: `chasecar-telegram-wait`

Registration now points Codex at a repo-local PowerShell wrapper that reuses
the `telegram-mcp-stdio` helper container with `docker compose exec` instead of
creating a fresh `telegram-mcp-stdio-run-*` container per MCP session.

## Behavioral Contract

- `telegram_send` creates exactly one active wait per chat.
- The human reply must be a direct Telegram reply to the prompt message.
- `/status` in Telegram reports whether a prompt is still pending.
- Unauthorized chat ids are ignored.
