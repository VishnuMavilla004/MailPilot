from datetime import datetime
from email.utils import parseaddr

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from ai_engine.classifier import classify_pending
from ai_engine.drafter import generate_draft
from ai_engine.extractor import extract_meeting
from calendar_integration.services import create_event, find_conflicts
from gmail_integration.services import send_reply, sync_emails

from .models import AIUsageLog, Draft, Email, Meeting

@login_required
def inbox(request):
    emails = request.user.emails.all()[:50]
    return render(request, "inbox.html", {"emails": emails})


@login_required
@require_POST
def sync(request):
    try:
        count = sync_emails(request.user)
        messages.success(request, f"Synced {count} new email(s).")
    except Exception as exc:
        messages.error(request, f"Sync failed: {exc}")
    return redirect("inbox")


@login_required
@require_POST
def classify(request):
    try:
        done, failed, last_error = classify_pending(request.user)
        if done == 0 and failed == 0:
            messages.info(request, "No unclassified emails.")
        elif failed:
            messages.warning(
                request, f"Classified {done}, failed {failed}. Last error: {last_error}"
            )
        else:
            messages.success(request, f"Classified {done} email(s).")
    except Exception as exc:
        messages.error(request, f"Classification failed: {exc}")
    return redirect("inbox")

@login_required
def email_detail(request, pk):
    email = get_object_or_404(Email, pk=pk, user=request.user)
    drafts = email.drafts.exclude(status=Draft.Status.DISCARDED).order_by("-created_at")
    prefill = request.session.pop(f"prefill_{pk}", None) or {}
    return render(request, "email_detail.html", {
        "email": email,
        "drafts": drafts,
        "meetings": email.meetings.all(),
        "default_title": prefill.get("title") or f"Meeting: {email.subject}"[:200],
        "default_start": prefill.get("start", ""),
        "default_end": prefill.get("end", ""),
        "default_attendees": prefill.get("attendees") or parseaddr(email.sender)[1],
    })


@login_required
@require_POST
def make_draft(request, pk):
    email = get_object_or_404(Email, pk=pk, user=request.user)
    if email.category in (Email.Category.NEWSLETTER, Email.Category.SPAM):
        messages.error(request, "No drafts for newsletters or spam.")
        return redirect("email_detail", pk=pk)
    try:
        generate_draft(email)
        messages.success(request, "Draft generated. Review it before sending.")
    except Exception as exc:
        text = str(exc)
        if "429" in text or "RESOURCE_EXHAUSTED" in text:
            messages.error(request, "AI rate limit reached. Wait a minute (or until tomorrow) and try again.")
        else:
            messages.error(request, f"Draft failed: {text[:300]}")
    return redirect("email_detail", pk=pk)


@login_required
@require_POST
def draft_action(request, pk):
    draft = get_object_or_404(Draft, pk=pk, email__user=request.user)
    if draft.status != Draft.Status.PENDING:
        messages.error(request, "This draft was already handled.")
        return redirect("email_detail", pk=draft.email_id)

    action = request.POST.get("action")
    content = request.POST.get("content", "").strip()

    if action == "discard":
        draft.status = Draft.Status.DISCARDED
        draft.save()
        messages.info(request, "Draft discarded.")
    elif not content:
        messages.error(request, "The draft is empty.")
    else:
        draft.content = content
        draft.save()
        if action == "send":
            try:
                send_reply(request.user, draft)
                draft.status = Draft.Status.SENT
                draft.save()
                messages.success(request, "Reply sent.")
            except Exception as exc:
                messages.error(request, f"Send failed: {str(exc)[:300]}")
        else:
            messages.success(request, "Draft saved.")
    return redirect("email_detail", pk=draft.email_id)


