# Doculytix V1 — HachiAI V2 webhook integration

This folder contains a **runnable example** of Doculytix V1 notifying HachiAI when document processing completes (`document.processed`).

## Quick start

1. In **HachiAI V2**: My Automations → your invoice workflow → **Triggers** → **Doculytix V1** → create webhook. Copy URL + secret.

   Or use the global inbox: **Settings → General → External webhook inbox**.

2. Configure env:

```bash
cp .env.example .env
# Edit .env with your HACHI_WEBHOOK_URL and HACHI_TRIGGER_SECRET
```

3. Run the callback simulator:

```bash
docker compose up --build
# or: cd hachiai-callback && pip install -r requirements.txt && python app.py
```

4. Simulate Doculytix finishing OCR on a document:

```bash
curl -X POST http://localhost:8080/simulate/document-processed \
  -H "Content-Type: application/json" \
  -d '{"document_url":"https://docx.hachiai.com/storage/invoices/sample-invoice.pdf"}'
```

5. Keep **HachiAI desktop open and logged in** — Runway should start your workflow within a few seconds.

See **[README-HACHIAI.md](./README-HACHIAI.md)** for payload format, setup details, and troubleshooting.

## Layout

| Path | Purpose |
|------|---------|
| `hachiai-callback/` | Mini service: simulates Doculytix → POST HachiAI webhook |
| `payloads/` | Example `document.processed` JSON bodies |
| `scripts/` | CLI helpers without Docker |

## Related docs

- HachiAI full guide: `ai-agent-platform/docs/features/workflow-webhook-triggers/README.md`
- HTML presentation: `ai-agent-platform/docs/features/workflow-webhook-triggers/webhook-triggers-guide.html`
- To test from within the repo, run this in the terminal of this repo: ./scripts/trigger-hachiai.sh --inbox --prompt "What is the result of 10-10+1" 
- Copy env.example and create .env and then paste required link and hash from the v2