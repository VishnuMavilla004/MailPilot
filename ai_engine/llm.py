from django.conf import settings


def generate(system, user):
    """Send a system prompt and a user message to the LLM.
    Returns (text, tokens_used)."""
    if settings.LLM_PROVIDER == "gemini":
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=settings.LLM_API_KEY)
        response = client.models.generate_content(
            model=settings.LLM_MODEL,
            contents=user,
            config=types.GenerateContentConfig(system_instruction=system, temperature=0),
        )
        tokens = getattr(response.usage_metadata, "total_token_count", 0) or 0
        return response.text or "", tokens

    # Any OpenAI-compatible provider (Groq, Ollama, OpenAI...)
    from .client import get_client

    response = get_client().chat.completions.create(
        model=settings.LLM_MODEL,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0,
    )
    tokens = getattr(response.usage, "total_tokens", 0) or 0
    return response.choices[0].message.content or "", tokens