@login_required
@require_POST
def meeting_extract(request, pk):
    email = get_object_or_404(Email, pk=pk, user=request.user)
    try:
        info = extract_meeting(email)
    except Exception as exc:
        text = str(exc)
        if "429" in text or "RESOURCE_EXHAUSTED" in text:
            messages.error(request, "AI rate limit reached. Try again later, or fill the form by hand.")
        else:
            messages.error(request, f"Extraction failed: {text[:300]}")
        return redirect("email_detail", pk=pk)

    fmt = "%Y-%m-%dT%H:%M"
    request.session[f"prefill_{pk}"] = {
        "title": info["title"],
        "start": info["start"].strftime(fmt) if info["start"] else "",
        "end": info["end"].strftime(fmt) if info["end"] else "",
        "attendees": ", ".join(info["attendees"]),
    }
    if info["start"]:
        messages.success(request, "Details filled in below. Review them, check conflicts, then create the event.")
    else:
        messages.info(request, "No clear meeting time found in this email. Enter it by hand.")
    return redirect("email_detail", pk=pk)


@login_required
def dashboard(request):
    user = request.user
    start_of_day = timezone.localtime().replace(hour=0, minute=0, second=0, microsecond=0)
    usage = AIUsageLog.objects.filter(user=user, created_at__gte=start_of_day).aggregate(
        calls=Count("id"), tokens=Sum("tokens_used")
    )
    return render(request, "dashboard.html", {
        "total": user.emails.count(),
        "unclassified": user.emails.filter(processed_at__isnull=True).count(),
        "by_category": user.emails.exclude(category="").values("category").annotate(n=Count("id")).order_by("-n"),
        "pending_drafts": Draft.objects.filter(
            email__user=user, status=Draft.Status.PENDING
        ).select_related("email")[:10],
        "upcoming": Meeting.objects.filter(
            email__user=user, status=Meeting.Status.CREATED, start_time__gte=timezone.now()
        ).order_by("start_time")[:10],
        "calls_today": usage["calls"] or 0,
        "tokens_today": usage["tokens"] or 0,
    })

def _fmt(dt):
    return dt.strftime("%d %b %H:%M")


@login_required
@require_POST
def meeting_create(request, pk):
    email = get_object_or_404(Email, pk=pk, user=request.user)
    try:
        title = request.POST["title"].strip()
        start = timezone.make_aware(datetime.fromisoformat(request.POST["start"]))
        end = timezone.make_aware(datetime.fromisoformat(request.POST["end"]))
    except (KeyError, ValueError):
        messages.error(request, "Please enter a title, start time and end time.")
        return redirect("email_detail", pk=pk)

    if not title or end <= start:
        messages.error(request, "The end time must be after the start time.")
        return redirect("email_detail", pk=pk)

    try:
        conflicts = find_conflicts(request.user, start, end)
    except Exception as exc:
        messages.error(request, f"Calendar check failed: {str(exc)[:300]}")
        return redirect("email_detail", pk=pk)

    action = request.POST.get("action")
    if action == "check":
        if conflicts:
            busy = ", ".join(f"{_fmt(s)}-{_fmt(e)}" for s, e in conflicts)
            messages.warning(request, f"You are busy: {busy}")
        else:
            messages.success(request, "You are free at that time.")
        return redirect("email_detail", pk=pk)

    if conflicts and not request.POST.get("force"):
        messages.warning(request, "You have a conflict. Tick 'Create even if I am busy' to continue.")
        return redirect("email_detail", pk=pk)

    meeting = Meeting.objects.create(
        email=email,
        title=title[:255],
        start_time=start,
        end_time=end,
        attendees=request.POST.get("attendees", "").strip(),
    )
    try:
        meeting.calendar_event_id = create_event(request.user, meeting)
        meeting.status = Meeting.Status.CREATED
        meeting.save()
        messages.success(request, "Event created in your Google Calendar.")
    except Exception as exc:
        meeting.delete()
        messages.error(request, f"Could not create event: {str(exc)[:300]}")
    return redirect("email_detail", pk=pk)