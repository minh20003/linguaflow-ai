# Deliverable #8: Development Journal (Nhật ký Phát triển)

**Dự án:** LinguaFlow (P-217) · **Nhóm thực hiện:** 4U  

Tài liệu nhật ký chi tiết quá trình phát triển 6 tuần của nhóm 4U được ghi nhận liên tục tại tệp gốc [`JOURNAL.md`](../JOURNAL.md).

---

## Tóm tắt Tiến trình Phát triển Theo Pha

### Pha 1: Hạ tầng & Translation Agent Core
- Khởi tạo repo, cấu hình CI/CD, thiết lập AI Usage Logging hooks.
- Xây dựng 6 sơ đồ kiến trúc chuẩn (Gate 2).
- Hiện thực hóa LLM Factory đa provider (Groq, DeepSeek, Gemini, Mistral, OpenAI).
- Xây dựng Translation Agent qua LangGraph state machine với 2-tier language detection và fallback chain.
- Triển khai PostgreSQL + `pgvector` thay thế SQLite cho toàn bộ các môi trường.

### Pha 2: Assistant Agent & Tính năng Nâng cao (Phát triển bổ sung ở pha sau này)
- Xây dựng Assistant Agent đồ thị riêng với mô hình Planner-Executor và cơ chế Human-in-the-Loop approval (ADR-30, ADR-37).
- Thêm kho RAG riêng `assistant_chunks` và kho `assistant_user_memory` cho trợ lý cá nhân.
- Tích hợp trích xuất cam kết/lịch hẹn tự động từ lịch sử chat, hỗ trợ nhắc nhở và hộp nhiệm vụ cá nhân (Task Inbox).
- Tích hợp đồng bộ 2 chiều với Google Calendar API (ADR-35).
- Thêm hỗ trợ tin nhắn thoại (Voice Messages) với Gemini 3.5 Transcribe.
- Mở rộng hệ thống đánh giá Evaluation Harness hỗ trợ cả chỉ số Sweep truy hồi (RAG & Chunk Recall@4).

Chi tiết toàn bộ nhật ký theo ngày: xem [`JOURNAL.md`](../JOURNAL.md).
