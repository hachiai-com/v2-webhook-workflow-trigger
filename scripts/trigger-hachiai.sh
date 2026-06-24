#!/usr/bin/env bash
# Trigger HachiAI with Doculytix payload — optional custom prompt.
#
# Usage:
#   ./scripts/trigger-hachiai.sh
#   ./scripts/trigger-hachiai.sh --prompt "Summarize this invoice in 3 bullets"
#   ./scripts/trigger-hachiai.sh --inbox --prompt "Your custom instruction here"
#   ./scripts/trigger-hachiai.sh --document-url "https://example.com/inv.pdf"
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

CUSTOM_PROMPT=""
CUSTOM_DOC_URL=""
FORCE_INBOX=""
PAYLOAD=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prompt|-p)
      CUSTOM_PROMPT="${2:-}"
      shift 2
      ;;
    --document-url|-d)
      CUSTOM_DOC_URL="${2:-}"
      shift 2
      ;;
    --inbox)
      FORCE_INBOX=1
      shift
      ;;
    --payload)
      PAYLOAD="${2:-}"
      shift 2
      ;;
    -h|--help)
      sed -n '2,12p' "$0"
      exit 0
      ;;
    *)
      echo "Unknown option: $1" >&2
      exit 1
      ;;
  esac
done

# shellcheck disable=SC1091
source "${SCRIPT_DIR}/load-env.sh"
load_env_file "${ROOT}/.env"

if [[ -z "${HACHI_TRIGGER_SECRET:-}" ]]; then
  echo "Missing HACHI_TRIGGER_SECRET. Copy .env.example to .env" >&2
  exit 1
fi

use_inbox="${FORCE_INBOX:-${USE_HACHI_INBOX:-0}}"
if [[ "$use_inbox" == "1" || "$use_inbox" == "true" || "$use_inbox" == "yes" ]] || [[ -n "$CUSTOM_PROMPT" && -z "${HACHI_WEBHOOK_URL:-}" ]]; then
  if [[ -z "${HACHI_INBOX_URL:-}" ]]; then
    echo "Custom prompts need HACHI_INBOX_URL (Settings → External webhook inbox)." >&2
    echo "Or use --prompt with HACHI_WEBHOOK_URL to override a saved automation's prompt." >&2
    exit 1
  fi
  TARGET="$HACHI_INBOX_URL"
  PAYLOAD="${PAYLOAD:-${ROOT}/payloads/inbox-with-prompt.json}"
elif [[ -n "$CUSTOM_PROMPT" ]]; then
  TARGET="${HACHI_WEBHOOK_URL:?Set HACHI_WEBHOOK_URL for Doculytix trigger with custom prompt}"
  PAYLOAD="${PAYLOAD:-${ROOT}/payloads/doculytix-with-custom-prompt.json}"
else
  TARGET="${HACHI_WEBHOOK_URL:?Set HACHI_WEBHOOK_URL or use --inbox with HACHI_INBOX_URL}"
  PAYLOAD="${PAYLOAD:-${ROOT}/payloads/document-processed.json}"
fi

if [[ "$TARGET" == *"dev-nexus.hachiai.com"* ]]; then
  echo "Warning: use dev-agent-backend.hachiai.com, not Nexus" >&2
fi

BODY="$(python3 - "$PAYLOAD" "$CUSTOM_PROMPT" "$CUSTOM_DOC_URL" <<'PY'
import json, sys
path, prompt, doc_url = sys.argv[1], sys.argv[2], sys.argv[3]
data = json.load(open(path))
if prompt:
    data["prompt"] = prompt
if doc_url:
    data["document_url"] = doc_url
    if isinstance(data.get("data"), dict):
        data["data"]["file_url"] = doc_url
print(json.dumps(data))
PY
)"

echo "→ POST to ${TARGET}"
echo "$BODY" | python3 -m json.tool
echo ""

curl -sS -X POST "$TARGET" \
  -H "Content-Type: application/json" \
  -H "X-Trigger-Secret: ${HACHI_TRIGGER_SECRET}" \
  -d "$BODY" | python3 -m json.tool 2>/dev/null || cat

echo ""
echo "Keep HachiAI desktop open and logged in."
