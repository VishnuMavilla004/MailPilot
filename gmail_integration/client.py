from datetime import timezone as dt_timezone

from django.conf import settings
from django.utils import timezone
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from accounts.models import GoogleCredential


def get_credentials(user):
    """Rebuild Google credentials from the encrypted tokens in MySQL.
    If the access token has expired, refresh it and save the new one."""
    cred = GoogleCredential.objects.get(user=user)
    expiry = cred.token_expiry
    creds = Credentials(
        token=cred.get_access_token(),
        refresh_token=cred.get_refresh_token(),
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=cred.scopes.split(),
        # Google's library expects a naive UTC datetime
        expiry=expiry.astimezone(dt_timezone.utc).replace(tzinfo=None) if expiry else None,
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        cred.set_tokens(creds.token)
        cred.token_expiry = (
            timezone.make_aware(creds.expiry, dt_timezone.utc) if creds.expiry else None
        )
        cred.save()
    return creds


def get_gmail_service(user):
    return build("gmail", "v1", credentials=get_credentials(user), cache_discovery=False)