import base64
import re
from datetime import datetime, timezone as dt_timezone
from email.utils import parseaddr


def _decode(data):
    data += "=" * (-len(data) % 4)  # restore base64 padding
    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")


def _find_part(payload, mime_type):
    """Search the message parts (they can be nested) for a given type."""
    body = payload.get("body", {})
    if payload.get("mimeType") == mime_type and body.get("data"):
        return _decode(body["data"])
    for part in payload.get("parts") or []:
        found = _find_part(part, mime_type)
        if found:
            return found
    return ""


def extract_body(payload):
    text = _find_part(payload, "text/plain")
    if not text:  # some emails are HTML only
        html = _find_part(payload, "text/html")
        text = re.sub(r"<style.*?</style>|<script.*?</script>", " ", html, flags=re.S)
        text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"[ \t]+", " ", text).strip()[:20000]


def parse_message(msg):
    """Turn a raw Gmail message into the fields our Email model needs."""
    headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}
    name, address = parseaddr(headers.get("from", ""))
    sender = f"{name} <{address}>" if name else address
    return {
        "gmail_message_id": msg["id"],
        "thread_id": msg.get("threadId", ""),
        "sender": sender[:255],
        "subject": headers.get("subject", "")[:500],
        "body": extract_body(msg["payload"]),
        "received_at": datetime.fromtimestamp(
            int(msg["internalDate"]) / 1000, tz=dt_timezone.utc
        ),
    }