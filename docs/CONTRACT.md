# ĐẶC TẢ GIAO DIỆN HỆ THỐNG (API & DATA CONTRACT)

**Dự án:** LinguaFlow (P-217) · **Nhóm thực hiện:** 4U
**Phiên bản:** 1.0 · **Ngày cập nhật:** 10/08/2026 · **Trạng thái:** Đang áp dụng

---

## Phạm vi và hiệu lực

Tài liệu này quy định giao diện dùng chung giữa các phân hệ Frontend, Backend và AI Agent trong quá trình phát triển song song. Đây là **nguồn tham chiếu duy nhất** cho tên trường dữ liệu, endpoint và sự kiện WebSocket.

Trường hợp phát sinh nhu cầu về trường dữ liệu, endpoint hoặc sự kiện chưa có trong tài liệu: cập nhật tài liệu này trước, thông báo cho nhóm, hoàn tất merge, sau đó mới hiện thực hoá phần phụ thuộc. Không tự đặt tên khác hoặc bổ sung ngầm trong mã nguồn.

**Tài liệu liên quan:** căn cứ lựa chọn kiến trúc xem [`ARCHITECTURE.md`](../ARCHITECTURE.md); schema cơ sở dữ liệu đầy đủ xem [`architecture_diagram.md`](architecture_diagram.md) §4.

## Mục lục

