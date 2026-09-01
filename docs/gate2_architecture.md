# LinguaFlow — Architecture Diagram (Gate 2 & Deliverables)

**Dự án:** LinguaFlow (P-217) · **Nhóm thực hiện:** 4U  
**Trạng thái:** Đã cập nhật đầy đủ cả **Translation Agent (Pha 1)** và **Assistant Agent (Phát triển bổ sung ở pha sau này)**.

> **Ghi chú quan trọng:** Để xem bộ 6 sơ đồ kiến trúc Mermaid hoàn chỉnh và thiết kế chi tiết nhất, vui lòng xem [`docs/architecture_diagram.md`](architecture_diagram.md) và [`ARCHITECTURE.md`](../ARCHITECTURE.md).

---

## 1. System Architecture Overview

```mermaid
flowchart LR
    subgraph UI["👤 User Interface"]
        FE["LinguaFlow Web Chat<br/>Next.js + React"]
    end

    subgraph BE["⚙️ Backend & Realtime Gateway"]
        API["FastAPI + Uvicorn<br/>REST API + WebSocket Gateway<br/>JWT Authentication"]
        CHAT["Chat Service<br/>Translation Service"]
        CONN["Connection Manager"]
    end

    subgraph AGENT1["🧠 Translation Agent (Pha 1)"]
        DETECT["detect_language"]
        CONTEXT["build_context"]
        TRANSLATE["translate"]
        VALIDATE["validate_output"]
        FALLBACK["fallback_translate"]
        DETECT --> CONTEXT --> TRANSLATE --> VALIDATE
        VALIDATE -->|failure| FALLBACK
    end

    subgraph AGENT2["📅 Assistant Agent (Phát triển ở pha sau)"]
        PLANNER["Planner Node"]
        EXECUTOR["Tool Executor"]
        RAG["RAG Search (assistant_chunks)"]
        PROPOSE["Action Proposal (HITL)"]
        PLANNER --> EXECUTOR --> RAG
        EXECUTOR --> PROPOSE
    end

    subgraph DATA["💾 Data Layer"]
        DB["PostgreSQL + pgvector<br/>Single DB for Messages, Embeddings & Assistant Proposals"]
    end

    subgraph AI["🤖 LLM & External Services"]
        LLM["LLM Providers<br/>Groq / DeepSeek / Gemini / OpenAI / Mistral"]
        GCAL["Google Calendar API"]
        TRACE["Braintrust / Langfuse"]
    end

    UI -->|"WebSocket / REST"| API
    API --> CHAT
    API --> CONN
    CONN -->|"realtime events"| UI
    CHAT -->|"translation request"| AGENT1
    API -->|"assistant request / background scan"| AGENT2
    AGENT1 --> LLM
    AGENT2 --> LLM
    AGENT1 --> DB
    AGENT2 --> DB
    PROPOSE -->|"Human approval required"| UI
    API -->|"Sync after approval"| GCAL
    AGENT1 -.-> TRACE
    AGENT2 -.-> TRACE
```

---

## 2. Tài liệu Tham chiếu Chi tiết
- [Tài liệu Kiến trúc Cột mốc 3 & Deliverable #3 (docs/architecture.md)](architecture.md)
- [Bộ 6 Sơ đồ Kiến trúc Mermaid Chuẩn (docs/architecture_diagram.md)](architecture_diagram.md)
- [Tài liệu Thiết kế Kỹ thuật Chi tiết (ARCHITECTURE.md)](../ARCHITECTURE.md)
