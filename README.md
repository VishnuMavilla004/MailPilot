# MailPilot
# MailPilot

AI-powered email assistant built with Django and MySQL. It connects to Gmail,
classifies emails with an LLM, drafts replies for human approval, and turns
meeting requests into Google Calendar events after a conflict check.

## Features
- Google OAuth 2.0 login; tokens are encrypted at rest (Fernet)
- Gmail sync into MySQL, with duplicate protection
- AI email classification (urgent, meeting, needs_reply, newsletter, spam, other) with confidence scores
- AI-drafted replies with edit, approve and send; nothing is sent without a click
- Meeting detection, Google Calendar free/busy check, event creation
- Dashboard with category counts, pending drafts, upcoming meetings and AI usage tracking
- Provider-agnostic LLM layer (Gemini native API or any OpenAI-compatible API)

## Tech stack
Python, Django, MySQL, Gmail API, Google Calendar API, Google OAuth 2.0, Gemini API

## Architecture
| Module | Responsibility |
|---|---|
| accounts | Google login, encrypted token storage |
| gmail_integration | Gmail API client, message parsing, sync, sending replies |
| calendar_integration | Free/busy checks, event creation |
| ai_engine | Prompts, LLM wrapper, classifier, draft writer, meeting extractor |
| emails | Models, views and templates for inbox, drafts, meetings, dashboard |

## Security and design decisions
- Email content is treated as untrusted input in every prompt (prompt-injection defence)
- Model output is validated; unknown categories fall back to "other"
- Human approval is required before any email is sent or event created
- Secrets live in `.env`; OAuth tokens are encrypted in the database
- Every AI call is logged with token counts

## Setup
1. `python -m venv venv` and activate it
2. `pip install -r requirements.txt`
3. Create a MySQL database and user, then copy `.env.example` to `.env` and fill it in
4. Create Google OAuth credentials (Gmail and Calendar APIs enabled) and add them to `.env`
5. `python manage.py migrate` then `python manage.py runserver`
6. Open http://localhost:8000

## Tests
`python manage.py test` (the LLM is mocked, so no API quota is used)

## Results
- Classification accuracy: [X/Y] on [Y] hand-checked emails
