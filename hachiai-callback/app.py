"""
Doculytix V1 → HachiAI webhook callback simulator.

Simulates Doculytix firing `document.processed` to HachiAI after OCR completes.

Endpoints:
  GET  /health
  POST /simulate/document-processed   — build Doculytix payload and POST to HachiAI
  POST /webhook/hachiai                 — same (alias for pipeline-style naming)
"""

from __future__ import annotations

import os
import uuid
from typing import Any

import requests
from flask import Flask, jsonify, request

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


def _hachi_target() -> str | None:
    if USE_HACHI_INBOX and HACHI_INBOX_URL:
        return HACHI_INBOX_URL
    if HACHI_WEBHOOK_URL:
        return HACHI_WEBHOOK_URL
    if HACHI_INBOX_URL:
        return HACHI_INBOX_URL
    return None


def _build_doculytix_payload(body: dict[str, Any]) -> dict[str, Any]:
    document_url = (body.get("document_url") or DEFAULT_DOCUMENT_URL).strip()
    trace_id = (body.get("trace_id") or f"doculytix-{uuid.uuid4().hex[:12]}").strip()
    metadata = body.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {
            "tenant_id": body.get("tenant_id") or "bank-a",
            "document_type": body.get("document_type") or "invoice",
        }

    if USE_HACHI_INBOX or (HACHI_INBOX_URL and not HACHI_WEBHOOK_URL):
        prompt = (body.get("prompt") or DEFAULT_INBOX_PROMPT).strip()
        return {
            "prompt": prompt,
            "event": "document.processed",
            "document_url": document_url,
            "trace_id": trace_id,
            "metadata": metadata,
        }

    payload: dict[str, Any] = {
        "event": "document.processed",
        "document_url": document_url,
        "trace_id": trace_id,
        "metadata": metadata,
    }
    custom_prompt = (body.get("prompt") or "").strip()
    if custom_prompt:
        payload["prompt"] = custom_prompt
    return payload


def _notify_hachiai(payload: dict[str, Any]) -> tuple[int, str, str]:
    url = _hachi_target()
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


@app.get("/health")
def health():
    return jsonify(
        {
            "ok": True,
            "service": "doculytix-hachiai-callback-simulator",
            "hachi_target": _hachi_target(),
            "use_inbox": USE_HACHI_INBOX or bool(HACHI_INBOX_URL and not HACHI_WEBHOOK_URL),
            "default_document_url": DEFAULT_DOCUMENT_URL,
        }
    )


@app.post("/simulate/document-processed")
@app.post("/webhook/hachiai")
def simulate_document_processed():
    """
    Simulate Doculytix V1 completing OCR and notifying HachiAI.

    Body (all optional):
      document_url, trace_id, tenant_id, document_type, metadata, prompt (inbox only)
    """
    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        body = {}

    try:
        payload = _build_doculytix_payload(body)
        status, text, url = _notify_hachiai(payload)
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
