from datetime import timezone as dt_timezone

from django.contrib.auth import get_user_model, login, logout
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from googleapiclient.discovery import build

from .google_oauth import build_flow
from .models import GoogleCredential


def home(request):
    return render(request, "home.html")


def google_login(request):
    flow = build_flow()
    auth_url, state = flow.authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
    )
    request.session["oauth_state"] = state
    return redirect(auth_url)


def google_callback(request):
    state = request.session.pop("oauth_state", None)
    if "error" in request.GET:
        return redirect("home")
    if not state or state != request.GET.get("state"):
        return HttpResponseBadRequest("Invalid OAuth state")

    flow = build_flow(state=state)
    flow.fetch_token(
    authorization_response=request.build_absolute_uri(),
    include_client_id=True,
)
    creds = flow.credentials

    info = build("oauth2", "v2", credentials=creds).userinfo().get().execute()

    User = get_user_model()
    user, _ = User.objects.get_or_create(
        username=info["email"],
        defaults={"email": info["email"], "first_name": info.get("given_name", "")},
    )

    cred, _ = GoogleCredential.objects.get_or_create(
        user=user, defaults={"google_id": info["id"], "access_token_enc": ""}
    )
    cred.google_id = info["id"]
    cred.set_tokens(creds.token, creds.refresh_token)
    cred.token_expiry = (
        timezone.make_aware(creds.expiry, dt_timezone.utc) if creds.expiry else None
    )
    cred.scopes = " ".join(creds.scopes or [])
    cred.save()

    login(request, user)
    return redirect("home")


@require_POST
def logout_view(request):
    logout(request)
    return redirect("home")