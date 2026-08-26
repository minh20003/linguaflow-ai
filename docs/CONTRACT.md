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

**Đổi `preferred_language` chỉ có hiệu lực với tin nhắn mới.** Bản dịch đã lưu trong `translation_results` không bị dịch lại, không có tác vụ nền nào chạy sau khi người dùng đổi ngôn ngữ, và `PUT /auth/me/language` không gọi Agent. Tin nhắn cũ vì thế giữ nguyên bản gốc cùng bản dịch đã có — client hiển thị bản dịch ứng với `target_language` mới nếu tồn tại, còn lại **hiển thị bản dịch đã lưu sẵn của tin đó** chứ không gọi lại API dịch và cũng không lùi về chỉ còn bản gốc.

### 1.2. Ngữ nghĩa trường `interface_language`

`users.interface_language` là ngôn ngữ của **chữ trên giao diện** — nhãn nút, trang cài đặt, điều khoản, thông báo hướng dẫn. Nó tách hẳn khỏi `preferred_language` ở §1.1 vì hai lựa chọn này độc lập: một người học tiếng Nhật có thể muốn đọc tin nhắn đã dịch sang tiếng Nhật nhưng vẫn muốn menu bằng tiếng Việt.

Hai trường khác nhau ở thời điểm có hiệu lực, và đây là điểm dễ nhầm nhất:

| | `preferred_language` | `interface_language` |
|---|---|---|
| Chi phối | Nội dung tin nhắn | Chữ của ứng dụng |
| Khi đổi | Chỉ áp dụng cho tin nhắn **mới** | Áp dụng **ngay lập tức** cho toàn bộ màn hình đang mở |
| Tốn hạn mức LLM | Có, khi có tin nhắn mới | Không bao giờ |

**Giao diện phải có đủ nhãn cho toàn bộ ngôn ngữ hệ thống hỗ trợ** — tức cả 14 mã trong `SUPPORTED_LANGUAGES` (`src/schemas/auth.py`), cùng danh sách mà `GET /languages` trả về. Không có ngôn ngữ hạng hai: đã cho chọn trong ô ngôn ngữ thì phải có nhãn.

Cơ chế lùi về `en` cho từng nhãn còn thiếu (quy tắc `altLabel` sẵn có ở `frontend/src/shared/lib/i18n.ts`) vẫn giữ, nhưng từ nay nó là **lưới an toàn cho lúc thêm nhãn mới**, không phải cách làm bình thường: thêm một nhãn vào giao diện mà chưa dịch thì người dùng `ar` thấy đúng dòng đó bằng tiếng Anh chứ không thấy chuỗi khoá hay màn hình trắng.

### 1.3. Ngôn ngữ trước khi đăng nhập

Trang đăng nhập và đăng ký chạy khi chưa có tài khoản nào để đọc `interface_language`, nên thứ tự lấy giá trị như sau:

1. **Lần đầu vào, chưa từng chọn gì: `en`.** Đây là ngôn ngữ duy nhất chắc chắn có đủ nhãn và là mặc định an toàn cho người lạ. `RegisterRequest.preferred_language` cũng mặc định `en` vì lý do này (sửa 16/08 — trước đây mặc định `vi`).
2. Người dùng đổi ngôn ngữ ngay tại đó bằng ô chọn có sẵn trên trang. Lựa chọn này đổi chữ **ngay lập tức** và được ghi vào `localStorage` của trình duyệt, nên lần vào sau vẫn đúng ngôn ngữ họ đã chọn.
3. **Đăng nhập xong thì `interface_language` của tài khoản thắng**, ghi đè giá trị trong `localStorage`. Từ đó trở đi ngôn ngữ giao diện và ngôn ngữ dịch đều lấy từ cài đặt tài khoản (§1.1, §1.2), không phải từ trình duyệt — đó là lý do hai trường này lưu ở server chứ không phải chỉ ở máy.

`localStorage` ở bước 2 không phải là nơi lưu chính thức, chỉ là bộ nhớ tạm cho trạng thái chưa đăng nhập và cho lần render đầu tiên sau khi mở lại trình duyệt. Không thành phần nào sau khi đăng nhập được đọc nó thay cho `UserDTO`.

