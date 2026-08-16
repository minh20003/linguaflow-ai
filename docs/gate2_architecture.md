# LinguaFlow — Architecture Diagram (Gate 2)

**Dự án:** LinguaFlow (P-217) · **Mục đích:** Gate 2 Submission

## System Architecture

```mermaid
flowchart LR
    subgraph UI["👤 User Interface"]
        FE["LinguaFlow Web Chat<br/>Next.js + React"]
    end

    subgraph BE["⚙️ Backend & Realtime"]
        API["FastAPI + Uvicorn<br/>REST API + WebSocket Gateway<br/>JWT Authentication"]
        CHAT["Chat Service<br/>Translation Service"]
        CONN["Connection Manager"]
    end

    subgraph AGENT["🧠 AI Agent Core (LangGraph)"]
        DETECT["detect_language"]
        CONTEXT["build_context"]
        TRANSLATE["translate"]
        VALIDATE["validate_output"]
        FALLBACK["fallback_translate"]
        DETECT --> CONTEXT --> TRANSLATE --> VALIDATE
        VALIDATE -->|failure| FALLBACK
    end

    subgraph AI["🤖 LLM & Supporting Tools"]
        LLM["Configured LLM Provider<br/>Groq / DeepSeek / Gemini / OpenAI"]
        LANGDETECT["langdetect"]
        DEEPTRANS["deep-translator"]
        LANGFUSE["Langfuse"]
    end

    subgraph DATA["💾 Data Layer"]
        DB["SQLAlchemy Async ORM<br/>SQLite (dev) / PostgreSQL (prod)<br/>Alembic"]
    end

    UI -->|"WebSocket / REST"| API
    API --> CHAT
    API --> CONN
    CONN -->|"realtime events"| UI
    CHAT -->|"translation request"| AGENT
    AGENT -->|"prompt + context"| LLM
    LLM -->|"translation"| AGENT
    AGENT -->|"read recent messages"| DB
    CHAT -->|"persist messages / translations / feedback"| DB
    AGENT -.->|"tracing"| LANGFUSE
    AGENT -.->|"fallback"| DEEPTRANS
```

## Data Flow

1. User sends message from LinguaFlow web UI
2. FastAPI authenticates via JWT and persists the message
3. WebSocket delivers original message to sender immediately
4. TranslationService checks if recipient's preferred language differs from source
5. If translation needed, LangGraph Agent is invoked:
   - `detect_language`: local langdetect + LLM arbitration on conflict
   - `build_context`: reads recent messages from database
   - `translate`: calls configured LLM with prompt + context
   - `validate_output`: verifies output language
   - `fallback_translate`: uses deep-translator when LLM fails
6. Translation is persisted (async) and delivered to recipients
7. Langfuse records AI traces for observability

## Agent Nodes

| Node | Purpose |
|------|---------|
| `detect_language` | Two-tier detection: local langdetect + LLM arbitration |
| `build_context` | Reads recent messages from DB for conversation context |
| `translate` | Calls configured LLM with prompt + context |
| `validate_output` | Verifies output is in target language |
| `fallback_translate` | Uses deep-translator when LLM fails |
| `passthrough` | Returns original when source == target language |

## Supported LLM Providers

Provider-neutral adapter via LangChain with support for:
- **Groq**: `llama-3.3-70b-versatile`
- **DeepSeek**: `deepseek-chat`
- **Gemini**: `gemini-2.5-flash`
- **OpenAI**: `gpt-4o-mini`

## Deployment

| Component | Platform |
|-----------|----------|
| Frontend | Vercel |
| Backend + Agent | Railway (Docker) |
| Database | Railway PostgreSQL |
| Observability | Langfuse (optional) |

> Single backend instance required: ConnectionManager holds sockets in process memory.

## Security Notes

- JWT authentication for all API endpoints and WebSocket connections
- Backend receives plaintext messages for AI translation (server-side processing)
- No true end-to-end encryption (AI requires access to message content)
