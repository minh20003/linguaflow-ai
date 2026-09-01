# Deliverable #7: Pitch Deck (Slide Thuyết trình Demo Day)

**Dự án:** LinguaFlow (P-217) · **Nhóm thực hiện:** 4U  

---

## 1. Tệp Slide Thuyết trình

Tệp slide bài thuyết trình chuẩn 10 slides được lưu trữ tại:
- **Tệp Slide PowerPoint**: [`presentation/LinguaFlow_Pitch_Upgraded_v3.pptx`](../presentation/LinguaFlow_Pitch_Upgraded_v3.pptx)
- **Tài liệu Thuyết trình Chi tiết**: [`presentation/project_presentation.md`](../presentation/project_presentation.md)

---

## 2. Tóm tắt Cấu trúc 10 Slides

1. **Slide 1: Title (Tiêu đề)** — LinguaFlow: Realtime Multilingual Chat with Context-Aware AI Agent.
2. **Slide 2: Problem (Vấn đề)** — Rào cản ngôn ngữ trong làm việc nhóm toàn cầu; công cụ dịch truyền thống mất ngữ cảnh xưng hô, ngữ cảnh công việc và gây gián đoạn luồng chat.
3. **Slide 3: Solution (Giải pháp)** — AI Agent dịch thuật đa ngôn ngữ tự động trong luồng chat + Trợ lý AI cá nhân trích xuất cam kết công việc (bổ sung ở pha sau).
4. **Slide 4: Product Demo (Sản phẩm)** — Giao diện chat thời gian thực, bật/tắt song ngữ, tin nhắn thoại, thẻ đề xuất lịch hẹn chờ duyệt.
5. **Slide 5: Architecture (Kiến trúc)** — Đồ thị LangGraph, PostgreSQL + pgvector, WebSocket Gateway, Braintrust tracing.
6. **Slide 6: AI/LLM Approach (Cách tiếp cận AI)** — Two-tier language detection, context injection 3-5 tin nhắn, RAG `assistant_chunks` riêng cho Assistant Agent.
7. **Slide 7: Technical Highlights (Điểm nổi bật)** — Multi-provider fallback (Groq, Gemini, DeepSeek, Mistral), Human-in-the-Loop approval, Voice STT.
8. **Slide 8: Evaluation Evidence (Kết quả Đánh giá)** — Golden set 53+ samples, 100% pass rate (score >= 0.7), RAG Chunking recall@4 metrics.
9. **Slide 9: Challenges & Learnings (Thách thức & Bài học)** — Xử lý rò rỉ ngữ cảnh, đồng bộ WebSocket đa tab, kiểm soát chi phí token.
10. **Slide 10: Team & Roadmap (Đội ngũ & Kế hoạch)** — Nhóm 4U VinUni AI20K, roadmap phát triển thêm các tính năng nâng cao.