**Khi đăng ký, ngôn ngữ đang chọn trở thành cả hai trường**: server ghi `interface_language = preferred_language = ` giá trị người dùng vừa chọn. Người mới chỉ phải trả lời một câu hỏi ngôn ngữ, và tách hai thứ ra là việc họ làm sau ở trang cài đặt nếu muốn. Vì vậy `POST /auth/register` **không** thêm trường mới vào request body.

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
| `POST` | `/auth/register` | `{"email": str, "password": str, "username": str \| null, "display_name": str \| null, "preferred_language": str}` | `{"access_token": str, "refresh_token": str, "token_type": "bearer", "user": UserDTO}` | Đã hiện thực |
| `POST` | `/auth/login` | `{"email": str, "password": str, "remember": bool}` | `{"access_token": str, "refresh_token": str, "token_type": "bearer", "user": UserDTO}` | Đã hiện thực |
| `POST` | `/auth/refresh` | `{"refresh_token": str}` | Như `/auth/login` | Đã hiện thực |
| `POST` | `/auth/logout` | `{"refresh_token": str}` | `204 No Content` | Đã hiện thực |
| `POST` | `/auth/password/forgot` | `{"email": str}` | `{"reset_token": str \| null}`, xem §3.9 | Đã hiện thực |
| `POST` | `/auth/password/reset` | `{"token": str, "password": str}` | `204 No Content` | Đã hiện thực |
| `GET` | `/auth/me` | — | `UserDTO` | Đã hiện thực |
| `PUT` | `/auth/me/language` | `{"preferred_language": str}` | `UserDTO` | Đã hiện thực |
| `PUT` | `/auth/me/interface-language` | `{"interface_language": str}` | `UserDTO`, xem §1.2 | Đã hiện thực |
| `GET` | `/languages` | — | `[str]` | Đã hiện thực |
| `GET` | `/users?q=` | — | `[UserDTO]`, xem §3.1 | Đã hiện thực |
| `POST` | `/conversations` | `{"type": "direct" \| "group", "member_ids": [uuid], "title": str \| null}` | `ConversationDTO`, `201` khi tạo mới và `200` khi dùng lại — xem §3.5 | Đã hiện thực |
| `GET` | `/conversations/{conversation_id}/messages?limit=&before=` | — | `[MessageDTO]` — mảng trần, xem ghi chú §3.2 | Đã hiện thực |
| `POST` | `/translations/{translation_id}/feedback` | `{"rating": int, "correction": str \| null}` | `{"feedback_id": uuid}` | Đã hiện thực |
| `POST` | `/translations/{translation_id}/edits` | `{"edited_text": str}` | `TranslationEditDTO`, xem §3.10 | **Đề xuất** |
| `PATCH` | `/conversations/{conversation_id}/messages/{message_id}` | `{"text": str}` | `MessageDTO`, xem §3.6 | Đã hiện thực |
| `DELETE` | `/conversations/{conversation_id}/messages/{message_id}` | — | `204 No Content` | Đã hiện thực |
| `POST` | `/conversations/{conversation_id}/attachments` | `multipart/form-data`, trường `file` | `AttachmentDTO`, xem §3.7 | Đã hiện thực |
| `GET` | `/conversations/{conversation_id}/attachments/{attachment_id}` | — | Nội dung tệp | Đã hiện thực |
| `POST` | `/conversations/{conversation_id}/read` | — | `{"unread_count": 0}` | Đã hiện thực |
| `GET` | `/conversations` | — | `[ConversationDTO]`, xem §3.5 | Đã hiện thực |
| `GET` | `/stats?days=` | — | Xem §3.4 | Đã hiện thực |
| `GET` | `/health` | — | `{"status": "ok", "env": str}` | Đã hiện thực |

### 3.1. UserDTO

Tương ứng lớp `UserResponse` trong `src/schemas/auth.py`.

```json
{
  "id": "uuid",
  "email": "user@example.com",
  "username": "an",
  "display_name": "Nguyễn An",
  "role": "member",
  "preferred_language": "vi",
  "interface_language": "vi",
  "created_at": "2026-08-10T09:00:00Z"
}
```

Trường `interface_language` (§1.2) **không bao giờ null**: tài khoản tạo trước khi có nó nhận giá trị bằng `preferred_language` của chính mình lúc migrate, nên giao diện của họ không đổi sau khi nâng cấp.

Hai trường `username` và `display_name` **không bao giờ null trong phản hồi**: tài khoản tạo trước khi có hai trường này được lấp bằng phần trước dấu `@` của email, nên client luôn có thứ để hiển thị.

**Tìm người dùng — `GET /users?q=`.** Tham số `q` tối thiểu 2 ký tự, khớp **tiền tố, không phân biệt hoa thường** trên `email`, `username` và `display_name`; riêng `display_name` khớp tiền tố của **bất kỳ từ nào** (gõ `an` tìm ra `Nguyễn An`). Trả về tối đa 20 kết quả, sắp xếp theo `email`, và **không bao giờ chứa chính người gọi**. Không tìm thấy ai là mảng rỗng chứ không phải `404` — `404` sẽ lẫn với lỗi sai đường dẫn.

