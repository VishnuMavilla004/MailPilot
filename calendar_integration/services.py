from datetime import datetime

from django.utils import timezone
from googleapiclient.discovery import build

from gmail_integration.client import get_credentials


def get_calendar_service(user):
    return build("calendar", "v3", credentials=get_credentials(user), cache_discovery=False)


def _parse_google_time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def find_conflicts(user, start, end):
    """Return a list of (start, end) busy periods that overlap the proposed meeting."""
    service = get_calendar_service(user)
    body = {
        "timeMin": start.isoformat(),
        "timeMax": end.isoformat(),
        "timeZone": str(timezone.get_current_timezone()),
        "items": [{"id": "primary"}],
    }
    result = service.freebusy().query(body=body).execute()
    busy = result.get("calendars", {}).get("primary", {}).get("busy", [])
    local = timezone.get_current_timezone()
    return [
        (_parse_google_time(b["start"]).astimezone(local),
         _parse_google_time(b["end"]).astimezone(local))
        for b in busy
    ]


def create_event(user, meeting):
    """Create the event in the user's primary calendar. Returns Google's event id."""
    service = get_calendar_service(user)
    tz = str(timezone.get_current_timezone())
    attendees = [a.strip() for a in meeting.attendees.split(",") if "@" in a]
    body = {
        "summary": meeting.title,
        "description": f"Created by MailPilot from the email: {meeting.email.subject}",
        "start": {"dateTime": meeting.start_time.isoformat(), "timeZone": tz},
        "end": {"dateTime": meeting.end_time.isoformat(), "timeZone": tz},
        "attendees": [{"email": a} for a in attendees],
    }
    event = service.events().insert(
        calendarId="primary",
        body=body,
        sendUpdates="all" if attendees else "none",  # only email invitations if there are attendees
    ).execute()
    return event["id"]