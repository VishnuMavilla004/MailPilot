from emails.models import Email
import base64

from .client import get_gmail_service
from .parser import parse_message
from email.message import EmailMessage
from email.utils import parseaddr


def sync_emails(user, max_results=20):
    """Fetch recent inbox emails and save the new ones. Returns how many were new."""
    service = get_gmail_service(user)
    response = service.users().messages().list(
        userId="me", labelIds=["INBOX"], maxResults=max_results
    ).execute()

    created = 0
    for item in response.get("messages", []):
        if Email.objects.filter(user=user, gmail_message_id=item["id"]).exists():
            continue  # already saved, so syncing twice never creates duplicates
        msg = service.users().messages().get(
            userId="me", id=item["id"], format="full"
        ).execute()
        Email.objects.create(user=user, **parse_message(msg))
        created += 1
    return created

def send_reply(user, draft):
    """Send the draft as a reply in the same Gmail thread."""
    service = get_gmail_service(user)
    email = draft.email

    # The original message's Message-ID lets Gmail attach our reply to the thread
    original = service.users().messages().get(
        userId="me",
        id=email.gmail_message_id,
        format="metadata",
        metadataHeaders=["Message-ID", "Message-Id"],
    ).execute()
    headers = {h["name"].lower(): h["value"] for h in original.get("payload", {}).get("headers", [])}
    message_id = headers.get("message-id")

    _, to_address = parseaddr(email.sender)
    subject = email.subject or ""

    msg = EmailMessage()
    msg["To"] = to_address
    msg["Subject"] = subject if subject.lower().startswith("re:") else f"Re: {subject}"
    if message_id:
        msg["In-Reply-To"] = message_id
        msg["References"] = message_id
    msg.set_content(draft.content)

    body = {"raw": base64.urlsafe_b64encode(msg.as_bytes()).decode()}
    if email.thread_id:
        body["threadId"] = email.thread_id
    service.users().messages().send(userId="me", body=body).execute()