# LinguaFlow

Realtime multilingual chat with context-aware AI translation. Users chat in their preferred language while the system automatically translates messages between participants.

## Live Demo

| | |
|---|---|
| App | https://linguaflow-4-u3.vercel.app |
| API health | https://linguaflow-api-production.up.railway.app/health |

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
- Admin translation statistics
- Multilingual interface

## How It Works

```
User → WebSocket → FastAPI → Translation Service → LangGraph Agent → LLM
                                                                      ↓
                                      Realtime translated message ← User
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
- SQLite (development)
- PostgreSQL (production)
- Alembic migrations

### Observability
- Braintrust (optional, default), or Langfuse — set `OBSERVABILITY_PROVIDER`

## Prerequisites

- Python 3.11+
- Node.js 20+
- npm

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

### Database

```env
# Development (SQLite — default)
DATABASE_URL=sqlite+aiosqlite:///./data/app.db

# Production (PostgreSQL)
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
├── frontend/              # Next.js frontend
│   └── package.json
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
- **Frontend**: Vercel (root directory: `frontend/`)
- **Backend**: Railway with Docker
- **Database**: Railway PostgreSQL
- **Observability**: Braintrust (optional, default) or Langfuse

## Security Note

LinguaFlow uses server-side AI translation:
- Messages are sent to the backend in plaintext
- The LLM receives plaintext for translation
- WebSocket connections use JWT authentication
- No true end-to-end encryption is implemented

This is intentional: server-side processing is required for AI translation.

## Gate 2 Evidence

- Architecture: [docs/gate2_architecture.md](docs/gate2_architecture.md)
- Evaluation: [eval/gate2_evidence.md](eval/gate2_evidence.md)
