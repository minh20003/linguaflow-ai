# Thiết kế hệ thống — Role Admin & Agent Trợ lý

**Nhóm 4U (P-217)** — bổ sung cho `ARCHITECTURE.md` và `docs/architecture_diagram.md`

---

## PHẦN I — MÔ TẢ AGENT TRỢ LÝ MỚI

### 1.1 Định vị

**Assistant Agent** là agent thứ hai trong hệ thống, chạy song song với Translation Agent đã có. Hai agent độc lập về luồng xử lý, dùng chung tầng hạ tầng (auth, DB, WebSocket, observability).

| | Translation Agent (đã có) | Assistant Agent (mới) |
|---|---|---|
| Kích hoạt | Tự động, mọi tin nhắn | Theo yêu cầu (chat riêng / tag trong nhóm) |
| Đầu ra | Bản dịch, hiển thị cho mọi người | Tóm tắt & task, **chỉ người gọi thấy** |
| Tính chất | Đồng bộ, độ trễ thấp | Bất đồng bộ, chấp nhận độ trễ cao hơn |
| Ghi dữ liệu | Không tạo bản ghi mới | Tạo task, event, memory |

### 1.2 Hai chế độ xuất hiện

**Chế độ A — Hội thoại cá nhân với agent**

Agent xuất hiện như một liên hệ trong danh sách hội thoại (tương tự "Khánh Thi", "Report dự án" hiện có). Người dùng chat trực tiếp: yêu cầu tóm tắt, hỏi việc cần làm, xem lịch. Đây là không gian riêng tư hoàn toàn.

**Chế độ B — Tag trong nhóm**

Người dùng gõ `@assistant` trong group chat để nhờ việc ngay tại chỗ ("@assistant tóm tắt 50 tin vừa rồi", "@assistant nhắc tôi việc này thứ 5").

**Ràng buộc quan trọng:** phản hồi của agent trong nhóm là **tin nhắn riêng tư (ephemeral)** — chỉ người tag nhìn thấy, các thành viên khác trong nhóm không thấy gì cả. Về mặt kỹ thuật đây không phải tin nhắn nhóm thật, mà là bản ghi có `visibility = 'private'` và `visible_to_user_id = <người tag>`, chỉ render phía client của người đó.

Lý do thiết kế: nếu agent trả lời công khai, nội dung tóm tắt (có thể chứa suy luận về cam kết của người khác) sẽ lộ ra cho cả nhóm — vừa gây phiền, vừa vi phạm quyền riêng tư của những người chưa cấp phép.

### 1.3 Vòng đời của một task

```
Agent phát hiện → Task đề xuất (pending) → User duyệt/sửa/từ chối
                                          → [duyệt] → Task đã xác nhận
                                                    → Vào Dashboard lịch trong app
                                                    → [nếu bật] Đồng bộ Google Calendar
                                          → [từ chối] → Lưu làm tín hiệu cải thiện độ chính xác
```

Không có task nào tự động vào lịch. Đây là ràng buộc human-in-the-loop bắt buộc của đề bài.

---

## PHẦN II — CÁC SƠ ĐỒ HỆ THỐNG

### Sơ đồ 1 — Kiến trúc tổng thể sau khi thêm role Admin và Assistant Agent

```mermaid
graph TB
    User([Người dùng thường])
    Admin([Quản trị viên])

    subgraph FE ["Frontend — Next.js"]
        ChatUI["Giao diện chat<br/>+ tag @assistant"]
        CalUI["Dashboard lịch & task"]
        AdminUI["Bảng điều khiển quản trị"]
    end

    subgraph BE ["Backend — FastAPI"]
        WS["WebSocket<br/>streaming & thông báo"]
        API["REST API"]
        RBAC["Middleware phân quyền<br/>user / admin"]
    end

    subgraph AG ["Tầng Agent"]
        TA{"Translation Agent<br/>LangGraph"}
        AA{"Assistant Agent<br/>planner-executor"}
        LLM["LLM Service"]
        Obs(["Langfuse<br/>tracing & cost"])
    end

    subgraph TOOL ["Tools"]
        GCal["Google Calendar API"]
        Sched["Scheduler<br/>BullMQ / cron"]
    end

    subgraph DATA ["Data Layer"]
        PG[("PostgreSQL<br/>users, messages, tasks,<br/>glossary, feedback")]
        VDB[("Vector DB<br/>memory & semantic search")]
        Cache[("Redis<br/>cache & queue")]
    end

    User <--> ChatUI
    User <--> CalUI
    Admin --> AdminUI

    ChatUI <--> WS
    CalUI --> API
    AdminUI --> API

    API --> RBAC
    WS --> RBAC
    RBAC --> TA
    RBAC --> AA
    RBAC --> PG

    TA <--> LLM
    AA <--> LLM
    TA -.-> Obs
    AA -.-> Obs

    AA --> GCal
    AA --> Sched
    Sched -.->|đẩy nhắc việc| WS

    AA <--> VDB
    AA <--> PG
    TA <--> Cache
    Obs -.->|số liệu tổng hợp| AdminUI
```

