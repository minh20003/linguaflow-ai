# LinguaFlow

Realtime multilingual chat with context-aware AI translation. Users chat in their preferred language while the system automatically translates messages between participants.

## Live Demo

| | |
|---|---|
| App | https://c3-lingua-flow-217.dquangminh2003.id.vn |
| API health | https://api-c3-lingua-flow-217.dquangminh2003.id.vn/health |

Sign up with your own email — registration sends a one-time code — or use the
seeded demo accounts in [Development Accounts](#development-accounts) below.

## What LinguaFlow Does

- Realtime direct and group messaging
- Per-user preferred translation language
- Automatic source-language detection
- Context-aware translation using recent conversation messages
- Recipient-language fan-out in group chats
- Toggle between original and translated text
- Translation fallback when LLM fails
- Translation feedback and correction
- WebSocket reconnection with idempotent message delivery
- Recorded voice messages with durable transcription, retry, playback, and the
  same context-aware translation UI as text
- Admin translation statistics
- Multilingual interface

## How It Works

```
Text → WebSocket ───────────────────────────────┐
                                               ├→ persisted original_text → existing Translation Service → LangGraph Agent → LLM
Voice → authenticated upload → Gemini 3.5 Transcribe (verbatim) ┘
```

[Architecture diagram](docs/gate2_architecture.md)

## Tech Stack

### Frontend
- Next.js 16.3
- React 19.2
- TypeScript

### Backend
- FastAPI + Uvicorn
- Python 3.11+
- WebSocket
- JWT Authentication

### AI Agent
- LangGraph + LangChain
- Provider-neutral LLM adapter (Groq, DeepSeek, Gemini, OpenAI)
- langdetect
- deep-translator (fallback)

### Database
- SQLAlchemy Async ORM
- PostgreSQL + pgvector (development and production)
- Alembic migrations

### Observability
- Braintrust (optional, default), or Langfuse — set `OBSERVABILITY_PROVIDER`

## Prerequisites

- Python 3.11+
- Node.js 20+
- npm
- No separate FFmpeg install is required: the pinned `imageio-ffmpeg` platform
  wheel provides the binary used for temporary STT preprocessing

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd <repository>

# Backend setup
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
# .venv\Scripts\activate  # Windows

pip install -r requirements.txt

# Frontend setup
cd frontend
npm install
cd ..
```

## Configuration

```bash
cp .env.example .env
```

### Required

```env
# Generate with: python -c "import secrets; print(secrets.token_urlsafe(48))"
JWT_SECRET=your-generated-secret
```

### LLM Provider

Only one provider needs an API key:

```env
LLM_PROVIDER=groq  # groq | deepseek | gemini | openai
GROQ_API_KEY=your-groq-key
```

### Voice message STT

Voice configuration is independent of `LLM_PROVIDER`. Gemini 3.5 Transcribe
uses the existing `GOOGLE_API_KEY`/`GEMINI_API_KEY` convention, the non-live
Files + Interactions transcription flow in verbatim mode, and stores the
complete original-language transcript in
`Message.original_text`.

```env
STT_PROVIDER=gemini
STT_MODEL=gemini-3.5-transcribe
STT_TIMEOUT_SECONDS=60
STT_RETRY_ATTEMPTS=3
GOOGLE_API_KEY=your-gemini-key
```

Files and Interactions use one bounded retry policy for transient 408, 429 and
5xx responses. Permanent 4xx responses, invalid audio and blank transcripts
fail without retry and are logged with safe machine-readable metadata only.

The recorder selects by `MediaRecorder.isTypeSupported()` rather than browser
name. It accepts browser-native WebM/Opus, OGG/Opus or Vorbis, and MP4/AAC or
Opus, plus direct AAC, AIFF, FLAC, MP3 and WAV inputs. The durable attachment is
always the exact uploaded recording. When its container is not a direct Gemini
input, the backend uses a fixed, shell-free FFmpeg command to produce a bounded
temporary mono 16 kHz FLAC for STT only; that output is never stored as the
message audio or placed in translation context.

The durable lifecycle is `pending → completed` or `pending → failed`. A failed
message keeps the same audio and can be retried through
`POST /api/v1/messages/{message_id}/transcription/retry`; an atomic
`failed → pending` transition prevents concurrent retries from launching two
authoritative jobs. Only a committed completed transcript enters the existing
text translation, context, glossary, tone and honorific pipeline. UI labels
such as “Voice message” and “Transcribing…” are presentation only and are never
stored in `Message.original_text`.

Current limitations: audio is buffered in memory up to the configured upload
cap (20 MiB by default), background work is process-local, and there is a crash
window after a durable lifecycle transition but before its realtime event or
next task is scheduled. Refresh/history recovers persisted state; it is not a
durable job queue. Browser/container support must be verified with the target
browser and OS because MediaRecorder capabilities vary.

### Database

```env
# PostgreSQL with pgvector (development and production)
DATABASE_URL=postgresql+asyncpg://user:password@host:5432/dbname
```

## Database Setup

```bash
make migrate
```

## Run Locally

### Terminal 1 — Backend

```bash
source .venv/bin/activate  # or .venv\Scripts\activate on Windows
make migrate
make run
```

Backend runs at: http://localhost:8000

### Terminal 2 — Frontend

```bash
cd frontend
npm run dev
```

Frontend runs at: http://localhost:3000

## Development Accounts

Two demo accounts created by `make reset-db`:

| Email | Password | Preferred Language | Role |
|-------|----------|-------------------|------|
| member@test.com | testpass123 | English (en) | member |
| admin@test.com | adminpass123 | Vietnamese (vi) | admin |

## Tests

```bash
# Backend tests
make test

# Linting
make lint

# Frontend
cd frontend
npm test
npx tsc --noEmit
npm run lint
npm run build
cd ..
```

## Evaluation

LinguaFlow includes 53 golden test cases for translation quality evaluation.

```bash
# Run full evaluation
python eval/run_eval.py

# Run subset for quick testing
python eval/run_eval.py --limit 10
```

Results are written to `eval/results/report.md` and `eval/results/<run-id>.json`.

Gate 2 evidence: `eval/gate2_evidence.md`

## Project Structure

```
.
├── frontend/               # Active production Next.js frontend
│   └── package.json
├── frontend-v1/            # Legacy tree; do not add current product work here
├── src/
│   ├── agents/           # LangGraph translation agent
│   ├── api/              # FastAPI routes
│   ├── core/             # Security, dependencies
│   ├── database/         # SQLAlchemy models
│   ├── schemas/          # Pydantic schemas
│   ├── services/         # Business logic
│   ├── config.py        # Settings
│   └── main.py           # App entry point
├── tests/                # pytest suite
├── eval/                 # Evaluation framework
│   ├── golden_set.jsonl  # 53 test cases
│   └── run_eval.py       # Evaluation runner
├── scripts/
│   └── seed_dev_users.py
├── docs/
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Deployment

See [docs/DEPLOY.md](docs/DEPLOY.md) for detailed deployment instructions.

Summary:
- **Runtime**: Ubuntu VPS with Docker Compose and Caddy
- **Frontend + Backend**: immutable GHCR images in the production Compose contract (CD-1; publication/deployment workflow comes later)
- **Database**: local PostgreSQL + pgvector durable volume
- **Observability**: Braintrust (optional, default) or Langfuse

## Security Note

LinguaFlow uses server-side AI translation:
- Messages are sent to the backend in plaintext
- Voice audio is uploaded to protected attachment storage and its transcript is
  processed server-side; a temporary provider copy is uploaded to Gemini and
  deleted best-effort after each attempt
- The LLM receives plaintext for translation
- WebSocket connections use JWT authentication
- No true end-to-end encryption is implemented

This is intentional: server-side processing is required for AI translation.

## Gate 2 Evidence

- Architecture: [docs/gate2_architecture.md](docs/gate2_architecture.md)
- Evaluation: [eval/gate2_evidence.md](eval/gate2_evidence.md)
