# Doculytix V1 — HachiAI V2 webhook integration

Runnable example of Doculytix V1 notifying HachiAI when document processing completes (`document.processed`). Includes a **web UI**, a small Flask API, and CLI scripts.

## Prerequisites

- [Docker](https://docs.docker.com/get-docker/) (recommended), **or** Python 3.12+
- [HachiAI desktop](https://hachiai.com) installed, open, and logged in
- A webhook URL + secret from HachiAI (see below)

## 1. Configure HachiAI

Pick **one** of these modes:

### Option A — Saved automation (Doculytix trigger)

Best for invoice workflows tied to a saved automation.

1. **My Automations** → your workflow → **Triggers** → **External webhook** → source **Doculytix V1** → **Create**
2. Copy the **Webhook URL** and **Secret** (secret is shown once)

### Option B — Global inbox (custom prompts)

Best for free-form prompts from the UI or CLI (`--inbox --prompt`).

1. **Settings → General → External webhook inbox**
2. Copy the **Inbox URL** and **Secret**

Use `dev-agent-backend.hachiai.com` — **not** Nexus.

## 2. Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your values:

**Doculytix trigger (Option A):**

```env
HACHI_WEBHOOK_URL=https://dev-agent-backend.hachiai.com/api/webhooks/sources/doculytix/YOUR_TRIGGER_ID
HACHI_TRIGGER_SECRET=your-doculytix-trigger-secret
HACHI_INBOX_URL=https://dev-agent-backend.hachiai.com/api/webhooks/inbox
```

**Inbox (Option B)** — use the inbox secret, which may differ from the Doculytix trigger secret:

```env
HACHI_INBOX_URL=https://dev-agent-backend.hachiai.com/api/webhooks/inbox
HACHI_TRIGGER_SECRET=your-inbox-secret
```

You can set both URLs in `.env`; the UI lets you pick which mode to use per request.

| Variable | Description |
|----------|-------------|
| `HACHI_WEBHOOK_URL` | Per-automation Doculytix webhook URL |
| `HACHI_INBOX_URL` | Global inbox URL (`…/api/webhooks/inbox`) |
| `HACHI_TRIGGER_SECRET` | `X-Trigger-Secret` header value from HachiAI |
| `DEFAULT_DOCUMENT_URL` | Default PDF URL in payloads (optional) |
| `PORT` | Local port (default `8080`) |

## 3. Run the project

### With Docker (recommended)

```bash
docker compose up --build
```

### Without Docker

```bash
cd hachiai-callback
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

The server loads `.env` from the repo root automatically.

Open **[http://localhost:8080](http://localhost:8080)** in your browser.

## 4. Use the web UI

Keep **HachiAI desktop open and logged in** before sending.

### Inbox — custom prompt

Same as `./scripts/trigger-hachiai.sh --inbox --prompt "…"`.

1. Select **Inbox — custom prompt**
2. Enter your prompt (e.g. `Make a list of pros and cons of using youtube`)
3. Leave **Document URL** empty for a text-only task, or add a PDF URL to attach a document
4. Click **Send to HachiAI**

### Doculytix — document.processed

Simulates Doculytix finishing OCR on a document.

1. Select **Doculytix — document.processed**
2. Set the document URL (or use the default)
3. Optionally override the automation prompt
4. Click **Send to HachiAI**

A successful response looks like:

```json
{ "status": "dispatched", "ws_delivered": 1 }
```

Runway should start within a few seconds.

## 5. CLI alternatives

Without the web UI or simulator server:

```bash
# Doculytix document.processed (saved automation)
./scripts/trigger-hachiai.sh

# Custom prompt via inbox
./scripts/trigger-hachiai.sh --inbox --prompt "Make a list of pros and cons of using youtube"

# Custom prompt on saved automation
./scripts/trigger-hachiai.sh --prompt "Summarize this invoice in 3 bullets"
```

Direct API calls:

```bash
# Health check
curl http://localhost:8080/health

# Inbox custom prompt (prompt-only)
curl -X POST http://localhost:8080/simulate/inbox \
  -H "Content-Type: application/json" \
  -d '{"use_inbox": true, "prompt": "Make a list of pros and cons of using youtube"}'

# Doculytix document.processed
curl -X POST http://localhost:8080/simulate/document-processed \
  -H "Content-Type: application/json" \
  -d @payloads/document-processed.json
```

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/` | Web UI |
| `GET` | `/health` | Service status and configured target |
| `GET` | `/api/config` | Defaults from `.env` |
| `POST` | `/simulate/inbox` | Inbox custom prompt (`use_inbox: true` in body) |
| `POST` | `/simulate/document-processed` | Doculytix `document.processed` payload |
| `POST` | `/webhook/hachiai` | Alias for `document-processed` |

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `Set HACHI_WEBHOOK_URL or HACHI_INBOX_URL` | Create `.env` from `.env.example` and restart the server |
| `401 Invalid trigger secret` | Re-copy the secret for the **correct** mode (inbox secret ≠ Doculytix trigger secret) |
| `Cannot POST /api/webhooks/...` | Use **dev-agent-backend**, not Nexus |
| Nothing in Runway | Desktop app must be open, logged in, same user as webhook owner |
| `ws_delivered: 0` | Wait ~3s; the app polls missed executions in dev |

See **[README-HACHIAI.md](./README-HACHIAI.md)** for payload formats, all prompt options, and full integration details.

## Project layout

| Path | Purpose |
|------|---------|
| `hachiai-callback/` | Flask app — web UI + API simulator |
| `payloads/` | Example JSON payloads |
| `scripts/` | CLI helpers (`trigger-hachiai.sh`, `trigger_hachiai.py`) |
| `.env.example` | Environment variable template |

## Related docs

- [README-HACHIAI.md](./README-HACHIAI.md) — integration guide and payload reference
- HachiAI webhook triggers: `ai-agent-platform/docs/features/workflow-webhook-triggers/README.md`