Khớp tiền tố chứ không phải khớp giữa chuỗi: tìm giữa chuỗi biến endpoint này thành công cụ quét danh bạ (gõ `a` ra gần như mọi tài khoản). Endpoint yêu cầu đăng nhập, nhưng người đã đăng nhập vẫn dò được sự tồn tại của một địa chỉ — chấp nhận ở giai đoạn này vì chưa có giới hạn tần suất; xem `docs/DEPLOY.md`.

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
      "is_fallback": false,
      "my_rating": 5,
      "my_correction": null,
      "my_edit": {
        "edit_id": "uuid",
        "edited_text": "string",
        "edited_at": "2026-08-15T09:04:00Z"
      }
    }
  ]
}
```

**Lịch sử trả về mảng trần, không bọc trong `{"messages": ...}`.** Bảng ở §3 từng ghi dạng bọc và đánh dấu "chưa hiện thực"; endpoint đã được hiện thực từ lâu với `response_model=list[MessageResponse]` (`src/api/routes.py`), và client đang đọc theo mã nguồn. Sửa tài liệu cho khớp mã chứ không ngược lại: đổi hình dạng phản hồi bây giờ sẽ làm hỏng frontend đang chạy, để đúng một dấu ngoặc trong tài liệu.

Trường `translation_id` là bắt buộc trong mỗi phần tử của mảng `translations`. Frontend sử dụng giá trị này để gọi endpoint gửi phản hồi (F-05).

Trường `my_edit` là bản góp ý **mới nhất của chính tài khoản đang gọi** cho bản dịch đó, `null` khi họ chưa góp ý (§3.10). Tiền tố `my_` mang đúng nghĩa như ở `my_rating`: hai người đọc cùng một `translation_id` nhận hai giá trị khác nhau, và **không tài khoản nào đọc được `my_edit` của người khác**. Chỉ bản mới nhất nằm trong DTO; lịch sử đầy đủ nằm trong bảng `translation_edits` và chỉ dành cho quản trị.

Ba trường `my_rating`, `my_correction` và `my_edit` là phản hồi **của chính tài khoản đang gọi** cho bản dịch đó, `null` khi tài khoản chưa đánh giá. Chúng tồn tại để nút đánh giá giữ nguyên trạng thái sau khi tải lại trang — không có chúng, người dùng không phân biệt được "chưa bình chọn" với "đã bình chọn nhưng giao diện quên mất". Đây là dữ liệu riêng theo người gọi: hai thành viên khác nhau đọc cùng một `translation_id` sẽ nhận hai giá trị khác nhau, nên tuyệt đối không cache chung giữa các tài khoản.

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

Endpoint **chỉ dành cho quản trị viên**: nội dung không chứa văn bản tin nhắn và không có dữ liệu theo từng người dùng, nhưng có lộ lưu lượng toàn hệ thống và mức tiêu thụ token. Chỉ tài khoản có `role == "admin"` được đọc; thành viên nhận `403 Forbidden`.

`fallback_rate` là `(secondary + original) / total_attempts`, tính trên **toàn bộ** lượt thử — xem §5 ghi chú 10.

### 3.5. ConversationDTO

Tương ứng lớp `ConversationResponse` trong `src/schemas/chat.py`, trả về bởi `GET /conversations` và `POST /conversations`.

```json
{
  "id": "uuid",
  "type": "group",
  "title": "Nhóm dự án",
  "created_by": "uuid",
  "created_at": "2026-08-10T09:00:00Z",
  "member_ids": ["uuid"],
  "members": [{"id": "uuid", "email": "user@example.com", "username": "an", "display_name": "Nguyễn An", "preferred_language": "vi"}],
  "last_message": "Deploy xong chưa anh?",
  "last_message_at": "2026-08-14T10:12:00Z",
  "online_member_ids": ["uuid"]
}
```

`online_member_ids` liệt kê những thành viên **đang giữ socket** tại thời điểm gọi, đọc từ sổ kết nối trong tiến trình chứ không từ cơ sở dữ liệu, nên không tốn thêm truy vấn nào. Đây là ảnh chụp tại thời điểm gọi: trạng thái online **không** được đẩy tiếp qua WebSocket, client muốn cập nhật thì gọi lại `GET /conversations`.

Lý do không đẩy qua socket: xác định "ai cần biết" đòi hỏi một truy vấn ngay lúc socket vừa mở hoặc vừa đóng, mà phiên cơ sở dữ liệu lại có vòng đời gắn với chính socket đó — truy vấn tại hai thời điểm ấy chạy đua với việc dọn phiên và làm hỏng kết nối một cách không ổn định. Đổi lại, trạng thái online chỉ mới đến mức lần gọi gần nhất.

Hai trường `last_message` và `last_message_at` mô tả tin nhắn mới nhất của hội thoại, `null` khi hội thoại chưa có tin nào.

**Tin mới nhất đã bị gỡ thì `last_message` là chuỗi rỗng, `last_message_at` vẫn giữ nguyên** (sửa 16/08). Trước đây tin đã gỡ bị loại khỏi phép tính, nên dòng xem trước lùi về tin trước đó — hoặc trống hẳn khi không còn tin nào — và người dùng không có cách nào biết chuyện gì vừa xảy ra. Chuỗi rỗng là tín hiệu không nhập nhằng vì tin nhắn thường **không bao giờ** rỗng: endpoint gửi tin từ chối nội dung trắng (§3.6). Câu chữ hiển thị ("Tin nhắn đã được thu hồi") do client quyết định — đó là chữ giao diện và phải theo ngôn ngữ người đọc, không phải thứ server áp đặt. Chúng tồn tại để danh sách hội thoại hiển thị được dòng xem trước và thời gian mà không phải gọi thêm một request cho mỗi hội thoại.

`last_message` là **dữ liệu riêng theo người gọi**, cùng nguyên tắc với `my_rating` ở §3.2: nếu tin nhắn đó đã có bản dịch sang `preferred_language` của tài khoản đang gọi thì trả về bản dịch, không thì trả về `original_text`. Lý do: danh sách hội thoại mà hiển thị thứ tiếng người đọc không hiểu thì không dùng để nhận ra hội thoại được. Vì vậy tuyệt đối không cache chung giá trị này giữa các tài khoản.

`POST /conversations` luôn trả về hai trường này bằng `null` — hội thoại vừa tạo chưa có tin nhắn nào.

Mỗi phần tử của `members` mang `username` và `display_name` theo đúng quy tắc lấp giá trị ở §3.1, để client hiển thị được tên người thay vì phải tự cắt email.

**Hội thoại 1-1 là duy nhất theo cặp người.** `POST /conversations` với `type: "direct"` mà giữa hai người đã có một hội thoại `direct` thì trả lại đúng hội thoại đó kèm mã **`200 OK`**; chỉ khi thật sự tạo mới mới trả `201 Created`. Không có quy tắc này thì mỗi lần bấm "nhắn tin" lại sinh thêm một hội thoại rỗng và lịch sử trò chuyện bị chẻ ra nhiều nơi. Client nên gộp kết quả vào danh sách theo `id` thay vì nối thêm.

Quy tắc này **không áp dụng cho `type: "group"`**: hai nhóm cùng thành viên vẫn là hai nhóm khác nhau, vì nhóm được phân biệt bằng mục đích chứ không bằng danh sách người.

### 3.6. Sửa và gỡ tin nhắn (F-06)

`PATCH .../messages/{message_id}` đổi `original_text`, ghi `edited_at`, rồi **dịch lại** tin nhắn cho các thành viên còn lại — bản dịch cũ không còn đúng với nội dung mới. `DELETE .../messages/{message_id}` là **xoá mềm**: giữ nguyên dòng, ghi `deleted_at`, và từ đó API trả `original_text` rỗng cùng mảng `translations` rỗng.

Xoá mềm chứ không xoá cứng vì `translation_results` và `translation_attempts` trỏ vào `messages` — xoá cứng sẽ kéo theo toàn bộ bằng chứng đo lường mà ADR-16 dựng ra để giữ, tức là gỡ một tin nhắn sẽ âm thầm làm sai số liệu `fallback_rate` ở §3.4.

Phân quyền: **chỉ người gửi** mới sửa hoặc gỡ được tin của mình (`403` nếu không phải). Tin đã gỡ không sửa được nữa (`409`). Cả hai endpoint trả `404` khi tin nhắn không tồn tại hoặc không thuộc hội thoại đã nêu, và `403` khi người gọi không phải thành viên hội thoại.

Hai trường `edited_at` và `deleted_at` có mặt trong mọi `MessageDTO`, `null` khi tin nhắn chưa bị sửa hoặc chưa bị gỡ.

### 3.7. Đính kèm tệp và trả lời

**AttachmentDTO**

```json
{
  "id": "string",
  "conversation_id": "uuid",
  "filename": "bao-cao.pdf",
  "content_type": "application/pdf",
  "size": 184320,
  "download_url": "/api/v1/conversations/{conversation_id}/attachments/{attachment_id}"
}
```

Tệp được tải lên **trước**, sau đó mới gửi tin nhắn kèm `attachment_id` trong sự kiện `send_message` (§4.1). Vì vậy một bản ghi đính kèm có thể tồn tại mà chưa gắn với tin nhắn nào — đó là tệp người dùng đã chọn rồi đổi ý, không phải lỗi. Tệp nằm ngoài thư mục tĩnh công khai; tải xuống vẫn phải qua kiểm tra tư cách thành viên, nên biết URL không đồng nghĩa với có quyền đọc.

`MessageDTO` mang thêm `attachment` (AttachmentDTO hoặc `null`) và `reply_to_message_id` (uuid hoặc `null`).

`reply_to_message_id` dùng `ON DELETE SET NULL`: gỡ tin nhắn gốc **không** kéo theo các tin trả lời nó — đó là lời của người khác. Client thấy `reply_to_message_id` trỏ tới tin đã bị gỡ thì hiển thị trích dẫn rỗng chứ không ẩn cả tin trả lời.

### 3.8. Đếm chưa đọc

`ConversationDTO` mang thêm `unread_count`: số tin nhắn **của người khác** tạo sau mốc `conversation_members.last_read_at` của tài khoản đang gọi. Tin do chính mình gửi không bao giờ được tính là chưa đọc, và tin đã gỡ cũng vậy.

`POST /conversations/{id}/read` đặt mốc đó về thời điểm hiện tại và trả về `{"unread_count": 0}`. Server phát tiếp sự kiện `message_read` (§4.2) để phía người gửi đổi dấu đã gửi thành đã xem.

### 3.9. Đặt lại mật khẩu

`POST /auth/password/forgot` **luôn** trả `200` kèm cùng một câu trả lời chung, dù địa chỉ có tồn tại hay không — trả `404` cho địa chỉ lạ sẽ biến endpoint này thành công cụ dò tài khoản không cần đăng nhập.

Trường `reset_token` trong phản hồi chỉ có giá trị khi `APP_ENV=development`, để lập trình viên chạy trọn luồng trên một màn hình. **Ở mọi môi trường khác, trường này là `null` và mã đặt lại chỉ được ghi vào log của server** (mức `WARNING`), do dự án chưa gắn dịch vụ gửi email — xem `docs/DEPLOY.md`. Client vì thế phải cho người dùng **nhập tay mã đặt lại** khi phản hồi không kèm token, chứ không được coi đó là lỗi.

`POST /auth/password/reset` tiêu thụ mã đó, đổi mật khẩu và **thu hồi toàn bộ phiên** của tài khoản. Mã dùng một lần và hết hạn sau `PASSWORD_RESET_EXPIRE_MINUTES` phút.

### 3.10. Góp ý bản dịch (F-05 mở rộng)

Nút bút chì dưới mỗi bản dịch cho phép người đọc gõ lại bản họ cho là đúng. **Bản góp ý là dữ liệu riêng tư của chính người viết ra nó** — không thành viên nào khác đọc được, kể cả người gửi tin nhắn, và nó không thay đổi thứ bất kỳ ai khác nhìn thấy.

Đây là điểm phân biệt bắt buộc với §3.6, hai việc rất dễ lẫn:

| | §3.6 Sửa **tin nhắn** (F-06) | §3.10 Góp ý **bản dịch** (F-05) |
|---|---|---|
| Ai làm được | Chỉ người gửi (server chặn) | Mọi thành viên (server); giao diện chỉ hiện nút cho người đọc bản dịch đó, cộng người gửi ở `direct` |
| Sửa cái gì | `messages.original_text` | Không sửa gì cả — ghi thêm một bản song song |
| Ai thấy kết quả | **Cả phòng**: nội dung mới, bản dịch mới, trạng thái "đã sửa" | **Chỉ người viết góp ý** |
| Có dịch lại không | Có, tốn hạn mức LLM | Không bao giờ |
| Sự kiện WebSocket | `message_updated`, rồi `translation_completed` như tin thường | **Không có** |

**TranslationEditDTO**

```json
{
  "edit_id": "uuid",
  "translation_id": "uuid",
  "message_id": "uuid",
  "target_language": "en",
  "edited_text": "string",
  "edited_at": "2026-08-15T09:04:00Z"
}
```

Không có trường `edited_by`: người viết luôn là tài khoản đang gọi, vì không tài khoản nào đọc được bản góp ý của người khác.

**Ai được góp ý — quy tắc phía server.** Bất kỳ **thành viên nào của hội thoại**, `403` nếu không phải. Đây là mô tả đúng endpoint feedback đã hiện thực (`src/api/routes.py`, `submit_translation_feedback`), vốn chỉ kiểm tư cách thành viên chứ không kiểm ngôn ngữ, và endpoint góp ý mới dùng lại đúng phạm vi đó. Không siết chặt hơn ở server vì dữ liệu này riêng tư: một thành viên gọi API để tự ghi chú về một bản dịch họ không đọc thì cũng không ai bị ảnh hưởng, trong khi thêm một quy tắc phân quyền nữa là thêm một chỗ để sai.

**Ai thấy nút — quy tắc phía client.** Hẹp hơn quy tắc trên, và đây mới là thứ người dùng cảm nhận được:

| Loại hội thoại | Người nhận | Người gửi |
|---|---|---|
| `direct` | Nút gạt bản gốc/bản dịch, đánh giá, góp ý | **Giống hệt người nhận**: nút gạt, đánh giá, góp ý |
| `group` | Nút gạt, đánh giá, góp ý cho bản dịch ngôn ngữ mình đọc | **Không có nút nào** |

Người gửi ở `direct` có đủ bộ điều khiển vì hội thoại chỉ có một người nhận và một bản dịch: họ nhìn thấy trọn vẹn cả bản gốc lẫn bản dịch nên đánh giá được, và cái họ gạt qua gạt lại là chính hai văn bản đó. Ở `group` thì không: một tin nhắn có nhiều bản dịch, không có "bản dịch của tin này" để mà gạt hay chấm điểm, nên người gửi không thấy nút nào và ai đọc ngôn ngữ nào thì góp ý cho ngôn ngữ ấy.

Nút gạt bản gốc/bản dịch không gọi API nào — nó chỉ đổi văn bản đang hiển thị trong bóng chat, dữ liệu đã có sẵn ở client.

**Góp ý nhiều lần.** Mỗi lần gọi ghi thêm một dòng vào `translation_edits`, không ghi đè. Bản có `created_at` mới nhất **của chính người đó** là bản có hiệu lực và là bản duy nhất xuất hiện trong `MessageDTO`; các bản trước vẫn nằm trong bảng, dành cho tính năng quản trị về sau. Không có endpoint xoá.

**Bản máy dịch không bao giờ bị ghi đè.** `translation_results.translated_text` giữ nguyên văn bản LLM sinh ra. Đây là điều kiện để so sánh người với máy, nên client **không** được coi bản góp ý là bản dịch mới của hệ thống.

**Hiển thị.** Bóng chat luôn hiện `translated_text`. Bản góp ý của chính mình nằm sau nút bút chì: bấm để mở, bấm lần nữa để đóng. Người dùng vì thế đối chiếu được hai bản, thay vì bị thay thầm nội dung đang đọc.

`404` khi `translation_id` không tồn tại; `409` khi tin nhắn tương ứng đã bị gỡ (§3.6).

## 4. WebSocket Protocol

**Endpoint:** `ws(s)://<host>/api/v1/ws` — một kênh duy nhất cho mọi hội thoại, không phải một kênh cho mỗi hội thoại.

