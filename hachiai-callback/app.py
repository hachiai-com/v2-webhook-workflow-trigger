"""
Doculytix V1 → HachiAI webhook callback simulator.

Simulates Doculytix firing `document.processed` to HachiAI after OCR completes.

Endpoints:
  GET  /
  GET  /health
  GET  /api/config
  POST /simulate/document-processed   — Doculytix payload → saved automation webhook
  POST /simulate/inbox                — inbox custom prompt (like --inbox --prompt)
  POST /webhook/hachiai                 — alias for document-processed
"""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request

_app_dir = Path(__file__).resolve().parent
for _env_path in (_app_dir / ".env", _app_dir.parent / ".env"):
    if _env_path.is_file():
        load_dotenv(_env_path)
        break

app = Flask(__name__)

HACHI_WEBHOOK_URL = (os.environ.get("HACHI_WEBHOOK_URL") or "").strip().rstrip("/")
HACHI_INBOX_URL = (os.environ.get("HACHI_INBOX_URL") or "").strip().rstrip("/")
HACHI_TRIGGER_SECRET = (os.environ.get("HACHI_TRIGGER_SECRET") or "").strip()
USE_HACHI_INBOX = os.environ.get("USE_HACHI_INBOX", "").strip().lower() in ("1", "true", "yes")
DEFAULT_DOCUMENT_URL = (
    os.environ.get("DEFAULT_DOCUMENT_URL") or "https://docx.hachiai.com/storage/invoices/sample-invoice-2026.pdf"
).strip()
DEFAULT_INBOX_PROMPT = (
    os.environ.get("HACHI_INBOX_PROMPT")
    or "Process this invoice: extract vendor, line items, tax, and total."
).strip()


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("1", "true", "yes")


def _resolve_target(body: dict[str, Any] | None = None) -> str | None:
    body = body or {}
    force_inbox = _truthy(body.get("use_inbox"))
    if force_inbox:
        return HACHI_INBOX_URL or None
    if USE_HACHI_INBOX and HACHI_INBOX_URL:
        return HACHI_INBOX_URL
    if HACHI_WEBHOOK_URL:
        return HACHI_WEBHOOK_URL
    if HACHI_INBOX_URL:
        return HACHI_INBOX_URL
    return None


def _build_doculytix_payload(body: dict[str, Any]) -> dict[str, Any]:
    force_inbox = _truthy(body.get("use_inbox"))
    use_inbox = force_inbox or USE_HACHI_INBOX or bool(HACHI_INBOX_URL and not HACHI_WEBHOOK_URL)

    prompt = (body.get("prompt") or "").strip()
    document_url = (body.get("document_url") or "").strip()
    trace_id = (body.get("trace_id") or f"doculytix-{uuid.uuid4().hex[:12]}").strip()

    if use_inbox:
        if not HACHI_INBOX_URL:
            raise ValueError("Set HACHI_INBOX_URL in .env for inbox mode (Settings → External webhook inbox)")
        if not prompt:
            raise ValueError("Prompt is required for inbox mode")

        if not document_url:
            return {"data": prompt}

        metadata = body.get("metadata")
        if not isinstance(metadata, dict):
            metadata = {
                "tenant_id": body.get("tenant_id") or "bank-a",
                "document_type": body.get("document_type") or "invoice",
            }
        return {
            "prompt": prompt,
            "event": "document.processed",
            "document_url": document_url,
            "trace_id": trace_id,
            "metadata": metadata,
        }

    document_url = document_url or DEFAULT_DOCUMENT_URL
    metadata = body.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {
            "tenant_id": body.get("tenant_id") or "bank-a",
            "document_type": body.get("document_type") or "invoice",
        }

    payload: dict[str, Any] = {
        "event": "document.processed",
        "document_url": document_url,
        "trace_id": trace_id,
        "metadata": metadata,
    }
    if prompt:
        payload["prompt"] = prompt
    return payload


def _notify_hachiai(payload: dict[str, Any], body: dict[str, Any] | None = None) -> tuple[int, str, str]:
    url = _resolve_target(body)
    if not url:
        raise ValueError("Set HACHI_WEBHOOK_URL or HACHI_INBOX_URL in environment")
    if not HACHI_TRIGGER_SECRET:
        raise ValueError("Set HACHI_TRIGGER_SECRET in environment")

    response = requests.post(
        url,
        headers={
            "Content-Type": "application/json",
            "X-Trigger-Secret": HACHI_TRIGGER_SECRET,
        },
        json=payload,
        timeout=60,
    )
    return response.status_code, response.text, url


@app.get("/")
def index():
    return render_template("index.html")


@app.get("/api/config")
def api_config():
    return jsonify(
        {
            "default_document_url": DEFAULT_DOCUMENT_URL,
            "default_inbox_prompt": DEFAULT_INBOX_PROMPT,
            "use_inbox": USE_HACHI_INBOX or bool(HACHI_INBOX_URL and not HACHI_WEBHOOK_URL),
            "hachi_configured": bool(_resolve_target() and HACHI_TRIGGER_SECRET),
            "hachi_webhook_url": HACHI_WEBHOOK_URL or None,
            "hachi_inbox_url": HACHI_INBOX_URL or None,
        }
    )


@app.get("/health")
def health():
    return jsonify(
        {
            "ok": True,
            "service": "doculytix-hachiai-callback-simulator",
            "hachi_target": _resolve_target(),
            "hachi_webhook_url": HACHI_WEBHOOK_URL or None,
            "hachi_inbox_url": HACHI_INBOX_URL or None,
            "hachi_configured": bool(_resolve_target() and HACHI_TRIGGER_SECRET),
            "use_inbox": USE_HACHI_INBOX or bool(HACHI_INBOX_URL and not HACHI_WEBHOOK_URL),
            "default_document_url": DEFAULT_DOCUMENT_URL,
        }
    )


@app.post("/simulate/document-processed")
@app.post("/webhook/hachiai")
@app.post("/simulate/inbox")
def simulate_document_processed():
    """
    Simulate Doculytix V1 completing OCR and notifying HachiAI.

    Body (all optional unless noted):
      use_inbox — force global inbox (like --inbox); prompt required
      document_url, trace_id, tenant_id, document_type, metadata, prompt
    """
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        body = {}

    try:
        payload = _build_doculytix_payload(body)
        status, text, url = _notify_hachiai(payload, body)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except requests.RequestException as e:
        return jsonify({"error": f"HachiAI request failed: {e}"}), 502

    ok = 200 <= status < 300
    return jsonify(
        {
            "message": "Doculytix document.processed simulated",
            "hachi_url": url,
            "payload_sent": payload,
            "hachi_status": status,
            "hachi_response": text[:2000],
            "success": ok,
        }
    ), (200 if ok else 502)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    app.run(host="0.0.0.0", port=port)
