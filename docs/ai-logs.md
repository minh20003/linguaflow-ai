# Deliverable #4: AI Logs & Observability

**Dự án:** LinguaFlow (P-217) · **Nhóm thực hiện:** 4U  
**Hạ tầng nhật ký & giám sát AI:** Braintrust / Langfuse Tracing + Instructor AI Usage Logging Hook.

---

## 1. Tổng quan Tracing & Logging AI Agent

LinguaFlow triển khai 2 hệ thống AI Logging & Tracing song song:

### 1.1. Braintrust / Langfuse Tracing (Cấu hình qua `OBSERVABILITY_PROVIDER`)
- **Tự động gắn Callback**: Tất cả các node đồ thị LangGraph (cả **Translation Agent** ở Pha 1 và **Assistant Agent** phát triển bổ sung ở pha sau này) tự động đính kèm callback handler thông qua `build_runnable_config()` (`src/agents/observability.py`).
- **Nội dung Trace**:
  - Từng câu prompt, context messages, input/output tokens.
  - Latency của từng lượt gọi LLM.
  - Phân định giữa Translation Agent và Assistant Agent Planner loops.
  - Trace chi tiết từng tool call (`search_old_messages`, `extract_actions`, `propose_calendar_event`, `recall_user_memory`).

### 1.2. Instructor AI Usage Logging Hook (Thiết lập tự động)
- Lưu vết toàn bộ prompt tương tác giữa lập trình viên / AI CLI trong quá trình phát triển dự án tại `.ai-log/session.jsonl`.
- Tự động nộp lên server chấm điểm của giảng viên via `git push` pre-push hook.

---

## 2. Cách kiểm tra AI Tracing trên Braintrust / Langfuse

```bash
# Trong file .env
OBSERVABILITY_PROVIDER=braintrust
BRAINTRUST_PROJECT=linguaflow
BRAINTRUST_API_KEY=sk-...
```

Khi chạy dịch thuật hoặc gọi Assistant Agent, toàn bộ trace được đẩy lên Braintrust Dashboard theo thời gian thực.
