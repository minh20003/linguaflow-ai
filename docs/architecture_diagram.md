# SƠ ĐỒ KIẾN TRÚC HỆ THỐNG

**Dự án:** LinguaFlow (P-217) · **Nhóm thực hiện:** 4U
**Phiên bản:** 1.0 · **Ngày cập nhật:** 10/08/2026 · **Trạng thái:** Đang áp dụng

Tài liệu này chứa các sơ đồ kiến trúc dưới dạng Mermaid. Mô tả thành phần và căn cứ lựa chọn thiết kế: xem [`ARCHITECTURE.md`](../ARCHITECTURE.md).

| Mục | Sơ đồ | Phạm vi mô tả |
|---|---|---|
| §1 | System Overview | Thành phần hệ thống và quan hệ giữa các tầng |
| §2 | Agent Flow | Luồng xử lý bên trong AI Agent |
| §3 | Data Flow | Luồng dữ liệu giữa các tiến trình và kho dữ liệu |
| §4 | ER Diagram | Cấu trúc cơ sở dữ liệu |
| §5 | Sequence Diagram | Trình tự tương tác giữa các tầng theo thời gian |
| §6 | Use Case Diagram | Chức năng hệ thống theo góc nhìn người dùng |

---

## 1. System Overview

```mermaid
graph TB
    User([User]) -->|WebSocket| FE[Frontend<br/>React Chat UI]
    FE -->|WS: send/receive message| BE[Backend<br/>FastAPI + WebSocket Gateway]
    FE -->|REST: login, set language, feedback| BE

    BE --> Agent[AI Agent<br/>LangGraph]
    Agent -->|prompt + context| LLM[LLM Provider<br/>Groq / DeepSeek / Gemini / OpenAI]
    Agent -->|read last 3-5 messages| DB[(SQLite dev<br/>PostgreSQL prod)]
    BE -->|persist message + translation + feedback| DB

    Monitor[Langfuse<br/>latency/token monitoring] -.-> Agent
```

Hệ thống sử dụng một nguồn dữ liệu duy nhất (`DB`), đảm nhiệm đồng thời hai vai trò: lưu trữ lịch sử hội thoại dài hạn và cung cấp ngữ cảnh cho Agent. Phạm vi MVP không sử dụng Vector Store riêng (xem ADR-01 trong [`ARCHITECTURE.md`](../ARCHITECTURE.md)).

## 2. Agent Flow

```mermaid
graph TD
    START([Agent nhận tin nhắn cần dịch]) --> TooShort{Quá ngắn hoặc<br/>không có chữ cái?}
    TooShort -->|Có| UseTemp[Giữ giá trị tạm<br/>= preferred_language người gửi]
    TooShort -->|Không| Local[langdetect cục bộ<br/>~2ms, không gọi API]
    Local --> Agree{Trùng giá trị tạm?}
    Agree -->|Có| UseLocal[Dùng kết quả langdetect]
    Agree -->|Không / thất bại| LLMDetect[LLM detect phân xử<br/>~1300ms]

    UseTemp --> SameLang
    UseLocal --> SameLang
    LLMDetect --> SameLang

    SameLang{Ngôn ngữ nguồn = đích?}
    SameLang -->|Có| ReturnOriginal[Trả về nguyên bản]
    SameLang -->|Không| BuildContext[Đọc 3-5 tin gần nhất<br/>từ bảng messages]
    BuildContext --> Prompt[Tạo prompt: text + context + target_lang]
    Prompt --> CallLLM[Gọi LLM — streaming]
    CallLLM --> Valid{Bản dịch hợp lệ?}
    Valid -->|Không / timeout| FallbackProvider[Provider dự phòng<br/>deep-translator, ADR-07]
    Valid -->|Có| ReturnTranslated[Trả về bản dịch]

    FallbackProvider --> FallbackOk{Dự phòng dịch được?}
    FallbackOk -->|Có| ReturnFallback[Trả bản dịch dự phòng<br/>is_fallback = true]
    FallbackOk -->|Không| ReturnOriginalOnError[Trả về nguyên bản<br/>is_fallback = true]

    ReturnOriginal --> Deliver([Gửi kết quả tới người nhận])
    ReturnFallback --> Deliver
    ReturnOriginalOnError --> Deliver
    ReturnTranslated --> Deliver

    ReturnTranslated -.async, không chặn response.-> Persist[(Lưu translation_results)]

    Deliver --> HasEdit{Người dùng sửa bản dịch?}
    HasEdit -->|Không| END([Kết thúc])
    HasEdit -->|Có| Correction[Ghi feedbacks]
    Correction --> END
```

