from emails.models import AIUsageLog, Draft

from .llm import generate
from .prompts import DRAFT_SYSTEM


def generate_draft(email):
    """Ask the LLM for a reply to this email and save it as a pending Draft."""
    name = email.user.first_name or email.user.username.split("@")[0]
    content = (
        f"Sign off as: {name}\n\n"
        f"From: {email.sender}\nSubject: {email.subject}\n\n"
        f"Body:\n{email.body[:3000]}"
    )
    text, tokens = generate(DRAFT_SYSTEM, content)
    text = text.strip()
    if not text:
        raise ValueError("The model returned an empty draft. Try again.")

    draft = Draft.objects.create(email=email, content=text)
    AIUsageLog.objects.create(user=email.user, task_type="draft", tokens_used=tokens)
    return draft