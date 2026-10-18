# Create your tests here.
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from ai_engine.classifier import _parse_json, classify_email
from ai_engine.extractor import extract_meeting
from emails.models import AIUsageLog, Email

User = get_user_model()


def make_email(user, **kwargs):
    defaults = dict(
        gmail_message_id="abc123",
        sender="Alex <alex@example.com>",
        subject="Hello",
        body="Can we meet tomorrow at 3pm?",
        received_at=timezone.now(),
    )
    defaults.update(kwargs)
    return Email.objects.create(user=user, **defaults)


class ClassifierTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("a@example.com", "a@example.com", "pw")
        self.email = make_email(self.user)

    @patch("ai_engine.classifier.generate")
    def test_valid_response_is_saved(self, mock_generate):
        mock_generate.return_value = ('{"category": "newsletter", "confidence": 0.93}', 120)
        classify_email(self.email)
        self.email.refresh_from_db()
        self.assertEqual(self.email.category, "newsletter")
        self.assertAlmostEqual(self.email.confidence, 0.93)
        self.assertIsNotNone(self.email.processed_at)
        self.assertEqual(AIUsageLog.objects.get().tokens_used, 120)

    @patch("ai_engine.classifier.generate")
    def test_unknown_category_falls_back_to_other(self, mock_generate):
        mock_generate.return_value = ('{"category": "made_up", "confidence": 5}', 10)
        classify_email(self.email)
        self.email.refresh_from_db()
        self.assertEqual(self.email.category, "other")
        self.assertEqual(self.email.confidence, 1.0)  # clamped to the 0-1 range

    @patch("ai_engine.classifier.generate")
    def test_garbage_response_does_not_crash(self, mock_generate):
        mock_generate.return_value = ("sorry, I cannot help", 5)
        classify_email(self.email)
        self.email.refresh_from_db()
        self.assertEqual(self.email.category, "other")
        self.assertEqual(self.email.confidence, 0.0)

    def test_parse_json_strips_code_fences(self):
        text = '```json\n{"category": "urgent", "confidence": 0.8}\n```'
        self.assertEqual(_parse_json(text)["category"], "urgent")


class ExtractorTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("a@example.com", "a@example.com", "pw")
        self.email = make_email(self.user)

    @patch("ai_engine.extractor.generate")
    def test_default_end_is_one_hour_after_start(self, mock_generate):
        mock_generate.return_value = (
            '{"is_meeting": true, "title": "Sync", "start": "2026-10-20T15:00", '
            '"end": null, "attendees": ["alex@example.com", "not-an-email"]}',
            50,
        )
        info = extract_meeting(self.email)
        self.assertEqual(info["start"].hour, 15)
        self.assertEqual(info["end"].hour, 16)
        self.assertEqual(info["attendees"], ["alex@example.com"])

    @patch("ai_engine.extractor.generate")
    def test_no_meeting_means_no_times(self, mock_generate):
        mock_generate.return_value = ('{"is_meeting": false, "start": "2026-10-20T15:00"}', 5)
        info = extract_meeting(self.email)
        self.assertIsNone(info["start"])
        self.assertIsNone(info["end"])


class ViewAccessTests(TestCase):
    def setUp(self):
        self.alice = User.objects.create_user("alice@example.com", "alice@example.com", "pw")
        self.bob = User.objects.create_user("bob@example.com", "bob@example.com", "pw")
        self.bobs_email = make_email(self.bob)

    def test_inbox_requires_login(self):
        response = self.client.get(reverse("inbox"))
        self.assertEqual(response.status_code, 302)

    def test_user_cannot_open_another_users_email(self):
        self.client.force_login(self.alice)
        response = self.client.get(reverse("email_detail", args=[self.bobs_email.pk]))
        self.assertEqual(response.status_code, 404)