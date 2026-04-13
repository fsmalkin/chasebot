param(
  [switch]$CheckBot,
  [switch]$LatestChatId,
  [string]$SendChatId,
  [string]$Text = "UAT ping from chasecar Telegram wait bridge"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$EnvFilePath = Join-Path $RepoRoot ".env"

function Get-EnvVar([string]$Name) {
  $value = [Environment]::GetEnvironmentVariable($Name)
  if (-not [string]::IsNullOrWhiteSpace($value)) {
    return $value.Trim()
  }
  if (-not (Test-Path $EnvFilePath)) {
    return ""
  }
  $line = Get-Content $EnvFilePath | Where-Object { $_ -match "^$Name=" } | Select-Object -First 1
  if ([string]::IsNullOrWhiteSpace($line)) {
    return ""
  }
  return ($line.Substring($Name.Length + 1)).Trim()
}

function Invoke-TelegramApi([string]$Token, [string]$Method, [hashtable]$Payload) {
  $url = "https://api.telegram.org/bot$Token/$Method"
  $body = ($Payload | ConvertTo-Json -Depth 8)
  try {
    $result = Invoke-RestMethod -Method Post -Uri $url -ContentType "application/json" -Body $body
  }
  catch {
    $details = $_.ErrorDetails.Message
    if (-not [string]::IsNullOrWhiteSpace($details)) {
      try {
        $errorBody = $details | ConvertFrom-Json
        if ($errorBody.description) {
          throw "Telegram API $Method failed: $($errorBody.description)"
        }
      }
      catch {
        throw "Telegram API $Method failed: $details"
      }
    }
    throw
  }
  if (-not $result.ok) {
    throw "Telegram API $Method failed: $($result.description)"
  }
  return $result.result
}

if (-not ($CheckBot -or $LatestChatId -or $SendChatId)) {
  throw "Specify at least one action: -CheckBot, -LatestChatId, or -SendChatId <id>."
}

$token = Get-EnvVar "TELEGRAM_BOT_TOKEN"
if ([string]::IsNullOrWhiteSpace($token)) {
  throw "TELEGRAM_BOT_TOKEN not set in environment or .env."
}

if ($CheckBot) {
  $me = Invoke-TelegramApi -Token $token -Method "getMe" -Payload @{}
  Write-Output "Bot OK: @$($me.username) (id=$($me.id))"
}

if ($LatestChatId) {
  $updates = Invoke-TelegramApi -Token $token -Method "getUpdates" -Payload @{ limit = 20; timeout = 0 }
  $chatId = $null
  foreach ($update in ($updates | Sort-Object update_id -Descending)) {
    $message = $update.message
    if ($null -eq $message) { $message = $update.edited_message }
    if ($null -eq $message -or $null -eq $message.chat) { continue }
    $chatId = [string]$message.chat.id
    break
  }
  if ([string]::IsNullOrWhiteSpace($chatId)) {
    Write-Output "No chat id found. Send /start to your bot, then run again."
    exit 1
  }
  Write-Output "Latest chat_id: $chatId"
}

if (-not [string]::IsNullOrWhiteSpace($SendChatId)) {
  Invoke-TelegramApi -Token $token -Method "sendMessage" -Payload @{ chat_id = $SendChatId; text = $Text } | Out-Null
  Write-Output "Sent message to chat_id $SendChatId"
}