**Đặc điểm kiến trúc của Agent Flow:**

1. Hệ thống không sử dụng Vector Store riêng; bước "Đọc 3-5 tin gần nhất" truy vấn trực tiếp bảng `messages`, do ngữ cảnh là cửa sổ trượt theo thời gian (ADR-01).
2. Bước xác định ngôn ngữ nguồn sử dụng chiến lược hai tầng: `langdetect` cục bộ trước, chỉ gọi LLM phân xử khi có mâu thuẫn (ADR-11).
3. Nhánh fallback xử lý theo cơ chế hai tầng: khi LLM lỗi hoặc bản dịch không hợp lệ, Agent gọi provider dự phòng `deep-translator` (ADR-07); nếu provider dự phòng cũng thất bại thì trả về nguyên bản kèm `is_fallback = true`.
4. Bước "Bản dịch hợp lệ?" bao gồm cả kiểm tra ngôn ngữ đầu ra bằng `langdetect` cục bộ, không chỉ kiểm tra độ dài (ADR-13). Ngoài ra hai bước không vẽ trong sơ đồ vì không rẽ nhánh: giới hạn kích thước `original_text` và kiểm tra dạng `target_language` chạy trước khi tạo prompt, còn từng dòng ngữ cảnh được làm sạch bên trong bước "Tạo prompt" (ADR-12). Chi tiết: `ARCHITECTURE.md` §5.2.

**Chi phí mỗi tin nhắn theo nhánh:**

| Nhánh | Số lần gọi LLM | Latency đo được (Groq) |
|---|---|---|
| Quá ngắn hoặc chỉ emoji | 0 | ~0ms |
| langdetect trùng, nguồn = đích | 0 | ~2ms |
| langdetect trùng, cần dịch | 1 | ~1501ms |
| langdetect mâu thuẫn, cần dịch | 2 | ~2800ms |
| LLM lỗi, provider dự phòng dịch thay | 1 (thất bại) | phụ thuộc mạng, giới hạn bởi `FALLBACK_TRANSLATOR_TIMEOUT_SECONDS` |

## 3. Data Flow

```mermaid
graph LR
    E1[User] -->|1. Chat message| P1((P1: Receive Message<br/>WebSocket))
    P1 -->|2. Broadcast tin gốc ngay lập tức| E1
    P1 -->|3. Message data| P2((P2: Translation Agent<br/>LangGraph))

    P2 -->|4. Query 3-5 recent messages| DB[(SQLite dev / PostgreSQL prod)]
    P2 -->|5. Translation request + prompt| E2[LLM Provider API]
    E2 -->|6. Translation stream| P2

    P2 -->|7. Translated message| E1
    P2 -.8. Async persist.-> P3((P3: Store Data<br/>Background Worker))
    P3 -->|9. Save translation_results| DB

    E1 -->|10. Submit correction| P4((P4: Handle Feedback<br/>REST API))
    P4 -->|11. Save feedbacks| DB
    P4 -.log metrics.-> Monitor[Langfuse]
```

**Ghi chú:** chỉ bước lưu bản dịch (bước 9) được thực hiện bất đồng bộ. Tin nhắn gốc được lưu đồng bộ trước khi phát tới các client, do các bước sau yêu cầu `message_id`. Trình tự chi tiết bao gồm cơ chế streaming: xem §5.

## 4. ER Diagram

> Convention theo code thật (`src/database/models.py`): tên bảng **thường, số nhiều**, PK luôn tên `id`, khóa ngoại `<entity>_id`.

