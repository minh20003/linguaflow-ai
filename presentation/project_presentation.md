# LinguaFlow (P-217)

**Tên đề tài:** AI Agent Dịch tin nhắn đa ngôn ngữ Real-time & Trợ lý Hội thoại Thông minh  
**Nhóm thực hiện:** 4U · **Chương trình:** VinUni AI20K Build Phase  
**Phiên bản:** 3.0 — cập nhật 01/09/2026  
**Bổ sung so với 2.0:** tin nhắn thoại & phiên âm, phạm vi đọc của trợ lý, đề xuất lịch fan-out cho cả nhóm, giao diện 14 ngôn ngữ, và định hướng thương mại hoá
**Link demo**: https://c3-lingua-flow-217.dquangminh2003.id.vn/

**Đội ngũ triển khai — nhóm 4U**

| Thành viên | Vai trò chính | Vai trò phụ |
|---|---|---|
| Nguyễn Thị Trà My | Trưởng nhóm / AI | Backend |
| Nguyễn Văn Hưởng | AI | Knowledge Base |
| Nguyễn Ngọc Thuận | Frontend | Tester |
| Đinh Quang Minh | Backend | Knowledge Base |

Bốn người làm song song trong 6 tuần trên các nhánh riêng. Mỗi người giữ thêm một vai phụ ở lĩnh vực của người khác — đó là lý do `docs/CONTRACT.md` tồn tại và luôn được sửa **trước** khi viết code: bốn người cùng chạm vào một schema thì tên trường phải chốt trước, không phải hoà giải sau.

---

## Mục lục

