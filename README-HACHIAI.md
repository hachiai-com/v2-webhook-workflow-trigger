# Doculytix → HachiAI V2 integration guide

When Doculytix V1 finishes processing a document (OCR / intelligence), it POSTs a webhook to HachiAI. The desktop app re-runs your saved automation or starts a free-form Runway task.

---

## Flow

```
User / pipeline          Doculytix V1              HachiAI agent backend        HachiAI desktop
      │                        │                              │                         │
      │  Upload document       │                              │                         │
      ├───────────────────────►│                              │                         │
      │                        │  OCR / extract               │                         │
      │                        │                              │                         │
      │                        │  POST document.processed     │                         │
      │                        ├─────────────────────────────►│ validate secret         │
      │                        │  + X-Trigger-Secret          │ push relay              │
      │                        │                              ├────────────────────────►│ Runway
```

---

## Step 1 — Configure HachiAI (once per user)

### Option A — Saved automation (recommended for invoices)

1. **My Automations** → open workflow (include **IDMS Agent** if needed).
2. **Triggers** → **External webhook** → source **Doculytix V1** → **Create**.
3. Copy:
   - **Webhook URL** — e.g. `https://dev-agent-backend.hachiai.com/api/webhooks/sources/doculytix/{trigger_id}`
   - **Secret** — shown once

The automation prompt should reference the trigger document URL, e.g.:

> Process the invoice from the external trigger document URL. Extract vendor, line items, tax, and total.

### Option B — Global inbox (any prompt per document)

1. **Settings → General → External webhook inbox**
2. Copy inbox URL + secret
3. Doculytix must send **prompt + document_url** (see inbox payload below)

---

## Step 2 — Configure Doculytix callback

In Doculytix admin / pipeline settings (or this repo's `.env` for the simulator):

| Setting | Value |
|---------|--------|
| Callback URL | HachiAI webhook URL from Step 1 |
| Method | `POST` |
| Content-Type | `application/json` |
| Header | `X-Trigger-Secret: <your-secret>` |

**Use `dev-agent-backend.hachiai.com` — not Nexus.**

---

## Step 3 — Payload Doculytix sends

File: [`payloads/document-processed.json`](./payloads/document-processed.json)

```json
{
  "event": "document.processed",
  "document_url": "https://docx.hachiai.com/storage/invoices/sample-invoice-2026.pdf",
  "trace_id": "doculytix-001",
  "metadata": {
    "tenant_id": "bank-a",
    "document_type": "invoice",
    "page_count": 3
  }
}
```

HachiAI normalizes this to:

- `_source`: `doculytix`
- `_event_type`: `document.processed`
- `_document_url`: PDF URL for IDMS / document agents

### Inbox mode (requires explicit prompt)

```json
{
  "prompt": "Process this invoice: extract vendor, line items, tax, and total.",
  "event": "document.processed",
  "document_url": "https://docx.hachiai.com/storage/invoices/sample-invoice-2026.pdf",
  "trace_id": "inbox-001"
}
```

POST to: `https://dev-agent-backend.hachiai.com/api/webhooks/inbox`

---

## Custom prompts (any instruction per document)

You have **three options**:

### Option 1 — Custom prompt on your Doculytix webhook (saved automation + override)

Keep `USE_HACHI_INBOX=0` and your existing `HACHI_WEBHOOK_URL`. Add a `prompt` field to the Doculytix payload:

```json
{
  "event": "document.processed",
  "document_url": "https://docx.hachiai.com/storage/invoices/sample-invoice.pdf",
  "trace_id": "doculytix-001",
  "prompt": "Compare this invoice to our vendor list and flag unknown vendors."
}
```

CLI:

```bash
./scripts/trigger-hachiai.sh --prompt "Summarize this invoice in three bullet points"
```

HachiAI uses **`prompt`** instead of the saved automation’s default question (document URL still attached).

### Option 2 — Global inbox (fully free-form, no saved automation)

In `.env`:

```env
USE_HACHI_INBOX=1
HACHI_INBOX_URL=https://dev-agent-backend.hachiai.com/api/webhooks/inbox
HACHI_TRIGGER_SECRET=your-inbox-secret
```

```bash
./scripts/trigger-hachiai.sh --inbox --prompt "Extract line items and total tax from this invoice"
```

Secret comes from **Settings → General → External webhook inbox** (may differ from the Doculytix trigger secret).

### Option 3 — Simulator with custom prompt

```bash
curl -X POST http://localhost:8080/simulate/document-processed \
  -H "Content-Type: application/json" \
  -d '{
    "document_url": "https://docx.hachiai.com/storage/invoices/sample-invoice.pdf",
    "prompt": "Your custom instruction here"
  }'
```

### Prompt-only (no document)

```bash
# Inbox — text only
curl -X POST "$HACHI_INBOX_URL" \
  -H "Content-Type: application/json" \
  -H "X-Trigger-Secret: $HACHI_TRIGGER_SECRET" \
  -d '{"data": "Draft a compliance checklist for Q3 audits"}'
```

---

## Step 4 — Run this example

```bash
cp .env.example .env
# Set HACHI_WEBHOOK_URL and HACHI_TRIGGER_SECRET

docker compose up --build
```

Simulate Doculytix completion:

```bash
curl -X POST http://localhost:8080/simulate/document-processed \
  -H "Content-Type: application/json" \
  -d @payloads/document-processed.json
```

Or without Docker:

```bash
./scripts/trigger-hachiai.sh
# or: python scripts/trigger_hachiai.py
```

**Expected HachiAI response:**

```json
{
  "execution_id": "...",
  "status": "dispatched",
  "ws_delivered": 1
}
```

---

## Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `HACHI_WEBHOOK_URL` | Yes* | Per-automation Doculytix URL (`.../sources/doculytix/{id}`) |
| `HACHI_INBOX_URL` | Yes* | Global inbox URL (use with `USE_HACHI_INBOX=1`) |
| `HACHI_TRIGGER_SECRET` | Yes | `X-Trigger-Secret` value from HachiAI |
| `DEFAULT_DOCUMENT_URL` | No | Default PDF when simulating |
| `USE_HACHI_INBOX` | No | Set to `1` to use inbox + prompt payload |
| `HACHI_INBOX_PROMPT` | No | Prompt for inbox mode |

\* One of `HACHI_WEBHOOK_URL` or `HACHI_INBOX_URL` (with inbox mode).

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Cannot POST /api/webhooks/...` | Wrong host — use **dev-agent-backend**, not Nexus |
| `401 Invalid trigger secret` | Re-copy secret; header name `X-Trigger-Secret` |
| Event ignored | Trigger created for Doculytix — event must be `document.processed` |
| Nothing in Runway | Desktop app open, logged in, same user as webhook owner |
| `ws_delivered: 0` | Wait ~3s; app polls missed executions in dev |

---

## Production wiring

Replace the simulator with your real Doculytix V1 webhook emitter: on `document.processed`, POST the same JSON shape to the HachiAI URL configured in Step 2. No HachiAI code changes required on the Doculytix side beyond standard HTTP POST + secret header.