```mermaid
erDiagram
    users ||--o{ conversation_members : joins
    users ||--o{ messages : sends
    users ||--o{ feedbacks : gives
    conversations ||--o{ conversation_members : has
    conversations ||--o{ messages : contains
    messages ||--o{ translation_results : translated
    translation_results ||--o{ feedbacks : receives

    users {
        string id PK
        string email UK
        string password_hash
        string role "member | admin — quyền hệ thống"
        string preferred_language "ngôn ngữ muốn ĐỌC"
        datetime created_at
    }
    conversations {
        string id PK
        string title
        datetime created_at
    }
    conversation_members {
        string id PK
        string conversation_id FK
        string user_id FK
        string role "vai trò trong hội thoại"
        datetime joined_at
    }
    messages {
        string id PK
        string conversation_id FK
        string sender_id FK
        text original_text
        string source_language "tạm = preferred_language người gửi, detect ghi đè"
        datetime created_at
    }
    translation_results {
        string id PK
        string message_id FK
        string target_language
        text translated_text
        string model
        int latency_ms
        datetime created_at
    }
    feedbacks {
        string id PK
        string translation_id FK
        string user_id FK
        int rating
        text correction
        datetime created_at
    }
```

**Ghi chú triển khai:**

1. Tại thời điểm cập nhật tài liệu, chỉ bảng `users` đã được hiện thực hoá (`src/database/models.py`). Các bảng còn lại khi tạo phải tuân thủ đúng tên bảng và kiểu dữ liệu quy định tại đây.
2. Hệ thống không có bảng riêng lưu ngữ cảnh. Ngữ cảnh được truy vấn trực tiếp từ bảng `messages` (xem §2).
3. Cột `confidence` đã được loại khỏi `translation_results` do không có bước nào trong Agent Flow sinh ra giá trị này. Cột sẽ được bổ sung khi hệ thống có node đánh giá độ tin cậy.
4. Hai cột `role` có ngữ nghĩa khác nhau: `users.role` là quyền ở cấp hệ thống; `conversation_members.role` là vai trò trong một cuộc hội thoại cụ thể.

## 5. Sequence Diagram

**SD-01 — Dịch tin nhắn real-time trong hội thoại 1-1**

Sơ đồ dưới đây mô tả chi tiết trình tự tương tác giữa các thành phần trong luồng dịch tin nhắn thời gian thực giữa hai người dùng khác ngôn ngữ.

```mermaid
sequenceDiagram
    actor Sender
    participant SenderUI as Sender Web UI
    participant WS as WebSocket Gateway
    participant Chat as Chat Service
    participant DB as Database
    participant Agent as Translation Agent (LangGraph)
    participant LLM as LLM Provider API
    participant ReceiverUI as Receiver Web UI
    actor Receiver

    note over Sender,Receiver: Thiết lập kết nối
    SenderUI->>WS: Connect(JWT)
    WS-->>SenderUI: Connection accepted
    ReceiverUI->>WS: Connect(JWT)
    WS-->>ReceiverUI: Connection accepted

    Sender->>SenderUI: Nhập và gửi tin nhắn
    SenderUI->>WS: send_message(conversation_id, text)
    WS->>Chat: Handle incoming message
    Chat->>Chat: Validate sender membership
    Chat->>DB: Save message (source_language = preferred_language người gửi, tạm)
    DB-->>Chat: message_id
    Chat-->>WS: Message accepted
    WS-->>SenderUI: message_created(message_id)

    Chat->>DB: Get DISTINCT preferred_language của thành viên
    DB-->>Chat: danh sách target_language
    Chat->>Agent: process_message(message_id, original_text, conversation_id, source_language, target_language)
    Agent->>Agent: Detect source_language
    opt source_language detect khác giá trị tạm
        Agent->>DB: UPDATE messages.source_language
    end

    alt source_language == target_language
        Agent-->>Chat: translation_required = false
        Chat->>WS: Deliver original message
        WS-->>ReceiverUI: message_received(message_id, original_text)
        ReceiverUI->>Receiver: Hiển thị tin nhắn gốc
    else source_language != target_language
        Chat->>WS: translation_status = "streaming"
        WS-->>SenderUI: message_received(message_id, original_text, translation_status="streaming")
        WS-->>ReceiverUI: message_received(message_id, original_text, translation_status="streaming")

        Agent->>DB: Load conversation context (3-5 tin gần nhất)
        DB-->>Agent: context_messages
        Agent->>Agent: Build prompt (original_text + context + target_language)
        Agent->>LLM: Start streaming translation

        loop mỗi translation chunk
            LLM-->>Agent: token_chunk
            Agent-->>Chat: translation_chunk(message_id, chunk)
            Chat->>WS: relay chunk
            WS-->>ReceiverUI: translation_chunk(message_id, chunk)
            ReceiverUI->>Receiver: Cập nhật bản dịch (typing effect)
        end

        Agent->>DB: Save translation_results (async)
        DB-->>Agent: translation_id
        Agent-->>Chat: translation_completed(message_id, translation_id, source_language đã xác nhận)
        Chat->>WS: relay completed
        WS-->>SenderUI: translation_completed(...)
        WS-->>ReceiverUI: translation_completed(...)
    end

    opt Receiver chọn "Xem bản gốc"
        Receiver->>ReceiverUI: Toggle original
        ReceiverUI->>Receiver: Hiển thị original_text
    end

```