### Sơ đồ 2 — Phân quyền: ranh giới metadata vs nội dung

```mermaid
graph LR
    subgraph U ["Quyền của USER"]
        U1["Đọc/ghi hội thoại của mình"]
        U2["Cấp & thu quyền đọc cho agent"]
        U3["Duyệt / sửa / từ chối task đề xuất"]
        U4["Sửa bản dịch, vote up/down"]
        U5["Đề xuất thuật ngữ vào glossary"]
        U6["Bật/tắt đồng bộ Google Calendar"]
    end

    subgraph A ["Quyền của ADMIN"]
        A1["Quản lý tài khoản: xem, khóa, mở"]
        A2["Duyệt glossary do agent đề xuất"]
        A3["Bảng đo chất lượng: BLEU, vote up/down"]
        A4["Dashboard token & chi phí"]
        A5["Cấu hình model, ngưỡng cảnh báo"]
        A6["Xem log lỗi & trace ẩn danh"]
    end

    subgraph F ["CẤM với cả hai vai trò"]
        F1["Đọc nội dung hội thoại của người khác"]
        F2["Xem nội dung task của người khác"]
        F3["Truy cập memory cá nhân của người khác"]
    end

    A -.->|không vượt qua được| F
    U -.->|không vượt qua được| F
```

### Sơ đồ 3 — Luồng Assistant Agent (LangGraph)

```mermaid
graph TB
    Start([Kích hoạt: chat riêng hoặc @tag]) --> Perm{Đã cấp quyền<br/>đọc hội thoại?}
    Perm -->|Chưa| AskPerm[Yêu cầu người dùng cấp quyền] --> End1([Kết thúc])
    Perm -->|Rồi| Fetch[Lấy tin nhắn trong phạm vi cho phép]

    Fetch --> Mem[Nạp memory ngữ cảnh<br/>từ Vector DB]
    Mem --> Sum[Tóm tắt hội thoại]
    Sum --> Extract[Trích xuất task / lịch hẹn / cam kết]

    Extract --> Ambig{Thông tin<br/>đủ rõ?}
    Ambig -->|Thiếu ngày, giờ, người| Ask[Hỏi lại người dùng] --> Wait([Chờ trả lời])
    Ambig -->|Đủ| Plan[Lập kế hoạch hành động]

    Plan --> Confirm[[HUMAN CONFIRM<br/>bắt buộc — không có đường vòng]]
    Confirm -->|Từ chối| Log[Ghi nhận tín hiệu<br/>cải thiện độ chính xác] --> End2([Kết thúc])
    Confirm -->|Duyệt| Exec[Thực thi tool:<br/>tạo task, reminder, event]

    Exec --> Sync{Bật đồng bộ<br/>Google Calendar?}
    Sync -->|Có| GC[Đẩy sự kiện lên Google Calendar]
    Sync -->|Không| Save[Lưu vào lịch trong app]
    GC --> Save
    Save --> Render[Hiển thị riêng tư cho người gọi] --> End3([Kết thúc])

    Extract -.->|lỗi LLM| Fallback[Trả thông báo lỗi thân thiện<br/>không làm đứt luồng chat] --> End2
```

### Sơ đồ 4 — Luồng duyệt glossary do agent đề xuất