**Xác thực:** token **không** nằm trong query string (query string bị ghi vào log của proxy). Khung đầu tiên client gửi phải là `{"type": "auth", "token": "<access_token>"}`, trong vòng 10 giây, nếu không server đóng kết nối với mã `4401`. Xác thực xong server trả `auth_ok`.

Server còn kiểm tra header `Origin` **trước khi** bắt tay: nguồn không nằm trong `CORS_ORIGINS` (hoặc `CORS_ORIGIN_REGEX`) bị từ chối với mã `4403`. Middleware CORS không áp dụng cho WebSocket, nên nếu thiếu bước này thì bất kỳ trang web nào cũng mở được socket trong trình duyệt của người đang đăng nhập.

Mọi thông điệp trên kênh WebSocket bắt buộc chứa trường `type` để xác định loại sự kiện.

### 4.1. Chiều Client đến Server

| `type` | Payload | Ý nghĩa |
|---|---|---|
| `user.message` | `{"type": "user.message", "text": "string"}` | Gửi tin nhắn mới |
| `typing` | `{"type": "typing", "conversation_id": uuid, "is_typing": bool}` | Người dùng bắt đầu hoặc ngừng soạn tin. Server kiểm tra tư cách thành viên rồi mới phát tiếp |
| `send_message` | thêm hai trường tuỳ chọn `attachment_id` và `reply_to_message_id` | Gửi tin kèm tệp đã tải lên trước đó (§3.7) hoặc trả lời một tin cụ thể |

