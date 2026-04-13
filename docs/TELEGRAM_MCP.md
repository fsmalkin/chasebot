# Telegram MCP

This repo includes a repo-local Telegram wait bridge for Codex MCP.

The runtime has two parts:

1. `telegram-daemon`: long-lived Docker service that sends prompts and long-polls Telegram for direct replies.
2. `telegram-mcp-stdio`: on-demand stdio MCP server that exposes `telegram_send`, `telegram_wait`, and `telegram_cancel`.

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

## Start The Daemon

```powershell
powershell -ExecutionPolicy Bypass -File scripts/run_telegram_wait_daemon.ps1 -Action up -Build
```

Other daemon actions:

- `-Action status`
- `-Action logs`
- `-Action down`

## Register The MCP Server

This repo registers a repo-specific MCP name so it does not clobber a global `telegram-wait` install from another checkout.

```powershell
powershell -ExecutionPolicy Bypass -File scripts/register_telegram_mcp.ps1
```

Default MCP server name: `chasecar-telegram-wait`

## Behavioral Contract

- `telegram_send` creates exactly one active wait per chat.
- The human reply must be a direct Telegram reply to the prompt message.
- `/status` in Telegram reports whether a prompt is still pending.
- Unauthorized chat ids are ignored.