```mermaid
sequenceDiagram
    participant U as Người dùng
    participant TA as Translation Agent
    participant DB as Database
    participant AD as Admin

    U->>TA: Sửa bản dịch một thuật ngữ
    TA->>DB: Lưu correction (kèm consent_to_share)
    Note over TA: Phát hiện thuật ngữ lặp lại<br/>từ nhiều người dùng
    TA->>DB: Tạo glossary_proposal (pending)<br/>+ trích dẫn ẩn danh

    AD->>DB: Mở trang duyệt glossary
    DB-->>AD: Danh sách đề xuất + trích dẫn<br/>(đã ẩn danh, chỉ đoạn liên quan)

    alt Admin duyệt
        AD->>DB: approve → status = active
        DB-->>TA: Nạp vào glossary khi dịch
    else Admin từ chối
        AD->>DB: reject + lý do
    end

    Note over AD,DB: Admin KHÔNG thấy: người gửi là ai,<br/>toàn bộ hội thoại, ngữ cảnh xung quanh
```

### Sơ đồ 5 — Đồng bộ hai chiều với Google Calendar

```mermaid
sequenceDiagram
    participant U as Người dùng
    participant App as LinguaFlow
    participant GC as Google Calendar

    Note over U,GC: Chiều đi — từ app ra Google
    U->>App: Duyệt task đề xuất
    App->>App: Lưu task + tạo event nội bộ
    App->>GC: Tạo sự kiện (kèm external_event_id)
    GC-->>App: Trả về event ID → lưu để đối chiếu

    Note over U,GC: Chiều về — từ Google vào app
    GC->>App: Webhook khi sự kiện thay đổi
    App->>App: Đối chiếu external_event_id
    alt Sự kiện có nguồn từ app
        App->>App: Cập nhật task tương ứng
        App-->>U: Thông báo qua WebSocket
    else Sự kiện tạo ngoài app
        App->>App: Hiển thị chỉ đọc trên dashboard lịch
    end
```

### Sơ đồ 6 — ER các bảng mới

```mermaid
erDiagram
    users ||--o{ tasks : "sở hữu"
    users ||--o{ agent_permissions : "cấp quyền"
    users ||--o{ translation_feedback : "gửi"
    users ||--o{ calendar_links : "liên kết"
    conversations ||--o{ agent_permissions : "được cấp quyền"
    tasks ||--o| calendar_events : "đồng bộ"
    messages ||--o{ translation_feedback : "nhận"
    glossary_proposals ||--o{ proposal_citations : "kèm theo"

    users {
        uuid id PK
        string role "user | admin"
        string preferred_language
    }
    agent_permissions {
        uuid id PK
        uuid user_id FK
        uuid conversation_id FK
        boolean is_granted "mặc định false"
        timestamp granted_at
    }
    tasks {
        uuid id PK
        uuid user_id FK
        string title
        timestamp due_at
        string status "pending | approved | rejected | done"
        uuid source_message_id
    }
    calendar_events {
        uuid id PK
        uuid task_id FK
        string external_event_id "ID phía Google"
        timestamp synced_at
    }
    calendar_links {
        uuid id PK
        uuid user_id FK
        boolean sync_enabled
        timestamp token_expires_at
    }
    translation_feedback {
        uuid id PK
        uuid message_id FK
        uuid user_id FK
        string vote "up | down"
        text corrected_text
        boolean consent_to_share "cho phép dùng làm trích dẫn"
    }
    glossary_proposals {
        uuid id PK
        string source_term
        string target_term
        string lang_pair
        string status "pending | active | rejected"
        int occurrence_count
    }
    proposal_citations {
        uuid id PK
        uuid proposal_id FK
        text anonymized_snippet "đã ẩn danh"
        timestamp observed_at
    }
```

### Sơ đồ 7 — Nguồn dữ liệu cho bảng điều khiển quản trị

