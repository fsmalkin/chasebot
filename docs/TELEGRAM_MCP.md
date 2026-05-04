# Telegram MCP

The canonical Telegram MCP bridge is global, not repo-local:

```powershell
powershell -ExecutionPolicy Bypass -File D:\services\codex-telegram\scripts\serve-mcp.ps1
```

Codex and Claude should use the MCP server named `telegram`, registered by:

```powershell
powershell -ExecutionPolicy Bypass -File D:\services\codex-telegram\scripts\install-global.ps1
```

Verify the global bridge with:

```powershell
powershell -ExecutionPolicy Bypass -File D:\services\codex-telegram\scripts\verify-global.ps1
```

## Tools

- `telegram_notify`: fire-and-forget status update.
- `telegram_send`: send a prompt and create a wait.
- `telegram_wait`: wait for a reply.
- `telegram_status`: inspect active/recent waits.
- `telegram_cancel`: cancel a wait.

Multiple waits may be active in the same chat. Replies must be direct replies to
the prompt message so the global daemon can match the correct wait.

## Repo-Local Fallback

The Chasecar `scripts/telegram_preflight.ps1`,
`scripts/run_telegram_wait_daemon.ps1`, `scripts/register_telegram_mcp.ps1`, and
`telegram_wait_bridge/` files are retained only as recovery/reference material.
Do not register the repo-local MCP bridge during routine work.

If an existing Codex or Claude session reports `Transport closed`, restart that
session after `verify-global.ps1` passes. Live sessions can cache a dead stdio
transport and may not hot-reload MCP configuration changes.
