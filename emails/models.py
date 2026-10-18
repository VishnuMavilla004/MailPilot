# Create your models here.
from django.conf import settings
from django.db import models

class Email(models.Model):
    class Category(models.TextChoices):
        URGENT = "urgent"
        MEETING = "meeting"
        NEEDS_REPLY = "needs_reply"
        NEWSLETTER = "newsletter"
        SPAM = "spam"
        OTHER = "other"

    user = models.ForeignKey(
    settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="emails"
)
    gmail_message_id = models.CharField(max_length=64)
    thread_id = models.CharField(max_length=64, blank=True)
    sender = models.CharField(max_length=255)
    subject = models.CharField(max_length=500, blank=True)
    body = models.TextField(blank=True)
    received_at = models.DateTimeField()
    category = models.CharField(max_length=20, choices=Category.choices, blank=True)
    confidence = models.FloatField(null=True)
    processed_at = models.DateTimeField(null=True)

    class Meta:
        unique_together = ("user", "gmail_message_id")  # never store the same email twice
        indexes = [models.Index(fields=["user", "-received_at"])]
        ordering = ["-received_at"]

class Draft(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending"
        APPROVED = "approved"
        SENT = "sent"
        DISCARDED = "discarded"

    email = models.ForeignKey(Email, on_delete=models.CASCADE, related_name="drafts")
    content = models.TextField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PENDING)
    created_at = models.DateTimeField(auto_now_add=True)

class Meeting(models.Model):
    class Status(models.TextChoices):
        PROPOSED = "proposed"
        CREATED = "created"
        DECLINED = "declined"

    email = models.ForeignKey(Email, on_delete=models.CASCADE, related_name="meetings")
    title = models.CharField(max_length=255)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    attendees = models.TextField(blank=True)
    calendar_event_id = models.CharField(max_length=128, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.PROPOSED)

class AIUsageLog(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    task_type = models.CharField(max_length=30)
    tokens_used = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)