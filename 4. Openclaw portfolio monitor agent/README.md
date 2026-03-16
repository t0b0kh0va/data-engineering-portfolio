# 📊 Portfolio Monitor Bot

A prompt-based AI agent that delivers a daily stock briefing to Telegram.

## What it does

Every day at 16:00 (UTC+9) the agent:
1. Searches recent news for each ticker in the portfolio
2. Applies a signal flag: 🟢 BUY / 🟡 HOLD / 🔴 CAUTION / 🚨 STRONG SELL / ⚪ NO UPDATE
3. Sends a concise 2–3 line summary per ticker to Telegram

## Stack

- **Agent**: Claude (prompt-based, no custom code)
- **Tools**: web_search, telegram_send, file_write
- **Schedule**: cron `0 7 * * *` (07:00 UTC)

## Structure

| File | Purpose |
|------|---------|
| `SOUL.md` | Core instructions, flag system, output format |
| `IDENTITY.md` | Agent name, role, personality |
| `TOOLS.md` | Allowed and prohibited tool usage |
| `USER.md` | Owner profile and preferences |
| `AGENTS.md` | Agent architecture (single agent) |
| `BOOTSTRAP.md` | First-run behaviour |
| `HEARTBEAT.md` | Schedule definition |

## Example output

```
📊 Portfolio Update — 2026-03-17 16:00

🟡 TSLA — HOLD
No company-specific news. General market softness, down 1.2% with sector.

🟢 NVDA — BUY
Announced expanded partnership with major cloud provider. Strong volume on positive catalyst.
```

## Notes

- Agent never invents or extrapolates news
- No positions are modified without explicit user confirmation
- Portfolio tickers are updated via chat