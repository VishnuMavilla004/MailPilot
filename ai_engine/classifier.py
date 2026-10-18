import json
import logging
import re
import time

from django.conf import settings
from django.utils import timezone

from emails.models import AIUsageLog, Email

from .client import get_client
from .prompts import CLASSIFY_SYSTEM

from .llm import generate

logger = logging.getLogger(__name__)
VALID_CATEGORIES = {c.value for c in Email.Category}


def _parse_json(text):
    """Models sometimes wrap JSON in ```json fences. Strip them, then parse."""
    text = re.sub(r"^```(?:json)?|```$", "", (text or "").strip(), flags=re.M).strip()
    try:
        data = json.loads(text)
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}


def classify_email(email):
    """Send one email to the LLM, validate the answer, save it, log token usage."""
    content = f"From: {email.sender}\nSubject: {email.subject}\n\nBody:\n{email.body[:3000]}"

    text, tokens = generate(CLASSIFY_SYSTEM, content)
    data = _parse_json(text)

    category = data.get("category")
    if category not in VALID_CATEGORIES:
        category = Email.Category.OTHER

    try:
        confidence = max(0.0, min(1.0, float(data.get("confidence", 0))))
    except (TypeError, ValueError):
        confidence = 0.0

    email.category = category
    email.confidence = confidence
    email.processed_at = timezone.now()
    email.save(update_fields=["category", "confidence", "processed_at"])

    AIUsageLog.objects.create(
        user=email.user, task_type="classify", tokens_used=tokens
    )
    return category, confidence

def classify_pending(user, limit=10):
    """Classify emails not yet processed. Returns (done, failed, last_error)."""
    pending = list(Email.objects.filter(user=user, processed_at__isnull=True)[:limit])
    done = failed = 0
    last_error = ""
    for email in pending:
        try:
            classify_email(email)
            done += 1
        except Exception as exc:
            logger.exception("Classification failed for email %s", email.pk)
            failed += 1
            last_error = str(exc)[:300]
        time.sleep(2)  # stay under the free tier's requests-per-minute limit
    return done, failed, last_error