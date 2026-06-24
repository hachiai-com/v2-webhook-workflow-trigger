#!/usr/bin/env python3
"""CLI: POST Doculytix document.processed payload to HachiAI (no simulator server)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
PAYLOADS = ROOT / "payloads"


def load_dotenv() -> None:
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def main() -> int:
    load_dotenv()
    secret = os.environ.get("HACHI_TRIGGER_SECRET", "").strip()
    if not secret:
        print("Set HACHI_TRIGGER_SECRET", file=sys.stderr)
        return 1

    use_inbox = os.environ.get("USE_HACHI_INBOX", "").strip().lower() in ("1", "true", "yes")
    if use_inbox:
        url = os.environ.get("HACHI_INBOX_URL", "").strip()
        payload_file = PAYLOADS / "inbox-with-prompt.json"
    else:
        url = os.environ.get("HACHI_WEBHOOK_URL", "").strip()
        payload_file = PAYLOADS / "document-processed.json"

    if not url:
        print("Set HACHI_WEBHOOK_URL or HACHI_INBOX_URL", file=sys.stderr)
        return 1

    payload = json.loads(payload_file.read_text())
    doc = os.environ.get("DEFAULT_DOCUMENT_URL", "").strip()
    if doc:
        payload["document_url"] = doc

    print(f"POST {url}\n{json.dumps(payload, indent=2)}\n")
    response = requests.post(
        url,
        headers={"Content-Type": "application/json", "X-Trigger-Secret": secret},
        json=payload,
        timeout=60,
    )
    print(f"HTTP {response.status_code}\n{response.text}")
    response.raise_for_status()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