**Nguyên tắc thiết kế thể hiện trong sơ đồ:**

| # | Nguyên tắc |
|---|---|
| 1 | Tin nhắn gốc được lưu và xác nhận (ACK) trước khi thực hiện dịch. Hai luồng không phụ thuộc nhau |
| 2 | Trường `source_language` tại thời điểm lưu là giá trị tạm; kết quả detect sẽ ghi đè |
| 3 | Trường hợp ngôn ngữ nguồn trùng ngôn ngữ đích, hệ thống bỏ qua bước gọi LLM |
| 4 | Sự kiện `translation_completed` bắt buộc chứa `translation_id` để Frontend thực hiện gửi phản hồi (F-05) |
| 5 | Với chat nhóm, hệ thống thực hiện một lần dịch cho mỗi ngôn ngữ đích, không phải cho mỗi người nhận |
| 6 | Mọi sự kiện từ Agent đều đi qua Chat Service. Agent độc lập với tầng truyền tải WebSocket |
| 7 | Glossary thuộc phạm vi Post-MVP, sẽ được chèn vào bước "Build prompt" khi triển khai. Không có trong luồng MVP |

## 6. Use Case Diagram

```mermaid
graph LR
    subgraph SYS["Hệ thống AI Agent Dịch tin nhắn đa ngôn ngữ Real-time"]
        UC01[UC-01<br/>Đăng nhập]
        UC02[UC-02<br/>Thiết lập ngôn ngữ nhận]
        UC03[UC-03<br/>Tham gia chat 1-1 / nhóm]
        UC04[UC-04<br/>Gửi tin nhắn văn bản]
        UC05[UC-05<br/>Nhận tin nhắn real-time]
        UC06[UC-06<br/>Dịch tin nhắn theo ngữ cảnh]
        UC07[UC-07<br/>Xem bản gốc / bản dịch]
        UC08[UC-08<br/>Chỉnh sửa và gửi phản hồi]
    end

    Sender((Người gửi)) --> UC01
    Sender --> UC02
    Sender --> UC03
    Sender --> UC04
    UC04 -. include .-> UC06

    Receiver((Người nhận)) --> UC01
    Receiver --> UC02
    Receiver --> UC03
    Receiver --> UC05
    Receiver --> UC07
    Receiver --> UC08
```

**Nguyên tắc xây dựng sơ đồ:**

1. Actor "Người gửi" chỉ liên kết với UC-04 (gửi tin nhắn). Actor "Người nhận" chỉ liên kết với UC-05, UC-07, UC-08 (nhận, xem, phản hồi). Không tồn tại liên kết chéo giữa hai vai trò.
2. UC-06 là use case được gọi qua quan hệ `<<include>>` từ UC-04, không phải use case do người dùng kích hoạt trực tiếp.
3. Sơ đồ tập trung vào các chức năng người dùng tương tác trực tiếp, không đưa các thao tác kỹ thuật nội bộ vào use case.