```mermaid
graph LR
    subgraph SRC ["Nguồn dữ liệu"]
        S1[translation_feedback<br/>vote up/down]
        S2[Bộ test có nhãn<br/>reference translations]
        S3[Langfuse traces<br/>token, latency, cost]
        S4[glossary_proposals]
    end

    subgraph AGG ["Xử lý tổng hợp"]
        G1[Tỷ lệ hài lòng<br/>= up / tổng vote]
        G2[Tính điểm BLEU<br/>so với bản tham chiếu]
        G3[Tổng token & chi phí<br/>theo ngày / theo model]
        G4[Đếm tần suất xuất hiện]
    end

    subgraph DASH ["Bảng điều khiển Admin"]
        D1[Bảng đo chất lượng dịch]
        D2[Dashboard chi phí & token]
        D3[Hàng đợi duyệt glossary]
        D4[Cảnh báo vượt ngưỡng]
    end

    S1 --> G1 --> D1
    S2 --> G2 --> D1
    S3 --> G3 --> D2
    G3 --> D4
    S4 --> G4 --> D3

    style DASH fill:none
```

---

## PHẦN III — GHI CHÚ THIẾT KẾ

### 3.1 Vấn đề trích dẫn trong glossary — cần xử lý trước khi code

Yêu cầu "có trích dẫn để admin kiểm tra" mâu thuẫn trực tiếp với ràng buộc riêng tư (agent chỉ xử lý trong vùng đã giải mã, admin không đọc nội dung người dùng). Ba phương án, xếp theo mức độ an toàn:

| Phương án | Cách làm | Đánh giá |
|---|---|---|
| **A — Opt-in tường minh** *(đề xuất)* | Khi user sửa bản dịch, hỏi "Cho phép dùng bản sửa này để cải thiện hệ thống?". Chỉ correction có `consent_to_share = true` mới được dùng làm trích dẫn | An toàn nhất, minh bạch với người dùng, dễ giải thích khi bảo vệ |
| **B — Trích dẫn tối giản** | Chỉ hiện cụm từ chứa thuật ngữ (5–10 từ), ẩn danh người gửi, không hiện ngữ cảnh xung quanh | Chấp nhận được nếu kết hợp với A |
| **C — Không trích dẫn** | Admin chỉ thấy cặp thuật ngữ + số lần xuất hiện + tỷ lệ được người dùng chọn | An toàn tuyệt đối nhưng admin khó thẩm định |

Thiết kế trong sơ đồ 4 và bảng ER ở trên áp dụng **A + B kết hợp**: cần cả `consent_to_share` lẫn `anonymized_snippet`.

### 3.2 Về điểm BLEU — lưu ý khi triển khai

BLEU cần **bản dịch tham chiếu** để so sánh, không tự tính ra từ dữ liệu chạy thật. Với phạm vi 5 ngày, phương án thực tế:

- Xây bộ test nhỏ (50–100 câu) có bản dịch chuẩn do người trong nhóm hoặc dịch giả xác nhận
- Chạy định kỳ (không realtime), hiển thị điểm BLEU theo từng lần chạy để thấy xu hướng
- Hiển thị kèm **tỷ lệ vote up/down** — chỉ số này lấy từ người dùng thật, phản ánh chất lượng cảm nhận, bổ khuyết cho hạn chế của BLEU (BLEU phạt các bản dịch đúng nghĩa nhưng khác cách diễn đạt)

Đừng để dashboard chỉ có mỗi BLEU — với dịch hội thoại, hai chỉ số này nói hai chuyện khác nhau.

### 3.3 Tin nhắn riêng tư trong nhóm — điểm cần test kỹ

Cơ chế `visibility = 'private'` là chỗ dễ rò rỉ nhất. Cần test:
- Thành viên khác load lại lịch sử hội thoại → không thấy tin của agent
- Thành viên khác dùng chức năng tìm kiếm trong hội thoại → không tìm ra
- API trả về danh sách tin nhắn đã lọc **ở tầng backend**, không dựa vào frontend ẩn đi

Lọc ở frontend là lỗi bảo mật kinh điển — dữ liệu vẫn đi qua mạng, mở DevTools là thấy.

### 3.4 Việc cần chốt trong `CONTRACT.md` trước khi code

- Tên các event WebSocket mới: `assistant_response`, `task_proposed`, `task_confirmed`, `reminder_due`
- Enum trạng thái task: `pending | approved | rejected | done`
- Enum trạng thái glossary: `pending | active | rejected`
- Trường `visibility` và `visible_to_user_id` trong bảng `messages`
- Format payload của task đề xuất (agent → FE)