### 4.2. Chiều Server đến Client

Trình tự sự kiện khi cần dịch: `message.received` (trạng thái `streaming`) → nhiều `translation.chunk` → `translation.completed`. Trường hợp không cần dịch: chỉ phát `message.received` với trạng thái `not_required`. Trình tự chi tiết: xem [Sequence Diagram](architecture_diagram.md#5-sequence-diagram).

| `type` | Payload | Điều kiện phát |
|---|---|---|
| `message.received` | `{"type": "message.received", "message_id", "sender_id", "original_text", "source_language", "translation_status": "not_required" \| "streaming", "created_at"}` | Ngay sau khi Chat Service lưu xong tin nhắn gốc. Phát tới toàn bộ thành viên trong cuộc hội thoại, bao gồm người gửi |
| `translation.chunk` | `{"type": "translation.chunk", "message_id", "target_language", "chunk": "string"}` | Mỗi đoạn bản dịch nhận được từ LLM ở chế độ streaming |
| `translation.completed` | `{"type": "translation.completed", "message_id", "translation_id", "target_language", "source_language", "translated_text", "model", "latency_ms", "is_fallback"}` | Khi Agent hoàn tất xử lý, bao gồm cả trường hợp fallback |
| `typing` | `{"type": "typing", "conversation_id", "user_id", "is_typing"}` | Chuyển tiếp sự kiện soạn tin tới **các thành viên khác**, không gửi lại cho chính người gõ |
| `message_updated` | `{"type": "message_updated", "message_id", "conversation_id", "original_text", "edited_at"}` | Sau khi người gửi sửa tin nhắn (§3.6). Phát tới các thành viên khác; bản dịch mới đến sau bằng `translation_completed` như tin nhắn thường |
| `message_deleted` | `{"type": "message_deleted", "message_id", "conversation_id", "deleted_at"}` | Sau khi người gửi gỡ tin nhắn (§3.6). Phát tới các thành viên khác |
| `message_read` | `{"type": "message_read", "conversation_id", "user_id", "read_at"}` | Khi một thành viên đánh dấu đã đọc (§3.8). Phát tới các thành viên khác để họ đổi dấu ✓ thành ✓✓ |
| `error` | `{"type": "error", "code": "string", "message": "string"}` | Khi phát sinh lỗi kết nối hoặc xác thực (xem §6) |

**Góp ý bản dịch (§3.10) không có sự kiện WebSocket nào.** Bản góp ý là dữ liệu riêng của người viết, không ai khác đọc được, nên không có gì để phát đi — phản hồi của lời gọi REST là đủ. Việc "người nhận thấy nội dung mới" thuộc về §3.6: người gửi sửa **tin nhắn gốc**, server dịch lại, cả phòng nhận `message_updated` rồi `translation_completed` như một tin nhắn thường và bóng chat hiện trạng thái đã sửa. Đừng gộp hai luồng này.

Hai sự kiện `message_updated` và `message_deleted` đặt tên `snake_case` theo đúng quy ước trong `CLAUDE.md` và theo tên các sự kiện đã hiện thực trong `src/schemas/chat.py`. Các dòng viết dạng chấm phía trên là bản nháp trước khi hiện thực, chưa được đồng bộ lại với mã nguồn.

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
3. Mỗi kết nối WebSocket chỉ nhận các sự kiện `translation.chunk` và `translation.completed` có `target_language` trùng với `preferred_language` của người dùng tương ứng — **cộng thêm người gửi tin nhắn trong hội thoại `type = "direct"`, nhận bản dịch của chính tin mình gửi** (sửa theo §3.10, **đề xuất**).

   Vế thêm vào là điều kiện để §3.10 chạy được ở chat 1-1. Trước đây `_recipients_by_language` xếp người gửi vào đúng nhóm ngôn ngữ *họ đọc*, nên giữa một người đọc `vi` và một người đọc `en`, bản dịch `en` chỉ tới người nhận. Người gửi không có bản dịch nào trong tay để đối chiếu hay góp ý cho tới khi tải lại trang — trong khi `GET /conversations/{id}/messages` vốn đã trả **toàn bộ** bản dịch của mỗi tin, tức dữ liệu đã sẵn sàng, chỉ thiếu đường phát theo thời gian thực.

   Phạm vi dừng ở `direct` chứ không mở cho nhóm, vì quyền góp ý của người gửi cũng chỉ có ở `direct` (§3.10). Hội thoại `direct` có đúng một ngôn ngữ đích khác, nên người gửi nhận thêm nhiều nhất một sự kiện cho mỗi tin nhắn.

Đây là yêu cầu chức năng bắt buộc, khác biệt với nội dung tối ưu hiệu năng tại ADR-03 ([`ARCHITECTURE.md`](../ARCHITECTURE.md)). ADR-03 chỉ đề cập việc tối ưu fan-out, không thay đổi quy tắc nêu trên.

## 5. Schema cơ sở dữ liệu

Quy ước đặt tên theo mã nguồn hiện có (`src/database/models.py`): tên bảng viết thường, dạng số nhiều; khoá chính đặt tên `id`.

| Bảng | Các trường |
|---|---|
| `users` | `id`, `email`, `password_hash`, `role`, `preferred_language`, `interface_language`, `created_at` |
| `conversations` | `id`, `type`, `title`, `created_by`, `created_at` |
| `conversation_members` | `conversation_id`, `user_id`, `joined_at` |
| `messages` | `id`, `client_message_id`, `conversation_id`, `sender_id`, `original_text`, `source_language`, `created_at`, `edited_at`, `deleted_at` |
| `translation_results` | `id`, `message_id`, `target_language`, `translated_text`, `model`, `latency_ms`, `is_fallback`, `created_at` |
| `feedbacks` | `id`, `translation_id`, `user_id`, `rating`, `correction`, `created_at` |
| `translation_edits` | `id`, `translation_id`, `editor_id`, `edited_text`, `created_at` |  <!-- đã hiện thực -->
| `translation_attempts` | `id`, `message_id`, `target_language`, `source_language_declared`, `source_language_detected`, `outcome`, `provider`, `model_configured`, `model_served`, `detect_method`, `llm_calls`, `input_tokens`, `output_tokens`, `finish_reason`, `detect_ms`, `context_ms`, `translate_ms`, `fallback_ms`, `total_ms`, `context_lines`, `fallback_reason`, `translation_id`, `created_at` |

**Ghi chú:**

1. `users.role` là quyền ở cấp hệ thống (`member` hoặc `admin`). Bảng `conversation_members` **không có cột `role`**: không tính năng nào trong F-01..F-06 dùng tới vai trò trong hội thoại, nên cột này đã được gỡ khỏi hợp đồng thay vì thêm một cột chết vào mã nguồn.
2. `conversation_members` dùng **khoá chính tổ hợp** `(conversation_id, user_id)`, không có cột `id` riêng. Một người chỉ thuộc một hội thoại đúng một lần, nên tổ hợp này vừa là định danh vừa là ràng buộc.
3. `conversations.type` nhận `direct` hoặc `group`, có `CheckConstraint` ở mức cơ sở dữ liệu.
4. `messages.client_message_id` do client sinh ra, cùng `sender_id` và `conversation_id` tạo thành ràng buộc duy nhất. Đây là cơ chế cho phép gửi lại an toàn khi mất kết nối — xem `docs/RECONNECT_CONTRACT.md`.
5. `messages.source_language` khi ghi là **giá trị tạm** (`preferred_language` của người gửi); node `detect_language` của Agent ghi đè bằng kết quả nhận diện thật (§4.3).
6. `translation_results` có ràng buộc duy nhất `(message_id, target_language)`. Ràng buộc này ép quy tắc "thành viên cùng ngôn ngữ dùng chung một `translation_id`" (§4.4) ở mức schema, đồng thời làm tác vụ dịch chạy nền trở nên idempotent khi phải chạy lại.
7. `translation_results.is_fallback` đúng khi văn bản **không** đến từ LLM đã cấu hình, bao gồm cả trường hợp provider dự phòng dịch thành công. `model` để rỗng khi không tầng nào dịch được và hệ thống trả nguyên bản (`ARCHITECTURE.md` §5.1).
8. **Alembic là nơi duy nhất định nghĩa schema** (sửa 15/08). Ứng dụng không còn tạo bảng lúc khởi động; container chạy `alembic upgrade head` trước `uvicorn`, còn trên máy phát triển là `make migrate`. Đổi schema nghĩa là sinh migration (`make revision m="..."`) rồi đọc lại bản sinh ra. `make reset-db` vẫn còn nhưng nay là `downgrade base` + `upgrade head` và **xoá sạch dữ liệu cục bộ**. Xem ADR-06.
9. `translation_attempts` là **nhật ký đo lường**, không phải trạng thái ứng dụng (ADR-16). Mỗi cặp (tin nhắn × ngôn ngữ đích) được thử ghi một dòng, **kể cả khi không sinh ra bản dịch nào**. Khác `translation_results` ở ba điểm có chủ đích: không có ràng buộc duy nhất (chạy lại là một lượt thử mới, đáng đếm riêng), `translation_id` cho phép `NULL` với `ON DELETE SET NULL` (xoá bản dịch không được xoá bằng chứng rằng đã dịch), và các cột được tự do thay đổi theo nhu cầu đo — **không** thành phần nào ngoài `src/services/metrics.py` và `scripts/report_metrics.py` được đọc bảng này.
10. `translation_attempts.outcome` nhận đúng bảy giá trị, có `CheckConstraint` ở mức cơ sở dữ liệu: `llm`, `secondary`, `original` (ba trường hợp có dòng trong `translation_results`), và `passthrough`, `timeout`, `error`, `empty` (bốn trường hợp không có). Bốn giá trị sau chính là mẫu số còn thiếu: mọi tỷ lệ fallback tính riêng trên các lượt thành công đều không phải là một tỷ lệ.
11. `translation_attempts.source_language_detected` để `NULL` khi nhận diện bị bỏ qua hoặc thất bại. Không được ghi giá trị khai báo vào đây: hai cột sẽ khớp nhau do cách xây dựng, và tỷ lệ đồng thuận của ADR-11 sẽ luôn đọc ra 100% bất kể nhận diện hoạt động thế nào.
12. `translation_edits` là **nhật ký chỉ ghi thêm** (đề xuất, §3.10): không có ràng buộc duy nhất trên `(translation_id, editor_id)` vì góp ý lại là một dòng mới chứ không phải sửa dòng cũ, và bản có hiệu lực là bản `created_at` lớn nhất **của từng người**. Chỉ mục `(translation_id, editor_id, created_at)` để lấy bản mới nhất của người đang gọi mà không quét cả bảng — thứ tự cột đúng theo cách truy vấn, vì mọi lần đọc đều lọc theo cả hai khoá. `editor_id` dùng `ON DELETE CASCADE`: dữ liệu này riêng tư của một người, xoá tài khoản thì xoá theo, không để lại dòng vô chủ mà không ai có quyền đọc. Khác `feedbacks.correction` đúng một điểm: bảng này giữ **toàn bộ lịch sử** góp ý thay vì một dòng mỗi người — cả hai đều riêng tư như nhau. `feedbacks.correction` sẽ **không còn được client ghi vào** kể từ khi giao diện chuyển sang endpoint mới (PR frontend của F-05); tới lúc đó nút bút chì vẫn ghi vào cột cũ. Cột giữ lại vĩnh viễn để đọc dữ liệu đã có.
13. `users.interface_language` (§1.2) `NOT NULL`; migration lấp giá trị ban đầu bằng chính `preferred_language` của từng dòng, nên không tài khoản nào thấy giao diện đổi ngôn ngữ sau khi nâng cấp. Không có ràng buộc khoá ngoại tới danh sách ngôn ngữ: danh sách đó là allowlist ở tầng ứng dụng (`GET /languages`), không phải bảng.
14. `translation_attempts.total_ms` đo bằng wall clock ở tầng service, bao trùm cả truy vấn ngữ cảnh và overhead LangGraph, nên **rộng hơn** `translation_results.latency_ms` (chỉ tính thời gian gọi model). Ngữ nghĩa của `latency_ms` giữ nguyên vì nó đã nằm trong sự kiện WebSocket và REST history; NFR-01 nói về `total_ms`.

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
