# Browser Selector Profile Guide

## Goal

Browser selector profiles let the self-built Local Agent adapt to different web customer-service pages without changing core code.

The same runtime can support:

- local mock page
- Pinduoduo web customer-service page
- future Taobao / JD / other web pages

## Current Command

Use the built-in mock profile:

```powershell
D:\anaconda3\python.exe -m app.local_agent.run_browser_mock --backend-url http://127.0.0.1:8000 --browser-channel msedge
```

By default this command is safe: it reads the page, calls the backend, and records `skipped_dry_run`; it does not fill the input or click send.

Only use real sending when you intentionally pass `--allow-real-send`:

```powershell
D:\anaconda3\python.exe -m app.local_agent.run_browser_mock `
  --backend-url http://127.0.0.1:8000 `
  --browser-channel msedge `
  --allow-real-send
```

Use an external selector profile:

```powershell
D:\anaconda3\python.exe -m app.local_agent.run_browser_mock `
  --backend-url http://127.0.0.1:8000 `
  --browser-channel msedge `
  --selector-profile-json app\local_agent\browser_profiles\pinduoduo_web.local.json `
  --page-url "https://example-platform-chat-page"
```

## Profile Fields

Required selectors:

- `root`: main chat app container.
- `buyer_messages`: all buyer message nodes that should be read.
- `reply_input`: text input or textarea used to type the AI reply.
- `send_button`: button used to send the reply.
- `sent_messages`: seller/agent sent message nodes used to verify successful sending.

Optional attributes:

- `message_id_attr`: stable message id attribute. Default: `data-message-id`.
- `conversation_id_attr`: stable conversation id attribute. Default: `data-conversation-id`.
- `customer_id_attr`: buyer id attribute.
- `customer_name_attr`: buyer display name attribute.
- `product_fields`: map structured product fields to page selectors.

## Pinduoduo Workflow

1. Copy the template:

```powershell
Copy-Item app\local_agent\browser_profiles\pinduoduo_web.template.json app\local_agent\browser_profiles\pinduoduo_web.local.json
```

2. Use selector discovery on the Pinduoduo web customer-service page:

```powershell
D:\anaconda3\python.exe -m app.local_agent.run_browser_discovery `
  --page-url "https://mms.pinduoduo.com/chat-merchant/index.html?r=0.5541775007481573#/" `
  --browser-channel msedge `
  --headed `
  --user-data-dir data\browser_profiles\pdd_edge `
  --wait-before-scan 60 `
  --output-json data\browser_profiles\pdd_selector_candidates.json
```

During the 60 seconds:

- log in if needed
- open the customer-service page
- select one active conversation
- keep the buyer message and reply input visible

3. Inspect `data\browser_profiles\pdd_selector_candidates.json`.

4. Fill `pinduoduo_web.local.json`:

- buyer message selector
- reply input selector
- send button selector
- sent message selector
- product title / SKU / price / stock selectors if visible

5. Run the Local Agent in headed mode first:

```powershell
D:\anaconda3\python.exe -m app.local_agent.run_browser_mock `
  --backend-url http://127.0.0.1:8000 `
  --browser-channel msedge `
  --headed `
  --user-data-dir data\browser_profiles\pdd_edge `
  --wait-before-run 20 `
  --selector-profile-json app\local_agent\browser_profiles\pinduoduo_web.local.json `
  --page-url "https://mms.pinduoduo.com/chat-merchant/index.html?r=0.5541775007481573#/"
```

6. Check the result:

- `processed_count` should be `1` or greater.
- The default result should be `send_status=skipped_dry_run`.
- risky return/refund/complaint questions should return `handoff`.
- The runner processes only the latest visible buyer message by default.

7. Only after the dry-run result is correct, run a tightly scoped real-send verification:

```powershell
D:\anaconda3\python.exe -m app.local_agent.run_browser_mock `
  --backend-url http://127.0.0.1:8000 `
  --browser-channel msedge `
  --headed `
  --user-data-dir data\browser_profiles\pdd_edge `
  --wait-before-run 20 `
  --selector-profile-json app\local_agent\browser_profiles\pinduoduo_web.local.json `
  --page-url "https://mms.pinduoduo.com/chat-merchant/index.html?r=0.5541775007481573#/" `
  --allow-real-send
```

Do not use `--process-all-visible` on a real platform unless you are intentionally debugging historical message ingestion.

## Notes

- Prefer stable attributes when possible.
- Avoid brittle full XPath selectors unless there is no alternative.
- If a page folds line breaks, the executor normalizes whitespace before verifying sent text.
- If Playwright Chromium download is slow, use `--browser-channel msedge`.
- Default command-line behavior is dry-run plus latest-only. Real sending is opt-in.
