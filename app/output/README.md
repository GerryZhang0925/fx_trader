# Output

Display proposals. Console, JSON/Markdown, Telegram, local HTML. No orders.

Unset Telegram token/chat_id → skip. `--serve` binds `127.0.0.1` only.

## Config

`config.yaml`: webhook, telegram chat_id, web host/port. Token: `TELEGRAM_BOT_TOKEN`. Webhook secret: `FX_TRADER_WEBHOOK_SECRET`.

## Tests / backtest

Fixture proposals → Markdown/HTML. No live network in tests.

## Do not

Compute signals or size. No broker.
