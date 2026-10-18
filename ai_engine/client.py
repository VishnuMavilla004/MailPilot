from django.conf import settings
from openai import OpenAI


def get_client():
    # Same library, but pointed at Google's server instead of OpenAI's
    return OpenAI(
        api_key=settings.LLM_API_KEY,
        base_url=settings.LLM_BASE_URL,
        timeout=30,
        max_retries=2,
    )