1. [Bài toán & Khảo sát Thị trường](#1-bài-toán--khảo-sát-thị-trường)
2. [Giải pháp Kỹ thuật — Kiến trúc Agent](#2-giải-pháp-kỹ-thuật--kiến-trúc-song-agent-dual-agent-architecture)
3. [Kỹ thuật Xử lý các Case khó](#3-kỹ-thuật-xử-lý-các-case-khó-advanced-edge-case-techniques)
4. [Hệ thống Chấm điểm & Đánh giá](#4-hệ-thống-chấm-điểm--đánh-giá-evaluation-framework)
5. [Kết quả thu được](#5-kết-quả-thu-được)
6. [Hướng tới người dùng thật](#6-hướng-tới-người-dùng-thật)

---

## 1. Bài toán & Khảo sát Thị trường

### 1.1. Vấn đề thực tế (Pain Points)

Trong các phòng chat làm việc đa ngôn ngữ (Đặc biệt là phòng chat ba bên: **Quản lý dự án (PM) ↔ Lập trình viên/Designer ↔ Khách hàng quốc tế**), rào cản ngôn ngữ gây giảm hiệu suất nghiêm trọng:

| Pain Point | Tác động thực tế |
|---|---|
| **Hiểu sai ngữ cảnh & Thuật ngữ** | Các từ viết tắt kỹ thuật (`API`, `DB`, `BE`, `FE`, `PR`, `deploy`, `hotfix`) nếu dịch rời rạc theo nghĩa đen sẽ bị sai lệch specification và gây hỏng sản phẩm. |
| **Trải nghiệm dịch đứt đoạn** | Dùng Google Translate/DeepL/ChatGPT buộc người dùng phải copy-paste ra ngoài app chat, gây mất tập trung và đứt luồng thảo luận. |
| **Bỏ sót Action Items & Deadline** | Trong các luồng chat dài, các cam kết, mốc deadline và lịch hẹn dễ bị trôi mất mà không có công cụ tự động trích xuất và nhắc nhở. |
| **Rủi ro Bảo mật & Quyền riêng tư (PII)** | Khi tích hợp AI vào chat nhóm, nguy cơ lộ thông tin cá nhân (email, SĐT, số tài khoản, mật khẩu) hoặc lộ nội dung thảo luận nội bộ cho bên thứ ba. |

### 1.2. Phân tích Thị trường & Khoảng trống (Market Gap Analysis)

```mermaid
graph LR
    subgraph Competitors["Công cụ hiện tại"]
        GT["Google Translate<br/>dịch nhanh, không nhớ ngữ cảnh"]
        DL["DeepL<br/>văn phong tốt, glossary tĩnh"]
        GPT["ChatGPT / Claude<br/>hiểu ngữ cảnh, không tối ưu chat real-time"]
    end
    
    GT --> Gap
    DL --> Gap
    GPT --> Gap

    Gap["Khoảng trống Thị trường (Market Gap)"]
    Gap --> P1["Tích hợp Real-time WebSocket<br/>ngay trong app chat"]
    Gap --> P2["Glossary thích ứng theo đối tượng đọc<br/>(Internal vs Client)"]
    Gap --> P3["Tự học thuật ngữ từ feedback<br/>(Human-in-the-loop Mining)"]
    Gap --> P4["Song Agent: Dịch real-time<br/>+ Trợ lý trích xuất Task/Lịch hẹn"]
```

---

## 2. Giải pháp Kỹ thuật — Kiến trúc Agent

LinguaFlow xây dựng kiến trúc Agent chạy song song trên cùng một hạ tầng (Auth, PostgreSQL + pgvector, WebSocket Gateway, Observability Tracing):

```mermaid
graph TB
    User([Người dùng Chat]) -->|WebSocket / REST| Gateway["FastAPI API Gateway & WS Manager"]
    
    subgraph DualAgent["Kiến trúc Song Agent (LangGraph)"]
        TA["Translation Agent<br/>(Dịch thuật Real-time, Streaming)"]
        AA["Assistant Agent<br/>(Trợ lý Thông minh, RAG & Tool Execution)"]
    end

    Gateway -->|"Mọi tin nhắn"| TA
    Gateway -->|"@assistant hoặc chat riêng"| AA

    TA --> DB[("PostgreSQL + pgvector")]
    AA --> DB
    AA --> Tools["External Tools<br/>(Google Calendar, Reminders, Memory RAG)"]
    
    Obs["Braintrust / Langfuse Observability"] -.-> DualAgent
```

### 2.1. Agent 1: Translation Agent (Luồng Dịch thuật Real-time)

- **Đặc điểm:** Chạy tự động cho mọi tin nhắn, độ trễ thấp (mục tiêu < 1.5s), streaming token qua WebSocket.
- **Quy trình LangGraph State Machine:**
  1. **Local Detect:** Kiểm tra ngôn ngữ cục bộ (`langdetect`) ~2ms.
  2. **LLM Arbitration:** Chỉ gọi LLM phân xử khi mâu thuẫn giữa khai báo và detect.
  3. **Context Injection:** Đọc 3-5 tin nhắn gần nhất để giữ đúng mạch hội thoại.
  4. **Audience-Aware Customization:** Tra cứu Glossary theo vị thế xưng hô và đối tượng đọc (`internal` vs `client`).
  5. **2-Level Fallback:** Nếu LLM lỗi/timeout ➔ Chuyển qua `deep-translator` ➔ Nếu vẫn lỗi ➔ Trả về bản gốc an toàn với flag `is_fallback = true`.

### 2.2. Agent 2: Assistant Agent (Trợ lý Thông minh & Quản lý Tác vụ)

- **Đặc điểm:** Kích hoạt theo yêu cầu (Chat riêng với Assistant hoặc gõ `@assistant` trong chat nhóm). Trả lời riêng tư (`visibility = 'private'`).
- **Quy trình xử lý Autonomous Planner:**
  1. **Consent Verification (ADR-30):** Kiểm tra quyền đọc hội thoại của người dùng trước khi nạp tin nhắn.
  2. **RAG Memory Retrieval:** Tìm kiếm tri thức và lịch sử hội thoại liên quan qua `pgvector`.
  3. **Task & Reminder Extraction:** Trích xuất hành động, thời hạn, người phụ trách từ nội dung chat.
  4. **Human-in-the-Loop Confirmation:** Hiển thị popup xác nhận trước khi ghi dữ liệu hoặc đồng bộ Google Calendar.

- **Phạm vi đọc do nơi hỏi quyết định, không do câu hỏi:**

| Hỏi ở đâu | Trợ lý đọc được gì |
|:---|:---|
| Chat riêng với trợ lý | **Mọi hội thoại** tài khoản là thành viên, kèm danh sách thành viên từng nhóm |
| `@assistant` trong một hội thoại | **Đúng hội thoại đó**, không gì khác |

---

## 3. Kỹ thuật Xử lý các Case khó

Trong quá trình phát triển, nhóm đã áp dụng các kỹ thuật chuyên sâu để giải quyết 5 nhóm bài toán khó (Edge Cases):

### Case 1: Tối ưu Độ trễ (Latency) & Chi phí gọi LLM
- **Bài toán:** Gọi LLM cho mọi tin nhắn gây tăng latency (2.6s/tin) và tốn kém token.
- **Kỹ thuật xử lý:** **Tách lọc ngôn ngữ 2 tầng (2-tier Language Detection)**.
  - Tầng 1: Chạy `langdetect` cục bộ (~2ms, 0đ chi phí). Nguồn và đích trùng nhau ➔ Trả về ngay không gọi LLM.
  - Tầng 2: Chỉ khi `langdetect` mâu thuẫn với thông tin người gửi mới gọi LLM phân xử.
- **Kết quả:** Giảm latency từ **2610ms xuống 1501ms** (~42.5%), tiết kiệm hơn 35% chi phí API.

### Case 2: Xử lý Ngữ cảnh & Thuật ngữ theo Đối tượng đọc (Audience Awareness)
- **Bài toán:** Từ "deploy" gửi cho Dev nội bộ nên giữ nguyên `deploy`, nhưng gửi cho Khách hàng nên dịch thành `triển khai`.
- **Kỹ thuật xử lý:** **Honorific & Audience Profile Fan-out**.
  - Hệ thống lưu trữ `honorific_profile` (`senior`, `peer`, `junior`, `client`).
  - Node `customize` trong LangGraph tra cứu bảng `glossary_entries` dựa theo cặp `(source_lang, target_lang, audience)`.

### Case 3: Lọc Nhiễu & Tự động Đề xuất Glossary từ Chỉnh sửa Người dùng
- **Bài toán:** Người dùng sửa bản dịch nhưng có thể sửa sai, sửa ngẫu nhiên hoặc gõ nhầm.
- **Kỹ thuật xử lý:** **Semantic Embedding Clustering & Multi-user Verification**.
  - Lưu các chỉnh sửa vào `correction_log` (khi người dùng bật consent).
  - Thuật toán Offline Mining thực hiện gom cụm Vector Embeddings với độ tương đồng Cosine $\ge 0.85$.
  - **Điều kiện lọc khắt khe:** Chỉ tạo `GlossaryProposal` khi thỏa mãn đồng thời: `occurrence_count >= 3` VÀ `distinct_user_count >= 2` (phải có ít nhất 2 người khác nhau cùng sửa giống nhau).
  - Admin duyệt trên Bảng điều khiển (`/admin` GlossaryPanel) trước khi thành `GlossaryEntry` chính thức.

### Case 4: An toàn Quyền riêng tư & Bảo vệ PII (Guardrails & Privacy)
- **Bài toán:** Tin nhắn chứa thông tin nhạy cảm (mật khẩu, STK, email) hoặc dữ liệu riêng tư trong hội thoại nhóm.
- **Kỹ thuật xử lý:**
  - **Assistant Consent Scope:** Bắt buộc người dùng cấp quyền đọc hội thoại mới cho phép Assistant truy cập RAG context.
  - **Privacy-Preserving Telemetry:** Mọi log tracing (Braintrust/Langfuse) và log lỗi hệ thống đều được làm sạch, mask PII, chỉ ghi nhận metadata (token count, latency, error code) không lưu trữ văn bản thô của người dùng.

### Case 5: Đảm bảo Hệ thống Không Bao giờ Cắt đứt Hội thoại (Zero-Crash Resilience)
- **Bài toán:** LLM Provider (Groq/DeepSeek) bị rate-limit, timeout hoặc ngắt kết nối.
- **Kỹ thuật xử lý:** **2-Level Graceful Fallback Architecture**.
  - Tầng 1: Tự động chuyển hướng sang Provider dự phòng (`deep-translator`).
  - Tầng 2: Nếu cả tầng dự phòng thất bại ➔ Trả về nguyên bản tin nhắn ban đầu kèm flag `is_fallback = true` và ghi log telemetry tại điểm thoát. Chat vẫy chạy liên tục, không bao giờ vỡ UI.

---

## 4. Hệ thống Chấm điểm & Đánh giá (Evaluation Framework)

Dự án LinguaFlow áp dụng hệ thống đánh giá đa chiều kết hợp giữa **Tự động hóa (Automated Benchmarking)**, **LLM-as-a-Judge** và **Phản hồi Người dùng thật (Human Feedback)**:

```mermaid
graph TD
    subgraph EvalInputs["Nguồn Đánh giá"]
        GS["Golden Set Test Suite<br/>(62 tình huống chuẩn)"]
        TF["User Feedback<br/>(Upvote / Downvote / Correction)"]
        TL["Telemetry Logs<br/>(translation_attempts 5 exit points)"]
    end

    subgraph MetricsEngine["Bộ chỉ số Đánh giá (eval/run_eval.py)"]
        M1["BLEU / ChrF Score<br/>(Đo độ chính xác từ vựng)"]
        M2["LLM-as-a-Judge<br/>(Đo Fidelity & Completeness)"]
        M3["Latency & Cost Metrics<br/>(P50/P90/P99 Response Time)"]
        M4["User Upvote Rate<br/>(% Hài lòng thực tế)"]
    end

    GS --> M1 & M2
    TF --> M4
    TL --> M3

    MetricsEngine --> Dashboard["Admin Analytics Dashboard & QA Report"]
```

### 4.1. Bộ Đánh giá Golden Set (`eval/golden_set.jsonl`)
- Gồm **62+ kịch bản kiểm thử có nhãn**, bao gồm:
  - Dịch thuật ngữ IT / Software Outsourcing.
  - Dịch câu ngắn, từ lóng, viết tắt (`FE`, `BE`, `PR`, `LGTM`).
  - Khả năng xử lý xưng hô theo vị thế (`senior`, `client`).
  - Xử lý tin nhắn chứa ký tự đặc biệt, đoạn code.

### 4.2. Bộ Chỉ số Đánh giá (Evaluation Metrics)

1. **Điểm BLEU / ChrF:** So sánh bản dịch đầu ra với bản dịch chuẩn (Reference Translation).
2. **Điểm Fidelity & Completeness (LLM-as-a-Judge):** Đánh giá xem bản dịch có giữ nguyên ý nghĩa cốt lõi và không bỏ sót các thông tin kỹ thuật quan trọng hay không (thang điểm 1 - 5).
3. **Chỉ số Telemetry (5 Exit Points Tracking):** Theo dõi tỷ lệ thành công của LLM chính, tỷ lệ chuyển qua Fallback, và tỷ lệ trả về tin nhắn gốc.
4. **User Upvote/Downvote Ratio:** Thống kê từ `POST /api/v1/translations/{id}/feedback` và `GET /api/v1/admin/feedback` để đo tỷ lệ hài lòng thực tế của người dùng.

---

## 5. Kết quả thu được

### 5.1. Ma trận tính năng đã nghiệm thu

| Mã | Tính năng | Trạng thái | Nơi kiểm chứng |
|:---:|:---|:---:|:---|
| **F-01** | Xác thực JWT, OTP đăng ký, đặt ngôn ngữ dịch & ngôn ngữ giao diện | ✓ | `src/api/routes.py`, `tests/test_api/test_auth.py` (23 test) |
| **F-02** | Chat real-time 1-1 và nhóm qua WebSocket | ✓ | `src/api/websocket.py`, `src/services/connection_manager.py` |
| **F-03** | Dịch có ngữ cảnh, phát hiện ngôn ngữ hai tầng, fallback 2 mức | ✓ | `src/agents/graph.py`, `src/agents/nodes/translation.py` |
| **F-04** | Bật/tắt bản gốc — bản dịch trên từng tin nhắn | ✓ | `frontend/src/features/chat/components/MessageBubble.tsx` |
| **F-05** | Human-in-the-loop: upvote/downvote và sửa bản dịch | ✓ | `src/services/correction_log.py` |
| **F-06** | Guardrail đầu vào/đầu ra, giới hạn độ dài, chống giả mạo thẻ ngữ cảnh | ✓ | `src/agents/guardrails.py`, `docs/GUARDRAILS.md` |
| **F-07** | Khai phá thuật ngữ tự động + bảng duyệt của quản trị | ✓ | `src/services/glossary_mining.py` |
| **F-08** | Assistant Agent: RAG riêng, trích việc, lịch cá nhân, đồng bộ Google Calendar | ✓ | `src/agents/assistant/`, `src/services/calendar.py` |
| **F-09** | Tin nhắn thoại: ghi âm → phiên âm (Gemini STT) → dịch → trích việc | ✓ | `src/services/voice_transcription.py`, `src/services/audio_conversion.py` |
| **F-10** | Gọi thoại/video 1-1 qua WebRTC | ✓ | `src/services/rtc.py` |
| **F-11** | Giao diện 14 ngôn ngữ theo cài đặt tài khoản | ✓ | `frontend/src/features/chat/i18n.ts` (576 khóa), `scripts/check_ui_keys.py` |

### 5.2. Kiểm thử tự động

| Bộ | Số lượng | Kết quả |
|:---|:---:|:---|
| Backend (`pytest tests/`) | **1236** | toàn bộ đạt, ~22 phút |
| Frontend (`vitest`) | **53** | toàn bộ đạt |
| Kiểu tĩnh (`tsc --noEmit`) | — | 0 lỗi |
| Lint (`ruff`, `eslint`) | — | 0 lỗi |
| Migration | 38 revision | một `head` duy nhất |

### 5.3. Kết quả đánh giá chất lượng dịch — kể cả phần chưa đạt

Chạy trên `eval/golden_set.jsonl` (62 mẫu), chấm bằng LLM-as-judge (`mistral-medium` chấm `gemini-3.7-flash`):

| Chỉ số | Mục tiêu | Thực tế | |
|:---|:---:|:---:|:---|
| Tỷ lệ đạt (≥ 0.7) | > 80% | **100%** | đạt |
| Điểm trung bình | > 0.80 | **0.912** | đạt |
| chrF++ / BLEU / TER | — | 65.6 / 52.2 / 56.9 | đạt |
| Tuân thủ glossary | 100% | **100%** | đạt |
| Số lần fallback | 0 | **0** | đạt |
| **Độ trễ trung bình** | < 2000ms | **2324ms** | **chưa đạt** |
| **Độ trễ p95** | < 5000ms | **4608ms** | **đạt** |
| **Đúng ngôn ngữ đích** | 100% | **96,6%** | **chưa đạt** |

### 5.4. Tính khả thi — vì sao sản phẩm này sống được

**Một câu:** thứ đắt nhất trong làm việc xuyên ngôn ngữ không phải là một câu dịch sai, mà là **một lời hứa rơi mất giữa hai thứ tiếng**. Google Translate và Zoom dịch câu. Không ai nhặt lời hứa lên.

#### Một cảnh

Nhóm dự án Việt Nam nhắn với khách Nhật, 4 giờ chiều thứ Năm:

> **Khách:** 来週の金曜午後3時でいかがでしょうか。
> **PM:** Ok chốt nhé, chiều thứ Sáu tuần sau 3 giờ.

Hai người vừa hẹn nhau. Với mọi công cụ dịch hiện có, **đến đây là hết**: hai câu được dịch, cuộc trò chuyện trôi tiếp, và cuộc hẹn nằm lại trong lịch sử chat cho tới khi ai đó nhớ ra.

Với LinguaFlow, cùng lúc đó:

- Cuộc hẹn thành **một mục lịch trên máy của từng người**, đúng 15:00 thứ Sáu tuần sau, theo múi giờ **người vừa nói ra nó** — không phải giờ máy chủ, không phải giờ người đọc.
- Người Việt thấy *"Gặp ở quán cà phê"*, khách Nhật thấy bản của họ. Cùng một cuộc hẹn, hai ngôn ngữ.
- **Chưa ai bị ghi gì vào lịch cả.** Mỗi người thấy một thẻ hỏi, tự duyệt hoặc từ chối, sửa được giờ và tiêu đề trước khi đồng ý. Một người duyệt không đẩy lịch sang máy người kia.

Khoảng cách giữa hai đoạn trên chính là sản phẩm.

#### Vì sao công cụ miễn phí không lấp được khoảng đó

Không phải vì máy dịch của họ kém — DeepL và GPT dịch **từng câu** rất tốt, có khi tốt hơn chúng tôi. Vấn đề là **câu không phải là đơn vị đúng** khi người ta nhắn tin cho nhau. Ba chỗ hỏng, đều tự kiểm chứng được:

**Tiếng Việt lược chủ ngữ.**

> — Anh gửi bản hợp đồng cho khách chưa?
> — Gửi rồi nhé.

Câu sau không có chủ ngữ, không thì, không tân ngữ. Dịch riêng lẻ thì buộc phải đoán, và **mất luôn gửi cái gì, cho ai**. LinguaFlow đọc 3–5 tin trước khi dịch.

**Xưng hô là thông tin, tiếng Anh làm phẳng nó.** *Anh, em, chị, bác* đều thành "you". Dịch ngược lại là chọn ngẫu nhiên — gọi "em" một khách hàng lớn tuổi không phải lỗi ngữ pháp mà là **lỗi xã giao**, và trong hội thoại với khách nó đắt hơn nhiều một câu dịch vụng.

**Một thuật ngữ, hai bản.** Với đồng nghiệp là *"con Jenkins nó đỏ rồi"*; với khách phải là *"pipeline CI hiện đang lỗi"*. Glossary tĩnh chỉ có một đáp án cho mỗi từ.

#### Vì sao các ông lớn chưa nuốt mất

Nói thẳng: **họ làm được**. Lợi thế hiện nay là *chưa ai làm*, không phải *khó làm*. Nhưng có ba lý do khoảng cách này không tự đóng trong một sớm một chiều:

1. **Sai bề mặt.** Zoom AI Companion sống trong phòng họp và tắt khi phòng đóng. Cuộc họp chỉ để chốt; *"gửi báo giá trước thứ Sáu nhé"* nằm trong chat giữa các cuộc họp — nơi họ không nhìn thấy.
2. **Sai động cơ.** Một tính năng miễn phí đi kèm được tối ưu để **trông thông minh**. Ở đây câu hỏi của người mua là *"AI đặt sai lịch thì ai chịu?"*, nên phải tối ưu để **không sai**: không có múi giờ đáng tin thì hệ thống **từ chối** đặt lịch và hỏi lại, thay vì đặt lệch giờ mà không báo; và không có gì lên lịch mà chưa qua tay người duyệt.
3. **Dữ liệu không sao chép được.** Glossary theo đối tượng đọc dày lên từ chính những lần nhân viên doanh nghiệp sửa bản dịch. Đối thủ copy được tính năng, không copy được ba tháng chỉnh sửa của khách hàng bạn.

#### Con số

Mô hình chỉ sống nếu **mỗi cuộc họp xử lý xong vẫn còn lãi**:

| | |
|---|---|
| Giá đề xuất | **$1,50** / cuộc họp hoàn tất |
| Chi phí thực / cuộc họp | **$0,41** |
| Biên gộp | **72,65%** |
| Ngưỡng hoà vốn | tỷ lệ tự xử lý ≥ **71,63%** — đo được **82%** |

Không cần giá enterprise mới sống. Đây là thứ quyết định sản phẩm tồn tại được ở phân khúc 20–200 nhân sự, chứ không chỉ ở doanh nghiệp lớn.

#### Bốn chỗ lập luận trên có thể sụp

1. **Nếu Zoom/Teams ship action item theo từng người kèm bước duyệt**, khoảng cách đóng nhanh. Thứ giữ được lâu là dữ liệu chỉnh sửa tích luỹ, không phải tính năng.
2. **96,6% đúng ngôn ngữ đích** — sai 1 trên 30 tin. Đó là chính lời hứa cốt lõi, hỏng trước khi kịp nói tới lịch với nhắc việc.
3. **Chỉ chạy được một bản sao** (ADR-18): vừa là trần công suất, vừa là điểm chết đơn lẻ.
4. **82% tự xử lý đến từ bộ eval, chưa từ người dùng.** Dưới 71,63% là hết lãi lành mạnh — nên đây là số phải **đo lại đầu tiên**, không phải số để trích dẫn tiếp.

### 5.5. Phiên bản triển khai

| Thành phần | Nơi chạy |
|:---|:---|
| Backend + Agent | Ubuntu VPS, container GHCR dựng sẵn, **đúng một bản sao** |
| Cơ sở dữ liệu | `pgvector/pgvector:pg16` trên cùng VPS, volume bền vững |
| Frontend | Ubuntu VPS, container GHCR sau Caddy |
| Quan sát | Braintrust (mặc định) hoặc Langfuse, đổi bằng biến môi trường |

---

## 6. Định hướng tương lai tới người dùng thật

### 6.1. Định vị: bán kết quả, không bán phần mềm

| | Khung A — Phần mềm | **Khung B — Thay thế công việc (đã chọn)** |
|:---|:---|:---|
| Cách nói | "Phần mềm trợ lý AI dịch họp và ghi biên bản" | "Đảm bảo 100% cuộc họp đa quốc gia được dịch chuẩn, biên bản & task giao đúng hạn" |
| Người quyết chi | IT Director | **COO / Head of Operations** |
| Lấy từ ngân sách | SaaS | **Nhân sự / Vận hành** |
| Bị so với | Zoom AI Companion ($0), Teams Premium ($10/user) | Thuê phiên dịch part-time ($600–1.000/tháng) |
| Phản đối lớn nhất | "Đã có Zoom/Teams miễn phí rồi" | "AI dịch sai gây thiệt hại hợp đồng thì ai chịu?" |

Lý do chọn B: ngân sách vận hành lớn và linh hoạt hơn ngân sách SaaS, vốn bị đọ giá trực tiếp với một sản phẩm giá $0 tích hợp sẵn.

### 6.2. Đơn vị tính tiền: một "Completed Job"

Mô hình đề xuất là **Outcome-based** (Attribution 8/10 × Autonomy cao), giá $1,50/completed meeting, với ngưỡng hòa vốn:

| Containment | Cost/Completed Job | Gross Margin | |
|:---:|:---:|:---:|:---|
| 60,0% | $0,6240 | 58,4% | cảnh báo |
| **71,63%** | $0,6000 | **60,0%** | ngưỡng hòa vốn |
| **82,0%** (đo thực) | **$0,4102** | **72,65%** | an toàn |

**con số 82% đó đến từ eval, chưa phải từ người dùng thật.** Việc đầu tiên khi có người dùng là đo lại containment thật và đối chiếu với ngưỡng 71,63% — dưới ngưỡng đó thì mô hình giá không còn lãi lành mạnh.

### 6.3. Kênh 90 ngày đầu: Partner-Led

Kênh chốt là **Partner-Led** qua liên minh tư vấn chuyển đổi số & IT Outsourcing (FPT Digital, Rikkei Soft, VNITO Alliance), chia sẻ 25% doanh thu. Bề mặt tích hợp mục tiêu: **Google Meet Chrome Extension** và **Zoom App Bot**, xuất biên bản & action item thẳng vào Slack/Notion của doanh nghiệp.

Khoảng cách kỹ thuật giữa bản hiện tại và bề mặt đó là rõ ràng: LinguaFlow hôm nay là một ứng dụng chat độc lập; để vào được cuộc họp Meet/Zoom cần một lớp bot tham gia phòng họp và nhận luồng audio — hạ tầng phiên âm và trích việc thì đã sẵn sàng, phần thiếu là đường vào.

### 6.4. Nâng cấp hệ thống hiện có

- **Đồng bộ hai chiều Google Calendar** đã có một chiều (đẩy lên) và pull định kỳ 300s; cần webhook để sự kiện đổi bên Google phản ánh ngược lại tức thì.
- **Ranh giới dữ liệu Admin/User**: quản trị xem chi phí, token, duyệt thuật ngữ — **không bao giờ đọc nội dung chat thô**. `message_visibility.public_only()` đã là nền cho việc này.
- **Bảng điều khiển chất lượng**: trực quan hóa xu hướng chrF++/BLEU, tỷ lệ upvote, chi phí token theo ngày và theo model, hiệu suất đề xuất glossary.
- **Mở rộng grammar thời gian**: hiện đã hiểu "ngày kia", "thứ 6 tuần sau", "6 giờ rưỡi", "3pm"; chưa hiểu mốc chỉ có giờ mà không có ngày, và chưa hiểu tiếng Việt không dấu.
