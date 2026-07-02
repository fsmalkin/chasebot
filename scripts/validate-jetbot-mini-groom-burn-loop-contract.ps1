param(
    [string]$AutomationPath = "$env:USERPROFILE\.codex\automations\jetbot-mini-groom-and-burn-loop\automation.toml"
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $AutomationPath)) {
    throw "JetBot Mini groom-and-burn automation was not found at $AutomationPath"
}

$text = Get-Content -LiteralPath $AutomationPath -Raw

$requiredPhrases = @(
    'target_thread_id = "019ee82b-6b01-7a50-aafe-019f4775956e"',
    "Aleph's event-driven terminal watcher is the primary loop",
    'This heartbeat is only a low-frequency recovery path',
    'RRULE:FREQ=HOURLY;INTERVAL=1',
    'keep the bridge locked and no-motion by default',
    'HTTP 423 `motion_disabled` refusals are success evidence',
    'Do not run live motion unless the owner/operator explicitly authorizes live motion',
    'chasecar_bridge_stack_closed_loop_runner.py --pretty --steps 2',
    'without `--execute-motion`',
    'Loop-continuation contract: completed hardware slices are checkpoints, not terminal stops',
    'A completed Codex goal plus safe robot state plus unblocked locked/no-motion work requires the next groom-and-burn pass.',
    'Terminal output requires one concrete finding:',
    'Return DONT_NOTIFY only when another run is active'
)

foreach ($phrase in $requiredPhrases) {
    if (-not $text.Contains($phrase)) {
        throw "Missing JetBot Mini groom-and-burn contract phrase: $phrase"
    }
}

$legacyStopPhrases = @(
    "a blocker, or a terminal result",
    "mark the loop complete after one passing slice"
)

foreach ($phrase in $legacyStopPhrases) {
    if ($text.Contains($phrase)) {
        throw "Legacy stop language is still present: $phrase"
    }
}

Write-Output "jetbot-mini-groom-burn-loop-contract: OK"
