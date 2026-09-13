# Output

Display proposals. Console, JSON/Markdown, Telegram, local HTML. No orders.

`--serve` binds `127.0.0.1:18080` only. The page shows core ON/OFF (POST `/api/cores`), module run status, and proposals. CLIs append one line to `reports/status.jsonl`. Core toggles are config, not orders.

Unset Telegram token/chat_id → skip.

## Config

`config.yaml`: webhook, telegram chat_id, web host/port. Token: `TELEGRAM_BOT_TOKEN`. Webhook secret: `FX_TRADER_WEBHOOK_SECRET`.

## Tests / backtest

Fixture proposals → Markdown/HTML. No live network in tests.

## Do not

Halt *messages* (Telegram) are output. Halt *state* is the venue account in `account`. No broker.