1. [Quy ước chung](#1-quy-ước-chung)
2. [LangGraph AgentState](#2-langgraph-agentstate)
3. [REST API](#3-rest-api)
4. [WebSocket Protocol](#4-websocket-protocol)
5. [Schema cơ sở dữ liệu](#5-schema-cơ-sở-dữ-liệu)
6. [Đặc tả lỗi](#6-đặc-tả-lỗi)
7. [Danh mục kiểm tra trước khi hiện thực hoá](#7-danh-mục-kiểm-tra-trước-khi-hiện-thực-hoá)

---

## 1. Quy ước chung

| Hạng mục | Quy định |
|---|---|
| Tên trường JSON | `snake_case`, thống nhất với quy ước mặc định của Pydantic và FastAPI |
| Mã ngôn ngữ | Chuẩn ISO 639-1. Nguồn tham chiếu duy nhất là hằng `SUPPORTED_LANGUAGES` trong `src/schemas/auth.py`. Không liệt kê lại danh sách ở tài liệu hoặc mã nguồn khác |
| Tên trường ngôn ngữ | Sử dụng dạng đầy đủ `source_language` và `target_language` ở mọi tầng. Không sử dụng dạng viết tắt (`lang`, `src_lang`) |
| Định dạng thời gian | ISO 8601 múi giờ UTC. Ví dụ: `2026-08-10T09:00:00Z` |
| Định danh | Chuỗi UUID (`String(36)`). Cột khoá chính đặt tên `id`; khoá ngoại đặt tên `<thực_thể>_id` |
| Vị trí schema Pydantic | Thư mục `src/schemas/` (ví dụ `auth.py`, `chat.py`). Thư mục `src/models/` là thành phần kế thừa từ template, không bổ sung tệp mới |

### 1.1. Ngữ nghĩa trường `preferred_language`

Bảng `users` chỉ có một cột lưu thông tin ngôn ngữ. Ngữ nghĩa được quy định như sau:

> **`users.preferred_language` là ngôn ngữ người dùng muốn đọc (target language).**

Trường này không mang ý nghĩa "ngôn ngữ người dùng sử dụng khi soạn tin". Ngôn ngữ nguồn của mỗi tin nhắn luôn do Agent xác định. Giá trị `preferred_language` của người gửi chỉ được sử dụng làm giá trị tạm tại thời điểm ghi bản ghi (xem §4.3) và luôn bị kết quả detect ghi đè.

## 2. LangGraph AgentState

Cấu trúc dưới đây là bắt buộc đối với mọi node trong `src/agents/nodes/`. Không sử dụng tên trường khác.

```python
from typing import TypedDict


class AgentState(TypedDict, total=False):
    conversation_id: str
    message_id: str
    sender_id: str
    original_text: str
    source_language: str          # ISO 639-1; giá trị tạm khi vào, detect sẽ ghi đè
    target_language: str          # Lấy từ users.preferred_language của người nhận
    context_messages: list[str]   # 3-5 tin gần nhất, đã định dạng sẵn cho prompt
    translated_text: str
    translation_id: str           # Định danh bản ghi translation_results, phục vụ F-05
    is_valid: bool                # Kết quả của node validate_output
    is_fallback: bool             # True khi kết quả không đến từ LLM đã cấu hình:
                                  # provider dự phòng dịch thay, hoặc trả về bản gốc
    model: str                    # Ví dụ: "llama-3.3-70b-versatile";
                                  # "deep-translator:google" khi do provider dự phòng dịch
    latency_ms: int
    error: str
    telemetry: dict               # Chỉ phục vụ đo lường — xem cảnh báo bên dưới
```

**`telemetry` nằm ngoài hợp đồng.** Trường này *thuộc* hợp đồng, nhưng **các khoá bên trong thì không**. Node ghi vào đó những gì đo được (tầng nhận diện đã dùng, số lượt gọi LLM, token, thời gian từng bước, mã lý do fallback), `record_attempt` đọc ra và ghi xuống bảng `translation_attempts`. Không thành phần nào khác được phụ thuộc vào khoá cụ thể trong đây, và không sự kiện WebSocket hay REST response nào được trả nó ra.

Lý do gộp thành một trường thay vì tám trường rời: chỉ số đo lường thay đổi nhanh hơn hợp đồng sản phẩm. Nếu mỗi chỉ số mới là một trường mới thì mỗi lần muốn đo thêm một thứ đều phải sửa tài liệu, báo nhóm và chờ merge — chi phí đó khiến việc đo bị bỏ qua, đúng thứ NFR-03 cần tránh.

Node cập nhật bằng cách trộn nông, vì trường này không có reducer của LangGraph nên trả về thẳng sẽ ghi đè toàn bộ:

```python
return {"telemetry": {**state.get("telemetry", {}), "detect_method": "langdetect"}}
```

## 3. REST API

**Base path:** `/api/v1`
**Xác thực:** header `Authorization: Bearer <access_token>`

Ba endpoint thuộc nhóm `/auth` đã được hiện thực hoá tại nhánh `feature/f-01-2-auth-user-config` (`src/api/routes.py`, `src/schemas/auth.py`). Bảng dưới đây mô tả đúng mã nguồn hiện có.

| Method | Path | Request Body | Response | Trạng thái |
|---|---|---|---|---|
| `POST` | `/auth/login` | `{"email": str, "password": str}` | `{"access_token": str, "token_type": "bearer"}` | Đã hiện thực |
| `GET` | `/auth/me` | — | `UserDTO` | Đã hiện thực |
| `PUT` | `/auth/me/language` | `{"preferred_language": str}` | `UserDTO` | Đã hiện thực |
| `GET` | `/conversations/{conversation_id}/messages?limit=&before=` | — | `{"messages": [MessageDTO]}` | Chưa hiện thực |
| `POST` | `/translations/{translation_id}/feedback` | `{"rating": int, "correction": str \| null}` | `{"feedback_id": uuid}` | Chưa hiện thực |
| `GET` | `/stats?days=` | — | Xem §3.4 | Đã hiện thực |
| `GET` | `/health` | — | `{"status": "ok", "env": str}` | Đã hiện thực |

### 3.1. UserDTO

Tương ứng lớp `UserResponse` trong `src/schemas/auth.py`.

```json
{
  "id": "uuid",
  "email": "user@example.com",
  "role": "member",
  "preferred_language": "vi",
  "created_at": "2026-08-10T09:00:00Z"
}
```

### 3.2. MessageDTO

```json
{
  "id": "uuid",
  "conversation_id": "uuid",
  "sender_id": "uuid",
  "original_text": "string",
  "source_language": "vi",
  "created_at": "2026-08-10T09:00:00Z",
  "translations": [
    {
      "translation_id": "uuid",
      "target_language": "en",
      "translated_text": "string",
      "model": "llama-3.3-70b-versatile",
      "latency_ms": 420,
      "is_fallback": false
    }
  ]
}
```

Trường `translation_id` là bắt buộc trong mỗi phần tử của mảng `translations`. Frontend sử dụng giá trị này để gọi endpoint gửi phản hồi (F-05).

### 3.3. Endpoint kế thừa

Hai endpoint `POST /api/v1/chat` và `GET /api/v1/status` là mã nguồn kế thừa từ template, không thuộc phạm vi đặc tả này. Hai endpoint sẽ được loại bỏ đồng thời với việc thay thế `src/agents/` bằng Agent dịch thuật. Không phát triển tính năng mới dựa trên hai endpoint này.

### 3.4. `GET /stats`

Tổng hợp bảng `translation_attempts` (NFR-03). Tham số `days` không bắt buộc, nhận 1..365, bỏ trống thì tính toàn bộ dữ liệu.

```json
{
  "window_days": 7,
  "total_attempts": 128,
  "outcomes": {"llm": 96, "passthrough": 24, "secondary": 6, "timeout": 2},
  "fallback_rate": 0.0547,
  "detect_methods": {"langdetect": 100, "llm": 28},
  "fallback_reasons": {"llm_error": 6, "wrong_language": 2},
  "models_served": {"llama-3.3-70b-versatile": 104, "(none)": 24},
  "language_pairs": {"vi->en": {"count": 60, "p50_ms": 780, "p95_ms": 1430}},
  "input_tokens": 24800,
  "output_tokens": 1960,
  "total_ms_p50": 810,
  "total_ms_p95": 1520
}
```

Endpoint **yêu cầu xác thực**: nội dung không chứa văn bản tin nhắn và không có dữ liệu theo từng người dùng, nhưng có lộ lưu lượng toàn hệ thống và mức tiêu thụ token. Mọi thành viên đã đăng nhập đều đọc được.

`fallback_rate` là `(secondary + original) / total_attempts`, tính trên **toàn bộ** lượt thử — xem §5 ghi chú 10.

## 4. WebSocket Protocol

**Endpoint:** `ws://<host>/ws/conversations/{conversation_id}?token=<jwt>`

Mọi thông điệp trên kênh WebSocket bắt buộc chứa trường `type` để xác định loại sự kiện.

### 4.1. Chiều Client đến Server

| `type` | Payload | Ý nghĩa |
|---|---|---|
| `user.message` | `{"type": "user.message", "text": "string"}` | Gửi tin nhắn mới |

### 4.2. Chiều Server đến Client

Trình tự sự kiện khi cần dịch: `message.received` (trạng thái `streaming`) → nhiều `translation.chunk` → `translation.completed`. Trường hợp không cần dịch: chỉ phát `message.received` với trạng thái `not_required`. Trình tự chi tiết: xem [Sequence Diagram](architecture_diagram.md#5-sequence-diagram).

| `type` | Payload | Điều kiện phát |
|---|---|---|
| `message.received` | `{"type": "message.received", "message_id", "sender_id", "original_text", "source_language", "translation_status": "not_required" \| "streaming", "created_at"}` | Ngay sau khi Chat Service lưu xong tin nhắn gốc. Phát tới toàn bộ thành viên trong cuộc hội thoại, bao gồm người gửi |
| `translation.chunk` | `{"type": "translation.chunk", "message_id", "target_language", "chunk": "string"}` | Mỗi đoạn bản dịch nhận được từ LLM ở chế độ streaming |
| `translation.completed` | `{"type": "translation.completed", "message_id", "translation_id", "target_language", "source_language", "translated_text", "model", "latency_ms", "is_fallback"}` | Khi Agent hoàn tất xử lý, bao gồm cả trường hợp fallback |
| `error` | `{"type": "error", "code": "string", "message": "string"}` | Khi phát sinh lỗi kết nối hoặc xác thực (xem §6) |

**Quy định xử lý phía Frontend:**

1. Trường `translation_id` trong sự kiện `translation.completed` là nguồn duy nhất cung cấp định danh bản dịch cho Frontend. Thiếu trường này, tính năng F-05 không thể hiện thực hoá.
2. Trường `source_language` trong `translation.completed` là giá trị đã xác nhận sau bước detect, có thể khác giá trị tạm đã phát trong `message.received`. Frontend cập nhật lại theo giá trị này.
3. Với `is_fallback = true`, Frontend hiển thị chỉ báo phân biệt (ví dụ biểu tượng cảnh báo) nhưng không hiển thị dưới dạng lỗi, do tin nhắn gốc vẫn được truyền tới người nhận.
4. Frontend sử dụng `translated_text` trong `translation.completed` làm kết quả cuối cùng. Các sự kiện `translation.chunk` chỉ phục vụ hiệu ứng hiển thị theo thời gian thực và có thể bị mất gói.

### 4.3. Quy tắc xác định `source_language`

Tin nhắn được lưu trước khi Agent xác định ngôn ngữ, do đó cột `messages.source_language` cần giá trị tạm tại thời điểm ghi:

1. Khi `INSERT`: gán `messages.source_language` bằng `preferred_language` của người gửi. Đây là giá trị tạm, chưa xác nhận.
2. Sự kiện `message.received` phát kèm giá trị tạm này.
3. Agent xác định ngôn ngữ nguồn theo chiến lược hai tầng (ADR-11):
   - Văn bản dưới 5 ký tự hoặc không chứa chữ cái: giữ giá trị tạm, không detect.
   - `langdetect` (cục bộ, khoảng 2ms) trùng giá trị tạm: dùng kết quả này, không gọi LLM.
   - `langdetect` mâu thuẫn với giá trị tạm hoặc thất bại: gọi LLM phân xử. `langdetect` kém tin cậy với câu ngắn nên kết quả của nó không được dùng khi có mâu thuẫn.
4. Sau khi hoàn tất detect: nếu kết quả khác giá trị tạm, thực hiện `UPDATE messages.source_language` và phát giá trị đã xác nhận trong `translation.completed`.
4. Nếu ngôn ngữ nguồn đã xác nhận trùng `target_language` của một người nhận, người nhận đó chỉ nhận `message.received` với `translation_status = "not_required"`, không nhận `translation.chunk` và `translation.completed`.

### 4.4. Quy tắc định tuyến chat nhóm (F-02, US-010)

Áp dụng cho cuộc hội thoại có N thành viên sử dụng M ngôn ngữ khác nhau:

1. Server truy vấn tập `DISTINCT preferred_language` của toàn bộ thành viên, loại trừ `source_language` đã xác định.
2. Thực hiện một lần dịch cho mỗi ngôn ngữ đích còn lại (tối đa M-1 lần, không phải N lần). Các thành viên cùng ngôn ngữ dùng chung một bản dịch và cùng một `translation_id`.
3. Mỗi kết nối WebSocket chỉ nhận các sự kiện `translation.chunk` và `translation.completed` có `target_language` trùng với `preferred_language` của người dùng tương ứng.

Đây là yêu cầu chức năng bắt buộc, khác biệt với nội dung tối ưu hiệu năng tại ADR-03 ([`ARCHITECTURE.md`](../ARCHITECTURE.md)). ADR-03 chỉ đề cập việc tối ưu fan-out, không thay đổi quy tắc nêu trên.

## 5. Schema cơ sở dữ liệu

Quy ước đặt tên theo mã nguồn hiện có (`src/database/models.py`): tên bảng viết thường, dạng số nhiều; khoá chính đặt tên `id`.

| Bảng | Các trường |
|---|---|
| `users` | `id`, `email`, `password_hash`, `role`, `preferred_language`, `created_at` |
| `conversations` | `id`, `type`, `title`, `created_by`, `created_at` |
| `conversation_members` | `conversation_id`, `user_id`, `joined_at` |
| `messages` | `id`, `client_message_id`, `conversation_id`, `sender_id`, `original_text`, `source_language`, `created_at` |
| `translation_results` | `id`, `message_id`, `target_language`, `translated_text`, `model`, `latency_ms`, `is_fallback`, `created_at` |
| `feedbacks` | `id`, `translation_id`, `user_id`, `rating`, `correction`, `created_at` |
| `translation_attempts` | `id`, `message_id`, `target_language`, `source_language_declared`, `source_language_detected`, `outcome`, `provider`, `model_configured`, `model_served`, `detect_method`, `llm_calls`, `input_tokens`, `output_tokens`, `finish_reason`, `detect_ms`, `context_ms`, `translate_ms`, `fallback_ms`, `total_ms`, `context_lines`, `fallback_reason`, `translation_id`, `created_at` |

**Ghi chú:**

1. `users.role` là quyền ở cấp hệ thống (`member` hoặc `admin`). Bảng `conversation_members` **không có cột `role`**: không tính năng nào trong F-01..F-06 dùng tới vai trò trong hội thoại, nên cột này đã được gỡ khỏi hợp đồng thay vì thêm một cột chết vào mã nguồn.
2. `conversation_members` dùng **khoá chính tổ hợp** `(conversation_id, user_id)`, không có cột `id` riêng. Một người chỉ thuộc một hội thoại đúng một lần, nên tổ hợp này vừa là định danh vừa là ràng buộc.
3. `conversations.type` nhận `direct` hoặc `group`, có `CheckConstraint` ở mức cơ sở dữ liệu.
4. `messages.client_message_id` do client sinh ra, cùng `sender_id` và `conversation_id` tạo thành ràng buộc duy nhất. Đây là cơ chế cho phép gửi lại an toàn khi mất kết nối — xem `docs/RECONNECT_CONTRACT.md`.
5. `messages.source_language` khi ghi là **giá trị tạm** (`preferred_language` của người gửi); node `detect_language` của Agent ghi đè bằng kết quả nhận diện thật (§4.3).
6. `translation_results` có ràng buộc duy nhất `(message_id, target_language)`. Ràng buộc này ép quy tắc "thành viên cùng ngôn ngữ dùng chung một `translation_id`" (§4.4) ở mức schema, đồng thời làm tác vụ dịch chạy nền trở nên idempotent khi phải chạy lại.
7. `translation_results.is_fallback` đúng khi văn bản **không** đến từ LLM đã cấu hình, bao gồm cả trường hợp provider dự phòng dịch thành công. `model` để rỗng khi không tầng nào dịch được và hệ thống trả nguyên bản (`ARCHITECTURE.md` §5.1).
8. **Không có công cụ migration trong MVP.** `Base.metadata.create_all` tạo được bảng còn thiếu nhưng không bao giờ ALTER bảng đã có, nên thay đổi schema ở môi trường phát triển được áp dụng bằng `make reset-db` (xoá và tạo lại). Xem ADR-06.
9. `translation_attempts` là **nhật ký đo lường**, không phải trạng thái ứng dụng (ADR-16). Mỗi cặp (tin nhắn × ngôn ngữ đích) được thử ghi một dòng, **kể cả khi không sinh ra bản dịch nào**. Khác `translation_results` ở ba điểm có chủ đích: không có ràng buộc duy nhất (chạy lại là một lượt thử mới, đáng đếm riêng), `translation_id` cho phép `NULL` với `ON DELETE SET NULL` (xoá bản dịch không được xoá bằng chứng rằng đã dịch), và các cột được tự do thay đổi theo nhu cầu đo — **không** thành phần nào ngoài `src/services/metrics.py` và `scripts/report_metrics.py` được đọc bảng này.
10. `translation_attempts.outcome` nhận đúng bảy giá trị, có `CheckConstraint` ở mức cơ sở dữ liệu: `llm`, `secondary`, `original` (ba trường hợp có dòng trong `translation_results`), và `passthrough`, `timeout`, `error`, `empty` (bốn trường hợp không có). Bốn giá trị sau chính là mẫu số còn thiếu: mọi tỷ lệ fallback tính riêng trên các lượt thành công đều không phải là một tỷ lệ.
11. `translation_attempts.source_language_detected` để `NULL` khi nhận diện bị bỏ qua hoặc thất bại. Không được ghi giá trị khai báo vào đây: hai cột sẽ khớp nhau do cách xây dựng, và tỷ lệ đồng thuận của ADR-11 sẽ luôn đọc ra 100% bất kể nhận diện hoạt động thế nào.
12. `translation_attempts.total_ms` đo bằng wall clock ở tầng service, bao trùm cả truy vấn ngữ cảnh và overhead LangGraph, nên **rộng hơn** `translation_results.latency_ms` (chỉ tính thời gian gọi model). Ngữ nghĩa của `latency_ms` giữ nguyên vì nó đã nằm trong sự kiện WebSocket và REST history; NFR-01 nói về `total_ms`.

## 6. Đặc tả lỗi

Áp dụng thống nhất cho cả REST và WebSocket:

```json
{
  "type": "error",
  "code": "AUTH_FAILED | VALIDATION_ERROR | TRANSLATION_TIMEOUT | NOT_FOUND | INTERNAL_ERROR",
  "message": "Thông điệp dành cho người dùng, không chứa stack trace"
}
```

Ánh xạ mã lỗi sang HTTP status trên giao diện REST:

| `code` | HTTP status |
|---|---|
| `AUTH_FAILED` | 401 |
| `VALIDATION_ERROR` | 422 |
| `NOT_FOUND` | 404 |
| `TRANSLATION_TIMEOUT` | 500 |
| `INTERNAL_ERROR` | 500 |

## 7. Danh mục kiểm tra trước khi hiện thực hoá

- [ ] Tên trường dữ liệu tuân thủ đúng quy định tại §2, §3, §5
- [ ] Schema Pydantic mới được đặt trong `src/schemas/`, không bổ sung vào `src/models/`
- [ ] Mã ngôn ngữ tham chiếu hằng `SUPPORTED_LANGUAGES` (`src/schemas/auth.py`), không khai báo danh sách mới
- [ ] Trường hợp cần bổ sung trường, endpoint hoặc sự kiện: cập nhật tài liệu này và hoàn tất merge trước khi hiện thực hoá
- [ ] Mọi response REST và thông điệp WebSocket xác định được loại thông qua trường `type` hoặc cấu trúc rõ ràng
- [ ] Không phát triển tính năng mới trên hai endpoint kế thừa `/chat` và `/status`
