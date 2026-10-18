import re
from datetime import datetime, timedelta

from django.utils import timezone

from emails.models import AIUsageLog

from .classifier import _parse_json
from .llm import generate
from .prompts import MEETING_SYSTEM

EMAIL_RE = re.compile(r"[^@\s]+@[^@\s]+\.[^@\s]+")


def _parse_dt(value):
    try:
        return datetime.fromisoformat(str(value).strip()[:16])  # "YYYY-MM-DDTHH:MM"
    except (ValueError, TypeError):
        return None


def extract_meeting(email):
    """Ask the LLM for meeting details. Returns a validated dict; nothing is saved."""
    now = timezone.localtime()
    content = (
        f"Current date and time: {now:%A, %Y-%m-%d %H:%M} ({timezone.get_current_timezone()})\n\n"
        f"From: {email.sender}\nSubject: {email.subject}\n\nBody:\n{email.body[:3000]}"
    )
    text, tokens = generate(MEETING_SYSTEM, content)
    data = _parse_json(text)

    is_meeting = bool(data.get("is_meeting"))
    start = _parse_dt(data.get("start")) if is_meeting else None
    end = _parse_dt(data.get("end")) if start else None
    if start and (not end or end <= start):
        end = start + timedelta(hours=1)  # default length: one hour

    attendees = [
        a.strip() for a in (data.get("attendees") or [])
        if isinstance(a, str) and EMAIL_RE.fullmatch(a.strip())
    ]
    title = str(data.get("title") or f"Meeting: {email.subject}")[:200]

    AIUsageLog.objects.create(user=email.user, task_type="extract_meeting", tokens_used=tokens)
    return {"is_meeting": is_meeting, "title": title, "start": start, "end": end, "attendees": attendees}