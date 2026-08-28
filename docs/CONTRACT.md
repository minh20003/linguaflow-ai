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

Cơ chế lùi về `en` cho từng nhãn còn thiếu (catalog đang áp dụng ở
`frontend/src/features/chat/i18n.ts`) vẫn giữ, nhưng từ nay nó là **lưới an toàn
cho lúc thêm nhãn mới**, không phải cách làm bình thường: thêm một nhãn vào giao
diện mà chưa dịch thì người dùng `ar` thấy đúng dòng đó bằng tiếng Anh chứ không
thấy chuỗi khoá hay màn hình trắng. `frontend-v1/` là cây legacy, không phải
frontend production.

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
    honorific_profile: str        # senior | peer | junior | client — vị thế của
                                  # NGƯỜI ĐỌC, nửa còn lại của khoá fan-out,
                                  # xem §4.4 quy tắc 2
    sender_honorific_profile: str # Cùng bốn giá trị, nhưng là vị thế của NGƯỜI
                                  # GỬI. Rỗng = chưa suy luận. Prompt cần cả hai
                                  # vì xưng hô là quan hệ, không phải thuộc tính
                                  # của một người — xem ghi chú ngay dưới
    translation_tone: str         # natural | formal | casual | friendly — lấy từ
                                  # users_settings.translation_tone của NGƯỜI ĐỌC
                                  # (nửa còn lại của khoá fan-out cùng
                                  # honorific_profile, xem §4.4). Do máy chủ suy ra
                                  # từ cài đặt, không phải văn bản do client tự gõ
    domain: str                   # Lĩnh vực hội thoại, do node customize điền từ
    audience: str                 # conversation_profiles. Rỗng = chưa suy luận,
                                  # khi đó prompt bỏ hẳn mục Audience (§5 ghi chú 15)
    glossary_terms: list          # Thuật ngữ tin nhắn này buộc phải dịch cố định.
                                  # KHÔNG thuộc hợp đồng ở mức khoá bên trong:
                                  # không client nào đọc, và nội dung đổi theo
                                  # glossary (ADR-26)
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

**Vì sao cần cả hai vị thế.** Cách xưng hô là một **quan hệ giữa hai người**, còn `participant_profiles` lại lưu **một** vị thế cho mỗi thành viên trong hội thoại. Hai thứ đó chỉ trùng nhau khi người gửi tình cờ đứng ở đỉnh thang. Trong nhóm ba người A `senior`, B `junior`, C `junior`: khi B nhắn, C vẫn nằm ở bucket `junior` và prompt vẫn phát biểu "người đọc ở vai dưới người gửi", trong khi B và C ngang hàng. Nói cách khác, cách xưng hô C nhìn thấy được suy ra từ thang vị thế của cả hội thoại — mà thang đó chủ yếu do quan hệ A–B dựng nên — chứ không phải từ quan hệ B–C. Đây là lỗi đã ghi ở ADR-23.

`sender_honorific_profile` chữa đúng chỗ đó và **không đụng tới khoá fan-out**: trong phạm vi một tin nhắn, người gửi là cố định, nên mọi người đọc có cùng vị thế tuyệt đối cũng có cùng quan hệ với người gửi. Số bucket vì thế **không đổi**, số lượt gọi LLM **không đổi**, và `translation_results.honorific_profile` vẫn lưu vị thế tuyệt đối của người đọc nên **đường đọc của client không phải sửa gì** (§4.4, §5 ghi chú 6). Trường mới chỉ đi vào prompt, không đi vào cơ sở dữ liệu và không ra sự kiện WebSocket nào.

Rỗng là trạng thái thật, không phải thiếu sót: mọi hội thoại đều ở trạng thái đó cho tới khi có đủ tin nhắn để suy luận (ADR-24). Khi rỗng, prompt lùi về đúng hành vi trước khi có trường này — phát biểu vị thế người đọc một mình — thay vì bịa ra một quan hệ.

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
| `POST` | `/auth/register` | `{"email": str, "password": str, "username": str \| null, "display_name": str \| null, "preferred_language": str}` | `202 Accepted`, `{"pending_id": str, "email": str, "expires_in_seconds": int, "cooldown_seconds": int}`, xem §3.11 | Đã hiện thực |
| `POST` | `/auth/register/verify` | `{"pending_id": str, "otp": str}` | `{"access_token": str, "refresh_token": str, "token_type": "bearer", "user": UserDTO}`, xem §3.11 | Đã hiện thực |
| `POST` | `/auth/register/resend` | `{"pending_id": str}` | `{"pending_id": str, "expires_in_seconds": int, "cooldown_seconds": int}`, xem §3.11 | Đã hiện thực |
| `POST` | `/auth/login` | `{"email": str, "password": str, "remember": bool}` | `{"access_token": str, "refresh_token": str, "token_type": "bearer", "user": UserDTO}` | Đã hiện thực |
| `POST` | `/auth/refresh` | `{"refresh_token": str}` | Như `/auth/login` | Đã hiện thực |
| `POST` | `/auth/logout` | `{"refresh_token": str}` | `204 No Content` | Đã hiện thực |
| `POST` | `/auth/password/forgot` | `{"email": str}` | `{"reset_token": str \| null}`, xem §3.9 | Đã hiện thực |
| `POST` | `/auth/password/reset` | `{"token": str, "password": str}` | `204 No Content` | Đã hiện thực |
| `GET` | `/auth/me` | — | `UserDTO` | Đã hiện thực |
| `PUT` | `/auth/me/language` | `{"preferred_language": str}` | `UserDTO` | Đã hiện thực |
| `PUT` | `/auth/me/interface-language` | `{"interface_language": str}` | `UserDTO`, xem §1.2 | Đã hiện thực |
| `GET` | `/languages` | — | `[str]` | Đã hiện thực |
| `POST` | `/auth/google/login` | `{"credential": str}` | `AuthResponse` | Đã hiện thực |
| `POST` | `/auth/me/google/link` | `{"credential": str}` | `GoogleLinkResponse` | Đã hiện thực |
| `DELETE` | `/auth/me/google/link` | — | `GoogleLinkResponse` | Đã hiện thực |
| `GET` | `/users?q=` | — | `[UserDTO]`, xem §3.1 | Đã hiện thực |
| `POST` | `/conversations` | `{"type": "direct" \| "group", "member_ids": [uuid], "title": str \| null}` | `ConversationDTO`, `201` khi tạo mới và `200` khi dùng lại — xem §3.5 | Đã hiện thực |
| `GET` | `/conversations/{conversation_id}/messages?limit=&before=` | — | `[MessageDTO]` — mảng trần, xem ghi chú §3.2 | Đã hiện thực |
| `POST` | `/translations/{translation_id}/feedback` | `{"rating": int, "correction": str \| null}` | `{"feedback_id": uuid}` | Đã hiện thực |
| `POST` | `/translations/{translation_id}/edits` | `{"edited_text": str, "consent_to_share": bool}` | `TranslationEditDTO`, xem §3.10 | Đã hiện thực |
| `PATCH` | `/conversations/{conversation_id}/messages/{message_id}` | `{"text": str}` | `MessageDTO`, xem §3.6 | Đã hiện thực |
| `DELETE` | `/conversations/{conversation_id}/messages/{message_id}` | — | `204 No Content` | Đã hiện thực |
| `POST` | `/conversations/{conversation_id}/attachments` | `multipart/form-data`, trường `file` | `AttachmentDTO`, xem §3.7 | Đã hiện thực |
| `GET` | `/conversations/{conversation_id}/attachments/{attachment_id}` | — | Nội dung tệp | Đã hiện thực |
| `POST` | `/messages/{message_id}/transcription/retry` | — | `202`, `{"message_id", "conversation_id", "transcription_status":"pending", "status":"scheduled"}` | Đã hiện thực; chỉ retry voice `failed` còn audio hợp lệ |
| `POST` | `/conversations/{conversation_id}/read` | — | `{"unread_count": 0}` | Đã hiện thực |
| `GET` | `/conversations` | — | `[ConversationDTO]`, xem §3.5 | Đã hiện thực |
| `GET` | `/stats?days=` | — | Xem §3.4 | Đã hiện thực |
| `GET` | `/admin/glossary/proposals?status=&limit=` | — | `[GlossaryProposalDTO]`, §3.12 | Đã hiện thực |
| `POST` | `/admin/glossary/proposals/{proposal_id}/approve` | `{"source_term"?, "target_term"?, "domain"?, "audience"?, "keep_verbatim"?}` | `GlossaryEntryDTO`, `201` — §3.12 | Đã hiện thực |
| `POST` | `/admin/glossary/proposals/{proposal_id}/reject` | `{"reason": str}` | `GlossaryProposalDTO`, §3.12 | Đã hiện thực |
| `GET` | `/admin/glossary?include_retired=&limit=` | — | `[GlossaryEntryDTO]`, §3.12 | Đã hiện thực |
| `POST` | `/admin/glossary` | `{"source_term", "target_term", "source_language", "target_language", "domain"?, "audience"?, "keep_verbatim"?}` | `GlossaryEntryDTO`, `201` — §3.12 | Đã hiện thực |
| `PATCH` | `/admin/glossary/{entry_id}` | `{"source_term"?, "target_term"?, "domain"?, "audience"?, "keep_verbatim"?}` | `GlossaryEntryDTO`, §3.12 | Đã hiện thực |
| `DELETE` | `/admin/glossary/{entry_id}` | — | `GlossaryEntryDTO` với `status = "retired"`, §3.12 | Đã hiện thực |
| `POST` | `/admin/glossary/{entry_id}/restore` | — | `GlossaryEntryDTO` với `status = "active"`, §3.12 | Đã hiện thực |
| `DELETE` | `/admin/glossary/{entry_id}/permanent` | — | `GlossaryEntryDTO` của dòng vừa bị xoá, `409` nếu mục còn `active` — §3.12 | Đã hiện thực |
| `GET` | `/admin/feedback?limit=` | — | `FeedbackOverviewDTO`, §3.14 | Đã hiện thực |
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
  "google_linked": false,
  "has_password": true,
  "created_at": "2026-08-10T09:00:00Z"
}
```

Trường `interface_language` (§1.2) **không bao giờ null**: tài khoản tạo trước khi có nó nhận giá trị bằng `preferred_language` của chính mình lúc migrate, nên giao diện của họ không đổi sau khi nâng cấp.

Hai trường `username` và `display_name` **không bao giờ null trong phản hồi**: tài khoản tạo trước khi có hai trường này được lấp bằng phần trước dấu `@` của email, nên client luôn có thứ để hiển thị.

Trường `google_linked` (`bool`) biểu thị trạng thái tài khoản đã liên kết Google (`google_sub` tồn tại) hay chưa. Trường định danh nội bộ `google_sub` **không bao giờ** xuất hiện trong phản hồi API để bảo vệ quyền riêng tư người dùng.

Trường `has_password` (`bool`) biểu thị tài khoản có mật khẩu thiết lập hay không (`true` nếu có mật khẩu, `false` nếu là tài khoản tạo thuần qua Google chưa đặt mật khẩu). Trường mật khẩu băm `password_hash` **không bao giờ** xuất hiện trong phản hồi API.

**Tìm người dùng — `GET /users?q=`.** Tham số `q` tối thiểu 2 ký tự, khớp **tiền tố, không phân biệt hoa thường** trên `email`, `username` và `display_name`; riêng `display_name` khớp tiền tố của **bất kỳ từ nào** (gõ `an` tìm ra `Nguyễn An`). Trả về tối đa 20 kết quả, sắp xếp theo `email`, và **không bao giờ chứa chính người gọi**. Không tìm thấy ai là mảng rỗng chứ không phải `404` — `404` sẽ lẫn với lỗi sai đường dẫn.

Khớp tiền tố chứ không phải khớp giữa chuỗi: tìm giữa chuỗi biến endpoint này thành công cụ quét danh bạ (gõ `a` ra gần như mọi tài khoản). Endpoint yêu cầu đăng nhập, nhưng người đã đăng nhập vẫn dò được sự tồn tại của một địa chỉ — chấp nhận ở giai đoạn này vì chưa có giới hạn tần suất; xem `docs/DEPLOY.md`.

### 3.2. Google Authentication Provider

**GoogleLinkResponse**

```json
{
  "google_linked": true,
  "message": "Google account linked successfully."
}
```

**Quy tắc định danh và xác thực Google (Batch G):**

Google hoạt động như một nhà cung cấp xác thực đầy đủ (Full Authentication Provider) kết hợp cả đăng nhập và tạo tài khoản mới:

1. **Đăng nhập và Đăng ký qua Google (`POST /auth/google/login`):**
   * Token Google phải vượt qua kiểm tra chữ ký server-side, đúng audience (`GOOGLE_OAUTH_CLIENT_ID`), đúng issuer, chưa hết hạn, và **bắt buộc `email_verified == true`**.
   * **Phân giải định danh (Identity Resolution):**
     * **Trường hợp 1 (`google_sub` trùng khớp):** Đăng nhập ngay vào tài khoản tương ứng, trả về `AuthResponse`.
     * **Trường hợp 2 (Chưa khớp `google_sub` nhưng trùng `email` đã xác thực):**
       * Nếu tài khoản hiện có chưa liên kết Google (`google_sub` là `NULL`): Tự động liên kết `google_sub`, bảo toàn nguyên vẹn `password_hash` và toàn bộ dữ liệu tài khoản, đăng nhập thành công.
       * Nếu tài khoản hiện có đã liên kết với một tài khoản Google khác: Trả về `409 Conflict` (ngăn chặn việc tự động đổi liên kết).
     * **Trường hợp 3 (Chưa có `google_sub` và chưa có `email`):**
       * Tự động tạo tài khoản Google-native mới: `email = verified_email`, `google_sub = token.sub`, `password_hash = NULL`, `role = member`, ngôn ngữ mặc định `en`.
       * Đăng nhập thành công và trả về `AuthResponse` ngay lập tức.
   * **Token không hợp lệ hoặc `email_verified == false`:** Trả về `401 Unauthorized`.

2. **Liên kết tài khoản từ Cài đặt (`POST /auth/me/google/link`):**
   * Cho phép người dùng đã đăng nhập liên kết tài khoản Google một cách tường minh (hỗ trợ cả trường hợp email Google khác với email LinguaFlow).
   * Yêu cầu xác thực (`Authorization: Bearer <token>`).
   * Trả về `409 Conflict` nếu tài khoản hiện tại đã liên kết hoặc `google_sub` đã bị tài khoản khác sử dụng.
   * Trả về `200 OK` với `{"google_linked": true, "message": "Google account linked successfully."}` khi thành công.

3. **Hủy liên kết tài khoản (`DELETE /auth/me/google/link`):**
   * Yêu cầu xác thực (`Authorization: Bearer <token>`).
   * **Bảo vệ tài khoản:** Nếu tài khoản là Google-native (`password_hash` là `NULL`), hệ thống từ chối hủy liên kết và trả về `409 Conflict` (`"Cannot unlink Google account without a password. Please set a password first."`) để tránh làm người dùng mất phương thức đăng nhập duy nhất.
   * Nếu tài khoản đã có mật khẩu: Xóa `google_sub`, trả về `200 OK` với `{"google_linked": false, "message": "Google account unlinked successfully."}`.
   * Idempotent: Nếu tài khoản chưa từng liên kết Google, luôn trả về `200 OK` với `google_linked: false`.

4. **Đăng nhập bằng mật khẩu đối với tài khoản Google-native:**
   * Tài khoản có `password_hash = NULL` khi thử đăng nhập bằng email/mật khẩu tại `POST /auth/login` sẽ luôn nhận phản hồi chuẩn `401 Unauthorized` (`"Invalid email or password"`), không tiết lộ loại tài khoản và không gây lỗi crash.

### 3.3. MessageDTO

```json
{
  "id": "uuid",
  "conversation_id": "uuid",
  "sender_id": "uuid",
  "client_message_id": "uuid-or-client-id",
  "original_text": "string",
  "message_type": "text",
  "transcription_status": null,
  "source_language": "vi",
  "created_at": "2026-08-10T09:00:00Z",
  "translations": [
    {
      "translation_id": "uuid",
      "target_language": "en",
      "honorific_profile": "peer",
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

Trường `honorific_profile` nhận một trong bốn giá trị `senior`, `peer`, `junior`, `client` và **bắt buộc phải đọc cùng `target_language`**: kể từ khi ràng buộc duy nhất của `translation_results` mở rộng sang ba cột (§5 ghi chú 6), một tin nhắn có thể có nhiều bản dịch cùng một ngôn ngữ đích, khác nhau ở cách xưng hô. Client chọn bằng **cặp** `(target_language, honorific_profile)` chứ không bằng ngôn ngữ. Chọn bằng ngôn ngữ thôi sẽ lấy phải phần tử đầu tiên tình cờ gặp — thứ tự do kế hoạch truy vấn quyết định, nên hỏng theo kiểu im lặng và không tất định.

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
  "models_served": {"llama-3.3-70b-versatile": 104},
  "model_usage": {
    "llama-3.3-70b-versatile": {
      "count": 104, "input_tokens": 24800, "output_tokens": 1960,
      "input_price_per_million_usd": 0.59, "output_price_per_million_usd": 0.79,
      "cost_usd": 0.0161
    }
  },
  "total_cost_usd": 0.0161,
  "cost_usd_partial": false,
  "language_pairs": {"vi->en": {"count": 60, "p50_ms": 780, "p95_ms": 1430}},
  "input_tokens": 24800,
  "output_tokens": 1960,
  "total_ms_mean": 895,
  "total_ms_p50": 810,
  "total_ms_p95": 1520
}
```

Endpoint **chỉ dành cho quản trị viên**: nội dung không chứa văn bản tin nhắn và không có dữ liệu theo từng người dùng, nhưng có lộ lưu lượng toàn hệ thống và mức tiêu thụ token. Chỉ tài khoản có `role == "admin"` được đọc; thành viên nhận `403 Forbidden`.

`fallback_rate` là `(secondary + original) / total_attempts`, tính trên **toàn bộ** lượt thử — xem §5 ghi chú 10. `total_attempts`, `outcomes` và `fallback_rate` vì thế vẫn tính cả `passthrough`: đó chính là mẫu số ADR-16 tồn tại để bảo toàn.

**`language_pairs` và `total_ms_p50`/`total_ms_p95` thì không, theo ngôn ngữ chứ không theo `outcome` (24/08).** Một dòng có ngôn ngữ đọc trùng ngôn ngữ của tin nhắn không phải là một bản dịch, bất kể dòng đó cuối cùng ghi `outcome` gì. `passthrough` là đường thường gặp nhất — rẽ nhánh trước `build_context`, không model nào, không API dự phòng nào từng chạy — nhưng một bucket cùng ngôn ngữ lỡ `timeout` hay `error` trước khi kịp rẽ nhánh cũng vô nghĩa y hệt: cả hai đều sẽ ra một dòng `"vi->vi"` và một loạt `total_ms` gần 0 kéo tụt độ trễ tổng cho việc không ai thử làm, nên phép loại dựa trên **so sánh hai ngôn ngữ**, không dựa trên `outcome == "passthrough"`. Một `timeout`/`error` giữa hai ngôn ngữ thật (`en->vi` chẳng hạn) không bị loại: có thử và có tốn thời gian thật trước khi hỏng.

**`models_served` bỏ luôn ô `"(none)"` (24/08).** Bất kỳ dòng nào không ghi được tên model — dù cùng ngôn ngữ hay khác ngôn ngữ, dù `outcome` gì — thì không có gì để tính vào chỉ số này, vì nó vốn trả lời "model nào đã phục vụ", không phải "có bao nhiêu lượt thử". Một `timeout` giữa `en->vi` do đó vẫn có mặt trong `language_pairs` (thời gian đã tốn là thật) nhưng không góp mặt trong `models_served` (không ai biết model nào đang chạy dở).

**`model_usage`, `total_cost_usd` và `cost_usd_partial` (thêm 24/08).** Đọc `src/services/llm_pricing.py` — bảng đơn giá **gõ tay, không lấy trực tiếp từ nhà cung cấp**, nên là con số tham khảo chứ không phải hoá đơn; đọc lại docstring của module đó trước khi trích dẫn con số này với ai định dựa vào nó. Mỗi mục trong `model_usage` gồm số lượt, tổng token vào/ra, và `cost_usd` — **`null` khi model đó chưa có đơn giá trong bảng**, cố tình không mặc định về 0, vì một model không có giá thì khác hẳn một model miễn phí. `total_cost_usd` chỉ cộng những model **có** giá; `cost_usd_partial = true` khi có ít nhất một model bị bỏ ngoài tổng đó, để client nói "tối thiểu ngần này" thay vì ngụ ý con số đã đầy đủ.

**`total_ms_mean` đứng cạnh `total_ms_p50` (thêm 24/08).** Hai con số khác nhau và dễ lẫn: `total_ms_mean` là trung bình cộng — cộng hết chia số lượt, dễ bị vài lượt bất thường kéo lệch. `total_ms_p50` là **trung vị** — lượt đứng chính giữa khi xếp theo thời gian, một nửa nhanh hơn và một nửa **chậm hơn** nó, **không phải** trung bình của nửa nhanh nhất. Hai số này trùng nhau khi độ trễ phân bố đối xứng và tách xa nhau ngay khi có vài lượt bất thường rất chậm — hiện cả hai là cách duy nhất để thấy sự tách đó thay vì âm thầm chọn một trong hai.

### 3.5. ConversationDTO

Mỗi phần tử của `members` mang thêm `honorific_profile` (§5 ghi chú 15). Đây là nơi client
đọc ra vị thế **của chính mình** trong hội thoại, thứ cần có để chọn đúng phần tử trong
mảng `translations` của §3.2. Giá trị theo từng hội thoại chứ không theo tài khoản: cùng
một người là `junior` với quản lý của mình và là `client` trong hội thoại với nhà cung cấp.
`TranslationEditDTO` ở §3.10 cũng mang thêm trường này, cùng một lý do — nó vốn đã mang
`target_language`, mà từ nay ngôn ngữ một mình không định danh được bản dịch.

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

`ConversationDTO` còn mang `last_message_type` và
`last_message_transcription_status`. Với voice `pending`/`failed`, server giữ
`last_message` rỗng đúng dữ liệu bền vững và frontend hiển thị nhãn i18n “Voice
message”; không ghi placeholder vào message. Với voice `completed`, quy tắc
preview bản dịch/`original_text` ngay dưới đây được dùng y hệt text. Timestamp,
unread và ordering không đổi.

**Tin mới nhất đã bị gỡ không được dùng làm preview.** Danh sách hội thoại trả về tin nhắn còn hiển thị gần nhất trước đó; chỉ trả `null` khi không còn tin nhắn nào. Nhờ vậy dòng xem trước luôn khớp với nội dung người dùng vẫn có thể mở trong hội thoại.

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

#### 3.7.1. Voice message ghi âm

Voice là **tin nhắn ghi âm**, không phải media của cuộc gọi. Client tải audio qua
endpoint attachment có xác thực, sau đó gửi `send_voice_message` (§4.1). Server
không tin `sender_id`, `message_type` hay lifecycle do client đưa lên: danh tính
đến từ JWT; attachment phải thuộc cùng hội thoại, do đúng người gửi upload, chưa
được claim và có MIME/container audio hợp lệ. Việc tạo Message và claim attachment
là một transaction.

Các invariant bền vững:

| `message_type` | `transcription_status` | `original_text` |
|---|---|---|
| `text` | `null` | nội dung text khác rỗng |
| `voice` | `pending` | `""` |
| `voice` | `completed` | transcript nguyên ngôn ngữ, khác rỗng |
| `voice` | `failed` | `""` |

Gemini 3.5 Transcribe chỉ làm STT ở `mode=verbatim`, tự phát hiện ngôn ngữ; file
provider là bản sao tạm và bị xoá best-effort. WebM/Opus, OGG/Opus và MP4/AAC
từ MediaRecorder được giữ nguyên trong attachment; backend có thể chuyển mã tạm
sang FLAC chỉ để gửi STT. Audio, filename, MIME và URI provider không bao giờ đi
vào Translation Agent. Chỉ sau commit `pending → completed`, các service
text-dependent hiện có mới đọc lại `Message.original_text` và chạy pipeline dịch,
context, glossary, tone/honorific, commitment/profile/embedding như text.

Retry chỉ dành cho thành viên hiện tại, message chưa xoá, `message_type=voice`,
`transcription_status=failed` và attachment gốc vẫn gắn đúng message. Nó dùng lại
cùng message/audio và guarded update `failed → pending`; chỉ request thắng update
mới khởi chạy detached STT task. History REST là nguồn phục hồi sau refresh hoặc
bỏ lỡ event, không cần replay event. Các nhãn “Voice message”, “Transcribing…” và
“Transcription unavailable” chỉ là i18n UI, không được ghi vào `original_text`.

### 3.8. Đếm chưa đọc

`ConversationDTO` mang thêm `unread_count`: số tin nhắn **của người khác** tạo sau mốc `conversation_members.last_read_at` của tài khoản đang gọi. Tin do chính mình gửi không bao giờ được tính là chưa đọc, và tin đã gỡ cũng vậy.

`POST /conversations/{id}/read` đặt mốc đó về thời điểm hiện tại và trả về `{"unread_count": 0}`. Server phát tiếp sự kiện `message_read` (§4.2) để phía người gửi đổi dấu đã gửi thành đã xem.

### 3.9. Đặt lại mật khẩu

`POST /auth/password/forgot` **luôn** trả `200` kèm cùng một câu trả lời chung, dù địa chỉ có tồn tại hay không — trả `404` cho địa chỉ lạ sẽ biến endpoint này thành công cụ dò tài khoản không cần đăng nhập. Với tài khoản tồn tại, server tạo một token dùng một lần, vô hiệu hoá các token reset còn mở trước đó, rồi gửi liên kết `FRONTEND_URL/reset-password?token=...` bằng SMTP. Liên kết dùng ngôn ngữ giao diện đã lưu của tài khoản.

Trường `reset_token` trong phản hồi chỉ có giá trị khi `APP_ENV=development`, để lập trình viên chạy trọn luồng mà không cần SMTP. **Ở mọi môi trường khác, trường này là `null`; token không bao giờ được ghi vào log server.** Nếu SMTP gặp sự cố, server chỉ ghi lỗi vận hành an toàn và vẫn trả phản hồi chung để không biến lỗi gửi mail thành kênh dò tài khoản.

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

**`consent_to_share` (thêm 20/08, đổi cách hỏi 24/08).** Trường vẫn nằm nguyên trong thân yêu cầu và server vẫn xử đúng cả hai giá trị — `false` là trạng thái có thật, và một client khác vẫn gửi được. Đổi là ở chỗ **hỏi thế nào**: giao diện chat không còn ô tích riêng mà đặt ngay dưới ô soạn một câu nói rõ rằng gửi góp ý đồng nghĩa với đồng ý chia sẻ tin nhắn này để cải thiện hệ thống, và gửi kèm `true`. Lý do là số liệu chứ không phải tiện tay: gần như không ai tích ô đó, nên miner gần như không nhận được gì và hàng đợi duyệt trống — một cơ chế đồng ý không ai dùng thì không bảo vệ được ai mà cũng chẳng dạy được điều gì. Câu thông báo vì thế phải đứng **trước** nút gửi, lúc quyết định còn mở. Khi `true`, ngoài dòng `translation_edits` như cũ, hệ thống ghi thêm **một bản dẫn xuất hẹp hơn nhiều** vào `correction_log`: cụm từ máy dùng, cụm người dùng thay vào, vài từ xung quanh cụm đó trong bản dịch của máy, và vài từ đầu câu người gửi thực sự viết (`original_snippet`, thêm 24/08) — tất cả đã bỏ email, link, dãy số dài. Chỉ bản dẫn xuất đó mới được khai thác để đề xuất glossary (ADR-28); `translation_edits` **vẫn riêng tư tuyệt đối với người viết** đúng như ADR-19 quy định, và không quy trình nào đọc nó. Cờ này khoá **cả dòng** `correction_log` chứ không riêng phần trích dẫn: đếm một bản sửa mà người ta không đồng ý chia sẻ thì vẫn là đang dùng nó.

**Góp ý nhiều lần.** Mỗi lần gọi ghi thêm một dòng vào `translation_edits`, không ghi đè. Bản có `created_at` mới nhất **của chính người đó** là bản có hiệu lực và là bản duy nhất xuất hiện trong `MessageDTO`; các bản trước vẫn nằm trong bảng, dành cho tính năng quản trị về sau. Không có endpoint xoá.

**Bản máy dịch không bao giờ bị ghi đè.** `translation_results.translated_text` giữ nguyên văn bản LLM sinh ra. Đây là điều kiện để so sánh người với máy, nên client **không** được coi bản góp ý là bản dịch mới của hệ thống.

**Hiển thị.** Bóng chat luôn hiện `translated_text`. Bản góp ý của chính mình nằm sau nút bút chì: bấm để mở, bấm lần nữa để đóng. Người dùng vì thế đối chiếu được hai bản, thay vì bị thay thầm nội dung đang đọc.

`404` khi `translation_id` không tồn tại; `409` khi tin nhắn tương ứng đã bị gỡ (§3.6).

### 3.11. Xác thực đăng ký tài khoản qua Email OTP (Batch F)

Quy trình đăng ký tài khoản được bảo vệ qua 2 bước bằng mã OTP gửi về email:

1. **Bước 1: Khởi tạo yêu cầu (`POST /api/v1/auth/register`)**
   - Payload: `{"email": str, "password": str, "username": str, "display_name": str, "preferred_language": str}`.
   - Server kiểm tra trùng lặp email/username (`409 Conflict`), mã hóa mật khẩu và sinh mã OTP 6 chữ số ASCII (`^[0-9]{6}$`).
   - Lưu vào bảng `pending_registrations` (chỉ lưu bcrypt hash của OTP, không bao giờ lưu OTP thô).
   - Bảo toàn ngôn ngữ: lưu đồng thời `preferred_language` và `interface_language` (hỗ trợ đầy đủ 14 ngôn ngữ).
   - Gửi email chứa mã OTP được bản địa hóa theo ngôn ngữ đã chọn.
   - Trả về mã **`202 Accepted`**:
     ```json
     {
       "pending_id": "uuid",
       "email": "user@example.com",
       "expires_in_seconds": 300,
       "cooldown_seconds": 60,
       "message": "Verification code sent to your email"
     }
     ```
   - **Tuyệt đối không tạo tài khoản `User` hoặc phiên làm việc `RefreshSession` tại bước này.**
   - **Lỗi gửi email**: Nếu delivery thất bại (`EmailDeliveryError`), trả về HTTP `500` với mã machine-readable `{"detail": "email_delivery_failed"}` và không hoàn tác (rollback) lượt đếm rate limit đã commit.

2. **Bước 2: Xác nhận OTP (`POST /api/v1/auth/register/verify`)**
   - Payload: `{"pending_id": str, "otp": str}` (OTP bắt buộc đúng 6 chữ số ASCII).
   - Thời hạn hiệu lực: chính xác 5 phút (300 giây) kể từ thời điểm phát hành mã gần nhất.
   - Giới hạn số lần thử: tối đa 3 lần sai (`attempts < 3`); lần thứ 3 sai sẽ khóa phiên đăng ký đó vĩnh viễn (`400 Bad Request`).
   - Khi mã hợp lệ: thực hiện claim nguyên tử bằng câu lệnh SQL conditional `DELETE ... RETURNING`, tạo tài khoản `User` và cấp phát phiên đăng nhập `AuthResponse` (`access_token`, `refresh_token`, `user`) trong cùng **1 database transaction duy nhất**.
   - Mã OTP là **dùng một lần (single-use)**; gọi lại với cùng `pending_id` sẽ trả về `400 Bad Request`.

3. **Gửi lại mã OTP (`POST /api/v1/auth/register/resend`)**
   - Payload: `{"pending_id": str}`.
   - Áp dụng Cooldown: tối thiểu 60 giây giữa các lần gửi (`429 Too Many Requests` kèm header `Retry-After`).
   - Rate limit: tối đa 5 lần gửi OTP trong vòng 1 giờ cho cùng một phiên đăng ký (`request_count < 5`).
   - Khi gửi lại thành công: cập nhật nguyên tử `otp_hash` mới, vô hiệu hóa hoàn toàn mã OTP cũ, đặt lại bộ đếm số lần thử `attempts = 0`, gia hạn `expires_at` thêm 5 phút và gửi email bằng `interface_language` đã lưu.
   - Trả về mã **`200 OK`**:
     ```json
     {
       "pending_id": "uuid",
       "expires_in_seconds": 300,
       "cooldown_seconds": 60,
       "message": "New verification code sent to your email"
     }
     ```
   - Nếu delivery thất bại (`EmailDeliveryError`), trả về `500` với `{"detail": "email_delivery_failed"}` nhưng vẫn bảo toàn bản ghi `request_count` và cooldown đã commit trong DB.

### 3.12. Glossary và hàng đợi duyệt (chỉ quản trị viên)

Mọi endpoint dưới tiền tố `/admin/` đều gác bằng `get_admin_user`; tài khoản `member`
nhận `403 Forbidden`. Gác đặt trên **từng** endpoint chứ không dựa vào tiền tố đường dẫn:
`users.role` so với chuỗi `"admin"` là toàn bộ mô hình phân quyền của dự án (§5 ghi chú 1),
không có middleware nào đứng sau, nên một dependency bị quên trông y hệt mã đang chạy đúng.

**`GlossaryProposalDTO` cố ý không mang gì hơn.** Nó có cặp thuật ngữ, `occurrence_count`,
`distinct_user_count`, `rationale`, và các `citations` đã ẩn danh — **không** có người gửi,
**không** có `conversation_id`, **không** có `message_id`. Quản trị viên bị cấm đọc nội dung
hội thoại (`docs/NewFeature.md` sơ đồ 2), và cách giữ điều đó thành sự thật là để DTO
**không có chỗ nào đặt những thứ ấy vào**. Trong hai con số, `distinct_user_count` mới là
con số để phán xét: năm lần sửa của một người là sở thích cá nhân, hai lần của hai người là
một quy ước đang hình thành (ADR-28).

**`GlossaryProposalDTO` mang thêm hai trường về trạng thái hiện có của glossary (22/08):**
`similar_entries` là danh sách các mục **đã có** cùng thuật ngữ nguồn và cùng cặp ngôn ngữ —
mỗi mục gồm `id`, `source_term`, `target_term`, `domain`, `audience`, `status` — và
`conflicts_with_active` là `true` khi trong số đó có một mục **đang `active` với bản dịch
khác**. Hai trường này trả lời đúng hai câu người duyệt cần: *đã có bao nhiêu cụm giống*, và
*bản dịch hiện tại đã dùng đúng chưa*. Nếu `conflicts_with_active` là `true` thì máy vẫn
đang dịch thuật ngữ này **đúng theo glossary hiện hành**, và đề xuất là yêu cầu **đổi** câu
trả lời chứ không phải bổ sung một câu còn thiếu — hai quyết định khác hẳn nhau mà hàng đợi
trước đây hiển thị y như nhau. Không có trường nào ở đây rò nội dung hội thoại: tất cả đều
đọc từ chính bảng `glossary_entries`.

**Đối sánh bằng thuật ngữ đã chuẩn hoá, không bằng embedding.** Đây là lựa chọn có số liệu
chứ không phải cho nhanh: đo trên chính bộ thuật ngữ của dự án, model embedding khả dụng
chấm một biến thể đúng và một từ không liên quan lệch nhau **0.002** (ADR-26), nên một ngưỡng
tương đồng ở đây chỉ làm màn hình người duyệt đầy nhiễu tự tin. Đối sánh chuẩn hoá hẹp hơn
nhưng **đúng**, và một màn hình sinh ra để ngăn một lần duyệt sai thì cần đúng.

**Duyệt được phép sửa đề xuất ngay lúc duyệt.** Câu trả lời của miner đến từ một model đọc
các đoạn trích ẩn danh; người duyệt mới là người biết đội mình thật sự nói thế nào. Bắt họ
từ chối rồi thêm tay lại một thuật ngữ gần đúng là cách nhanh nhất để hàng đợi không còn ai
làm.

**Từ chối bắt buộc có lý do**, và dòng bị từ chối **giữ lại vĩnh viễn** kèm embedding: đó là
thứ để miner nhận ra cùng thuật ngữ đó tuần sau viết khác đi và không hỏi lại (ADR-28). Vài
tháng sau sẽ có người muốn biết vì sao một thuật ngữ trông rất hợp lý lại không bao giờ vào
được, và chữ "rejected" một mình không trả lời được.

**Quyết định hai lần trên cùng một đề xuất trả `409 Conflict`**, không phải `200`. Hai người
cùng làm hàng đợi sẽ đều tin mình là người đã duyệt, và quyết định sau âm thầm ghi đè quyết
định trước — kể cả lý do của nó.

**`DELETE /admin/glossary/{id}` không xoá.** Nó đổi `status` thành `retired`. Một bản dịch
giao tháng trước được định hình bởi thuật ngữ đang active lúc đó; xoá dòng là xoá mất lời
giải thích duy nhất cho câu chữ người đọc đang nhìn. Nghỉ hưu thì nó thôi định hình những
bản dịch mới (§5 ghi chú 16).

**`keep_verbatim = true` nghĩa là thuật ngữ không được dịch**, và prompt khi đó ghi
`"<thuật ngữ>": leave untranslated, exactly as written` chứ **không** đọc tới `target_term`.
Cột `target_term` vẫn `NOT NULL` nên vẫn phải có giá trị, và quy ước — do chính prompt đề xuất
thuật ngữ đặt ra — là **lặp lại đúng thuật ngữ nguồn**. Màn hình quản trị vì thế tự điền và khoá
ô bản dịch khi ô "giữ nguyên" được tích: trước 22/08 biểu mẫu vẫn đòi một bản dịch mà nó sắp
bỏ qua, và không có gì trên màn hình nói ra điều đó.

**`DELETE /admin/glossary/{id}/permanent` xoá thật, và chỉ xoá được mục đã nghỉ hưu (24/08).**
Server trả `409 Conflict` cho một mục còn `active`: mục đang có hiệu lực thì theo định nghĩa
là đang định hình bản dịch, nên câu trả lời cho "xoá cái này" luôn là "cho nghỉ hưu trước đã
rồi xem". Phần còn lại mới là việc endpoint này làm: một thuật ngữ gõ nhầm chưa từng định
hình gì thì cũng không giải thích được gì, mà dòng của nó vẫn giữ chỗ trong ràng buộc duy
nhất `(source_term, source_language, target_language, domain, audience)` — thêm lại bản đã
sửa sẽ nhận `409` chừng nào dòng cũ còn đó. Phản hồi là dòng **trước khi** bị xoá, vì sau lời
gọi này không còn chỗ nào tra lại. Hai bước hỏi trên giao diện quản trị là một phần của thiết
kế chứ không phải trang trí: đây là thao tác duy nhất trong màn hình không hoàn tác được.

**`POST /admin/glossary/{id}/restore` là chiều ngược lại của việc nghỉ hưu (22/08).** Vì
không có gì bị xoá nên khôi phục chỉ là đổi `status` về `active`: mục giữ nguyên `id`,
embedding và ngày được duyệt lần đầu, thay vì được tạo lại thành một dòng thứ hai mà người
đọc phải đối chiếu mới biết máy đang dùng dòng nào.

**`PATCH /admin/glossary/{id}` sửa một mục đang có hiệu lực (22/08).** Chỉ những trường được
gửi mới thay đổi, nên một màn hình chưa biết tới cột thêm về sau không thể xoá trắng cột đó
bằng cách bỏ sót. **Cặp ngôn ngữ không sửa được**: một mục sai cặp ngôn ngữ là một mục khác
chứ không phải một mục gõ nhầm, và cả embedding lẫn ràng buộc duy nhất đều gắn với cặp ấy.
Khi `source_term` đổi, server **tính lại embedding** — không có vector mới thì tầng khớp ngữ
nghĩa vẫn khớp theo cách viết cũ, im lặng, và triệu chứng duy nhất là một thuật ngữ bỗng
không còn được tìm thấy. Sửa được là cần thiết vì phương án còn lại tệ hơn: sửa một lỗi gõ
bằng cách cho mục cũ nghỉ hưu rồi thêm một mục gần giống sẽ để lại hai dòng vĩnh viễn.

### 3.13. Tin nhắn đã lưu (Saved Messages)

Quản lý danh sách tin nhắn được người dùng đánh dấu/lưu trữ (bookmark):

- **Lưu/bỏ lưu:** `PUT /conversations/{conversation_id}/messages/{message_id}/saved` và `DELETE /conversations/{conversation_id}/messages/{message_id}/saved` trả về `SavedMessageStateResponse` (`{"message_id": str, "is_saved": bool}`).
- **Danh sách tin đã lưu:** `GET /api/v1/saved-messages` (hỗ trợ phân trang qua `limit`, `before_created_at`, `before_id`).
- Phản hồi dạng `SavedMessagesResponse`:
  ```json
  {
    "items": [
      {
        "id": "uuid",
        "conversation_id": "uuid",
        "sender_id": "uuid",
        "original_text": "string",
        "source_language": "vi",
        "translations": [],
        "created_at": "2026-08-24T07:00:00Z",
        "is_saved": true,
        "reactions": []
      }
    ],
    "has_more": false,
    "next_before_created_at": null,
    "next_before_id": null
  }
  ```

### 3.14. Tổng quan góp ý của người đọc (chỉ quản trị viên, 24/08)

`GET /admin/feedback?limit=` trả về **một** phản hồi cho cả tab góp ý, thay vì nhiều endpoint:
thống kê và các hàng kiểm tra đều được đọc cùng lúc, nên màn hình không có nhiều vòng quay chờ.

```json
{
  "votes": {
    "up": 12,
    "down": 3,
    "total": 16,
    "up_rate": 0.75,
    "ratings": {"5": 12, "3": 1, "1": 3}
  },
  "review_entries": [
    {
      "entry_type": "edit",
      "original_text": "Deploy xong chưa anh?",
      "translated_text": "Is the deploy done?",
      "source_language": "vi",
      "target_language": "en",
      "model": "gemini-3.7-flash",
      "vote": null,
      "rating": null,
      "user_correction": "Is the deployment finished yet?",
      "created_at": "2026-08-24T09:04:00Z"
    }
  ],
  "shared_corrections": [
    {
      "source_phrase": "staging environment",
      "corrected_target": "môi trường staging",
      "source_language": "en",
      "target_language": "vi",
      "domain": "engineering",
      "audience": "internal",
      "original_snippet": "Can you deploy to the staging …",
      "anonymized_snippet": "… deploy lên staging environment trước …",
      "observed_at": "2026-08-24T09:04:00Z"
    }
  ],
  "shared_total": 41,
  "withheld_total": 7
}
```

**`votes` là histogram của `feedbacks.rating`.** Giao diện chỉ gửi 5 cho ngón cái lên và 1 cho
ngón cái xuống, nên **chỉ hai ô đó được gọi tên**. Không có ô `neutral` (bỏ 24/08): giao diện
không có lựa chọn thứ ba nào để bấm, nên một con số luôn bằng 0 hiện trên màn hình chỉ khiến
người đọc tưởng đó là một ý kiến có thật. Mọi giá trị ngoài 5 và 1 vẫn đếm được trong
`ratings` — histogram 1–5 nguyên vẹn — và đó chính là cách một thay đổi của giao diện tự lộ ra.
`total` là tổng mọi lượt đánh giá nên có thể lớn hơn `up + down`. `up_rate` làm tròn 4 chữ số,
bằng 0 khi chưa có lượt nào.

**`shared_corrections` chỉ gồm các dòng `correction_log` có `consent_to_share = true`,** mới
nhất trước, cắt theo `limit`. Mỗi dòng đúng bằng những cột miner đọc, và đó chính là điểm của
màn hình này: trước khi có nó, đầu ra nhìn thấy được của cả đường ống góp ý chỉ là một đề xuất
— thứ chỉ xuất hiện khi đã có vài người độc lập sửa giống nhau — nên mọi thứ dưới ngưỡng ấy
đều vô hình, kể cả trường hợp không có gì đang chảy về.

**`review_entries` là bảng kiểm tra chất lượng nội bộ, mới nhất trước và cắt theo `limit`.**
Mỗi hàng là một `feedbacks` (vote, với `entry_type = "vote"`) hoặc một
`translation_edits` (bản người dùng sửa, với `entry_type = "edit"`). Cả hai được nối với
bản gốc, bản dịch máy, cặp ngôn ngữ và model để người duyệt thấy chính xác điều cần đối chiếu.
`vote` là `up` cho rating 5, `down` cho rating 1 và `other` cho các giá trị còn lại; bản sửa
nằm ở `user_correction`.

**Ranh giới của bảng kiểm tra:** không người gửi/người sửa, không `user_id`, `editor_id`,
`conversation_id`, `message_id`, `translation_id`, email hoặc liên kết mở lại hội thoại. Đây
là quyền chỉ của `role == "admin"`, dùng để kiểm soát chất lượng trong hệ thống; không phải
API công khai hay dữ liệu xuất cho người dùng. `shared_corrections` vẫn là luồng opt-in đã
ẩn danh dành cho khai thác glossary và không bị thay thế bởi bảng kiểm tra này.

**`withheld_total` là số dòng `correction_log` mà người viết không đồng ý chia sẻ** — một con
số, không kèm gì khác. Nó tồn tại để việc "đang bị bỏ ra ngoài" nhìn thấy được, thay vì trông
như chưa từng có. `shared_total` là tổng số dòng đã đồng ý chia sẻ, khác với độ dài mảng ở
trên khi `limit` cắt bớt.

### 3.15. Quyền người dùng cấp cho trợ lý AI (27/08)

Trợ lý AI đọc nội dung hội thoại, ghi nhớ nó và ghi vào lịch bên ngoài. Không việc nào
trong số đó được phép chạy chỉ vì người dùng là thành viên hội thoại — tư cách thành viên
trả lời câu hỏi "ai được xem", không trả lời câu hỏi "người này có đồng ý cho máy đọc
không". Đây là hai câu hỏi khác nhau và cần hai cơ chế khác nhau.

**Năm quyền, độc lập với nhau, mặc định đều là `false`:**

| `scope` | Cho phép điều gì | Không cấp thì mất gì |
|---|---|---|
| `read_conversations` | Trợ lý đọc nội dung tin nhắn để tóm tắt và trích việc | Tóm tắt, trích việc, `@assistant` đều từ chối |
| `proactive_scan` | Tự quét mỗi tin nhắn mới để phát hiện cam kết/lịch hẹn | Vẫn dùng được trợ lý, nhưng phải tự yêu cầu |
| `store_memory` | Lưu vector nhúng của tin nhắn làm bộ nhớ dài hạn | Trợ lý chỉ thấy ngữ cảnh gần, không nhớ chuyện cũ |
| `calendar_read` | Đọc sự kiện từ Google Calendar về ứng dụng | Lịch trong ứng dụng không thấy sự kiện tạo ngoài |
| `calendar_write` | Ghi sự kiện đã duyệt lên Google Calendar | Việc đã duyệt chỉ nằm trong lịch của ứng dụng |

`proactive_scan` **không bao hàm** `read_conversations`: quét chủ động cần cả hai. Tách ra
vì "cho phép đọc khi tôi hỏi" và "cho phép đọc mọi lúc kể cả khi tôi không hỏi" là hai
mức riêng tư khác hẳn nhau, và người dùng phải nói được điều thứ nhất mà không phải chấp
nhận điều thứ hai.

```
GET /api/v1/auth/me/agent-consents
PUT /api/v1/auth/me/agent-consents
```

`GET` luôn trả **đủ cả năm** quyền kể cả khi người dùng chưa từng động tới — quyền chưa
có hàng trong cơ sở dữ liệu là quyền **chưa cấp**, không phải quyền không tồn tại. Trả
thiếu thì giao diện không dựng được danh sách để hỏi.

```json
{
  "policy_version": "1",
  "consents": [
    {"scope": "read_conversations", "is_granted": true,  "granted_at": "2026-08-27T09:12:00Z", "revoked_at": null},
    {"scope": "proactive_scan",     "is_granted": false, "granted_at": null, "revoked_at": "2026-08-27T10:03:00Z"}
  ]
}
```

`PUT` nhận `{"consents": {"<scope>": bool, ...}}`, chỉ những quyền muốn đổi, `extra="forbid"`.
Trả về đúng hình dạng của `GET`. Rút một quyền chỉ đặt `is_granted = false` và ghi
`revoked_at`; hàng không bị xoá, để trả lời được câu "người này đã từng đồng ý chưa".

**`policy_version`** đi kèm mọi lần cấp. Khi danh sách quyền đổi, đồng ý cũ **không** im
lặng áp sang quyền mới: giao diện so `policy_version` của hàng với hằng hiện hành và hỏi
lại. Không có trường này thì việc thêm quyền thứ sáu sẽ tự động coi như đã được đồng ý.

**Quan hệ với `user_settings.ai_smart_assistance`:** đó là **công tắc hiển thị**, không
phải quyền. Tắt nó thì trợ lý biến mất khỏi giao diện; nó không thu hồi quyền nào và bật
lại không hỏi lại điều gì. Quyền nằm ở đây.

### 3.16. Lịch cá nhân và nhắc việc (27/08)

```
GET    /api/v1/me/calendar/events?starts_after=&starts_before=&include_cancelled=
POST   /api/v1/me/calendar/events
PATCH  /api/v1/me/calendar/events/{event_id}
DELETE /api/v1/me/calendar/events/{event_id}
GET    /api/v1/me/reminders?include_delivered=
POST   /api/v1/me/reminders/{reminder_id}/dismiss
```

Tất cả đều **giới hạn theo chủ sở hữu ở cả chiều đọc lẫn chiều ghi**. Lịch là bề mặt
riêng tư nhất của sản phẩm, và một truy vấn thiếu bộ lọc `user_id` ở đây là một vụ lộ dữ
liệu **im lặng** chứ không phải một lỗi.

Chạm tới mục của người khác bằng id trả **404 chứ không phải 403**: người gọi tự cung
cấp id, nên phân biệt "không phải của bạn" với "không có id này" chỉ làm lộ đúng một dữ
kiện mới — rằng id đó có tồn tại.

`DELETE` là **huỷ chứ không xoá** — trả về mục với `status = 'cancelled'` (xem §5 ghi chú
21) và tắt các nhắc việc chưa gửi của nó.

Mục có `sync_state = 'remote_only'` (đến từ Google) trả **409** cho `PATCH` và `DELETE`.

`POST` nhận `reminder_minutes_before`, mặc định 15. `null` nghĩa là **không nhắc** — đó
là một lựa chọn thật, khác với "dùng mặc định". Nếu mốc nhắc rơi vào quá khứ thì **không
tạo nhắc việc nào** thay vì bắn ngay: một thông báo về việc đang diễn ra là nhiễu, và với
một việc nhập sau khi đã xong thì nó sẽ nổ ngay lúc bấm lưu.

Duyệt một đề xuất **có thời gian** sẽ tự tạo một mục lịch, **trong cùng giao dịch** với
lần chuyển trạng thái. Đề xuất **không có thời gian** thì không lên lịch: "tôi sẽ xem lại
tài liệu" mà không nói khi nào là một việc có thật, và nó thuộc về hộp nhiệm vụ chứ không
phải một ô giờ do hệ thống bịa ra.

`POST /api/v1/action-proposals/{id}/confirm` nhận **`reminder_minutes_before`** cùng bộ
trường sửa (`title`, `details`, `location`, `scheduled_start_at`, `scheduled_end_at`,
`due_at`, `resolved_timezone`). **Cùng tên và cùng ngữ nghĩa** với `POST /me/calendar/events`:
vắng mặt là 15 phút, `null` là **không nhắc**. Đây là lúc con người bổ sung thứ mà tin
nhắn không hề chứa — người ta viết "review thiết kế 10h sáng thứ Tư", không ai viết họ
muốn được nhắc trước bao lâu — nên hỏi ở bước duyệt chứ không đoán từ văn bản.

Trường này **không phải một phép sửa đề xuất**: nó định hình *mục lịch* được tạo ra, không
phải hàng `action_proposals`, nên nó đi như một tham số riêng. Để lẫn vào danh sách sửa
thì bộ lọc allowlist ở `confirm_proposal` sẽ **âm thầm loại nó** và lựa chọn của người
dùng biến mất mà không có lỗi nào.

### 3.17. Liên kết Google Calendar (27/08)

```
GET    /api/v1/me/calendar/google/authorize
POST   /api/v1/me/calendar/google/callback
DELETE /api/v1/me/calendar/google/link
POST   /api/v1/me/calendar/sync
```

Cả bốn đều yêu cầu quyền **`calendar_read`** (§3.15). Đưa người dùng qua màn hình đồng ý
của Google để xin một quyền mà họ chưa cấp ở đây là thu về quyền truy cập mà chính ứng
dụng đã được bảo là đừng dùng.

`authorize` trả về URL đồng ý kèm tham số `state` là **token đã ký, hạn 10 phút**. Google
trả lại `state` nguyên văn, và `callback` **đối chiếu nó với người gọi đã xác thực** chứ
không chỉ kiểm tính hợp lệ: một token ký cho tài khoản khác chứng tỏ callback bị phát lại.

`DELETE` **idempotent** — gỡ một liên kết vốn không có là đúng trạng thái người gọi muốn,
không phải lỗi. Nó xoá token nhưng **giữ nguyên các sự kiện đã đẩy lên Google**: đó là
lịch hẹn thật của người dùng, không phải tài sản của tích hợp này.

`POST /me/calendar/sync` chạy một chu kỳ ngay lập tức cho nút "Đồng bộ ngay". Cơ chế mang
thay đổi từ Google về vẫn là **polling định kỳ** (ADR-36); endpoint này chỉ để bỏ qua thời
gian chờ. Trả về `pushed`, `pulled` và **`last_sync_error`** — lỗi được đưa lên chứ không
nuốt đi, vì một lịch đồng bộ hỏng nhìn giống hệt một lịch không có gì để đồng bộ.

Nếu deployment chưa cấu hình đủ (`GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET`,
`GOOGLE_OAUTH_REDIRECT_URI`, `TOKEN_ENCRYPTION_KEY`) thì `authorize` trả **503**.

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
| `send_voice_message` | `{"type":"send_voice_message", "client_message_id", "conversation_id", "attachment_id", "reply_to_message_id"?}` | Claim audio đã upload và tạo voice `pending`; không có trường text hoặc lifecycle từ client |

### 4.2. Chiều Server đến Client

Trình tự sự kiện khi cần dịch: `message.received` (trạng thái `streaming`) → nhiều `translation.chunk` → `translation.completed`. Trường hợp không cần dịch: chỉ phát `message.received` với trạng thái `not_required`. Trình tự chi tiết: xem [Sequence Diagram](architecture_diagram.md#5-sequence-diagram).

| `type` | Payload | Điều kiện phát |
|---|---|---|
| `message.received` | `{"type": "message.received", "message_id", "sender_id", "original_text", "source_language", "translation_status": "not_required" \| "streaming", "created_at"}` | Ngay sau khi Chat Service lưu xong tin nhắn gốc. Phát tới toàn bộ thành viên trong cuộc hội thoại, bao gồm người gửi |
| `translation.chunk` | `{"type": "translation.chunk", "message_id", "target_language", "chunk": "string"}` | Mỗi đoạn bản dịch nhận được từ LLM ở chế độ streaming |
| `translation.completed` | `{"type": "translation.completed", "message_id", "translation_id", "target_language", "honorific_profile", "source_language", "translated_text", "model", "latency_ms", "is_fallback"}` | Khi Agent hoàn tất xử lý, bao gồm cả trường hợp fallback |
| `typing` | `{"type": "typing", "conversation_id", "user_id", "is_typing"}` | Chuyển tiếp sự kiện soạn tin tới **các thành viên khác**, không gửi lại cho chính người gõ |
| `message_updated` | `{"type": "message_updated", "message_id", "conversation_id", "original_text", "edited_at"}` | Sau khi người gửi sửa tin nhắn (§3.6). Phát tới các thành viên khác; bản dịch mới đến sau bằng `translation_completed` như tin nhắn thường |
| `message_deleted` | `{"type": "message_deleted", "message_id", "conversation_id", "deleted_at"}` | Sau khi người gửi gỡ tin nhắn (§3.6). Phát tới các thành viên khác |
| `message_read` | `{"type": "message_read", "conversation_id", "user_id", "read_at"}` | Khi một thành viên đánh dấu đã đọc (§3.8). Phát tới các thành viên khác để họ đổi dấu ✓ thành ✓✓ |
| `message_created` / `message_received` | `{"type", "message": RealtimeMessage, ...}` | Ack cho sender / giao cho recipients sau commit. Voice mới mang `message_type="voice"`, `transcription_status="pending"`, `original_text=""` và attachment audio |
| `voice_transcription_completed` | `{"type":"voice_transcription_completed", "message_id", "conversation_id", "original_text", "source_language", "transcription_status":"completed"}` | Chỉ sau khi transcript nguyên văn đã commit; `translation_completed` tiếp tục qua handler chung |
| `voice_transcription_failed` | `{"type":"voice_transcription_failed", "message_id", "conversation_id", "transcription_status":"failed", "retryable":true}` | Chỉ sau khi trạng thái failed và `original_text=""` đã commit; không lộ provider detail |
| `error` | `{"type": "error", "code": "string", "message": "string"}` | Khi phát sinh lỗi kết nối hoặc xác thực (xem §6) |

**Góp ý bản dịch (§3.10) không có sự kiện WebSocket nào.** Bản góp ý là dữ liệu riêng của người viết, không ai khác đọc được, nên không có gì để phát đi — phản hồi của lời gọi REST là đủ. Việc "người nhận thấy nội dung mới" thuộc về §3.6: người gửi sửa **tin nhắn gốc**, server dịch lại, cả phòng nhận `message_updated` rồi `translation_completed` như một tin nhắn thường và bóng chat hiện trạng thái đã sửa. Đừng gộp hai luồng này.

Hai sự kiện `message_updated` và `message_deleted` đặt tên `snake_case` theo đúng quy ước trong `CLAUDE.md` và theo tên các sự kiện đã hiện thực trong `src/schemas/chat.py`. Các dòng viết dạng chấm phía trên là bản nháp trước khi hiện thực, chưa được đồng bộ lại với mã nguồn.

**Quy định xử lý phía Frontend:**

1. Trường `translation_id` trong sự kiện `translation.completed` là nguồn duy nhất cung cấp định danh bản dịch cho Frontend. Thiếu trường này, tính năng F-05 không thể hiện thực hoá.
2. Trường `source_language` trong `translation.completed` là giá trị đã xác nhận sau bước detect, có thể khác giá trị tạm đã phát trong `message.received`. Frontend cập nhật lại theo giá trị này.
3. Với `is_fallback = true`, Frontend hiển thị chỉ báo phân biệt (ví dụ biểu tượng cảnh báo) nhưng không hiển thị dưới dạng lỗi, do tin nhắn gốc vẫn được truyền tới người nhận.
4. Frontend sử dụng `translated_text` trong `translation.completed` làm kết quả cuối cùng. Các sự kiện `translation.chunk` chỉ phục vụ hiệu ứng hiển thị theo thời gian thực và có thể bị mất gói.

### 4.2.1. Sự kiện của trợ lý và lịch (27/08)

| Sự kiện | Khi nào | Gửi cho |
|---|---|---|
| `action_proposal_created` | Trợ lý tìm ra một việc cần duyệt | **chỉ chủ sở hữu** |
| `reminder_due` | Tới mốc nhắc việc | chủ sở hữu |
| `action_proposal_confirmed` | Người dùng duyệt một đề xuất | chủ sở hữu |
| `calendar_event_updated` | Mục lịch đổi ở nơi khác (thường là từ Google) | chủ sở hữu |

Bốn sự kiện này **không bao giờ phát cho cả hội thoại**, kể cả khi đề xuất sinh ra từ một
tin nhắn nhóm: nội dung của chúng là việc riêng của một người, và người khác trong nhóm
chưa hề yêu cầu điều đó (ADR-31).

`action_proposal_created` hiện là sự kiện **duy nhất** trong hệ thống được phát dưới dạng
dict trần thay vì `Literal` trên một model Pydantic. Đó là nợ kỹ thuật đã biết, không phải
tiền lệ — sự kiện mới phải theo quy ước ở §4.

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
2. Thực hiện một lần dịch cho mỗi cặp **(ngôn ngữ đích, vị thế xưng hô)** còn lại — **sửa ngày 20/08**, trước đó là mỗi ngôn ngữ đích. Các thành viên cùng ngôn ngữ **và cùng vị thế** dùng chung một bản dịch và cùng một `translation_id`. Vị thế nhận bốn giá trị `senior | peer | junior | client`, lấy từ `participant_profiles` (§5 ghi chú 15), nên số lượt dịch tối đa là số cặp khác nhau chứ không phải số thành viên: một nhóm 10 người đọc 3 ngôn ngữ đi từ 3 lượt lên nhiều nhất 9, và hội thoại `direct` không đổi vì mỗi ngôn ngữ ở đó vốn chỉ có một người nhận. Lý do phải thêm chiều này: tiếng Việt, tiếng Nhật và tiếng Hàn không dựng được câu mà không chọn cách xưng hô, và lựa chọn đó khác nhau giữa một quản lý và một khách hàng trong cùng một nhóm (ADR-23).

   **Thang dự phòng khi đọc.** `translation_results.honorific_profile` ghi một lần và không bao giờ ghi đè, trong khi hồ sơ vị thế do LLM suy ra và **thay đổi được**. Hai giá trị vì thế lệch nhau theo thiết kế, nên đường đọc chọn bản dịch theo ba bậc, đúng thứ tự này:

   1. đúng cặp `(ngôn ngữ của người đọc, vị thế hiện tại của họ)`;
   2. không có thì lấy cùng ngôn ngữ ở bậc trung tính `peer`;
   3. vẫn không có thì lấy **bất kỳ** bản dịch nào cùng ngôn ngữ, theo thứ tự `created_at` tăng dần để hai lần đọc liên tiếp không cho hai kết quả khác nhau.

   Thang này nới **vị thế**, tuyệt đối không nới **ngôn ngữ**. Không có nó, một lần suy luận lại hồ sơ sẽ làm biến mất mọi bản dịch đã giao trong luồng hội thoại: người dùng tải lại trang và thấy toàn bộ quay về nguyên bản, không có lỗi nào được ghi. Giao một cách xưng hô hơi lệch là thiệt hại nhỏ hơn hẳn giao một tin nhắn chưa dịch.
3. Mỗi kết nối WebSocket chỉ nhận các sự kiện `translation.chunk` và `translation.completed` có `target_language` trùng với `preferred_language` của người dùng tương ứng — **cộng thêm người gửi tin nhắn trong hội thoại `type = "direct"`, nhận bản dịch của chính tin mình gửi** (sửa theo §3.10, **đề xuất**).

   Vế thêm vào là điều kiện để §3.10 chạy được ở chat 1-1. Trước đây `_recipients_by_language` xếp người gửi vào đúng nhóm ngôn ngữ *họ đọc*, nên giữa một người đọc `vi` và một người đọc `en`, bản dịch `en` chỉ tới người nhận. Người gửi không có bản dịch nào trong tay để đối chiếu hay góp ý cho tới khi tải lại trang — trong khi `GET /conversations/{id}/messages` vốn đã trả **toàn bộ** bản dịch của mỗi tin, tức dữ liệu đã sẵn sàng, chỉ thiếu đường phát theo thời gian thực.

   Phạm vi dừng ở `direct` chứ không mở cho nhóm, vì quyền góp ý của người gửi cũng chỉ có ở `direct` (§3.10). Hội thoại `direct` có đúng một ngôn ngữ đích khác, nên người gửi nhận thêm nhiều nhất một sự kiện cho mỗi tin nhắn.

Đây là yêu cầu chức năng bắt buộc, khác biệt với nội dung tối ưu hiệu năng tại ADR-03 ([`ARCHITECTURE.md`](../ARCHITECTURE.md)). ADR-03 chỉ đề cập việc tối ưu fan-out, không thay đổi quy tắc nêu trên.

## 5. Schema cơ sở dữ liệu

Quy ước đặt tên theo mã nguồn hiện có (`src/database/models.py`): tên bảng viết thường, dạng số nhiều; khoá chính đặt tên `id`.

| Bảng | Các trường |
|---|---|
| `users` | `id`, `email`, `username`, `display_name`, `password_hash`, `google_sub`, `role`, `preferred_language`, `interface_language`, `created_at` |
| `conversations` | `id`, `type`, `title`, `created_by`, `created_at` |
| `conversation_members` | `conversation_id`, `user_id`, `joined_at` |
| `messages` | `id`, `client_message_id`, `conversation_id`, `sender_id`, `original_text`, `source_language`, `visibility`, `visible_to_user_id`, `created_at`, `edited_at`, `deleted_at` |
| `translation_results` | `id`, `message_id`, `target_language`, `honorific_profile`, `translated_text`, `model`, `latency_ms`, `is_fallback`, `created_at` |
| `feedbacks` | `id`, `translation_id`, `user_id`, `rating`, `correction`, `created_at` |
| `translation_edits` | `id`, `translation_id`, `editor_id`, `edited_text`, `created_at` |  <!-- đã hiện thực -->
| `translation_attempts` | `id`, `message_id`, `target_language`, `source_language_declared`, `source_language_detected`, `outcome`, `provider`, `model_configured`, `model_served`, `detect_method`, `llm_calls`, `input_tokens`, `output_tokens`, `finish_reason`, `detect_ms`, `context_ms`, `translate_ms`, `fallback_ms`, `total_ms`, `context_lines`, `fallback_reason`, `translation_id`, `honorific_profile`, `created_at` |

| `conversation_profiles` | `id`, `conversation_id`, `domain`, `audience`, `message_count_at_last_run`, `consecutive_stable_runs`, `locked_at`, `rationale`, `created_at`, `updated_at` |
| `participant_profiles` | `id`, `conversation_id`, `user_id`, `honorific_profile`, `inferred_by`, `confidence`, `rationale`, `created_at`, `updated_at` |
| `glossary_entries` | `id`, `source_term`, `source_term_normalized`, `target_term`, `source_language`, `target_language`, `domain`, `audience`, `keep_verbatim`, `status`, `approved_by`, `embedding`, `embedding_model`, `created_at`, `updated_at` |
| `glossary_proposals` | `id`, `source_term`, `source_term_normalized`, `target_term`, `source_language`, `target_language`, `domain`, `audience`, `keep_verbatim`, `status`, `occurrence_count`, `distinct_user_count`, `rationale`, `reviewed_by`, `reviewed_at`, `reject_reason`, `embedding`, `embedding_model`, `created_at` |
| `glossary_proposal_citations` | `id`, `proposal_id`, `anonymized_snippet`, `observed_at` |
| `correction_log` | `id`, `source_phrase`, `corrected_target`, `source_language`, `target_language`, `domain`, `audience`, `user_id`, `translation_id`, `consent_to_share`, `original_snippet`, `anonymized_snippet`, `embedding`, `embedding_model`, `observed_at` |
| `message_embeddings` | `id`, `message_id`, `conversation_id`, `embedding`, `embedding_model`, `created_at` |
| `agent_consents` | `id`, `user_id`, `scope`, `is_granted`, `granted_at`, `revoked_at`, `policy_version`, `created_at`, `updated_at` |
| `calendar_events` | `id`, `user_id`, `action_proposal_id`, `source`, `title`, `details`, `location`, `starts_at`, `ends_at`, `all_day`, `timezone`, `status`, `google_event_id`, `google_calendar_id`, `google_etag`, `sync_state`, `created_at`, `updated_at` |
| `reminders` | `id`, `user_id`, `calendar_event_id`, `remind_at`, `delivered_at`, `dismissed_at`, `created_at` |
| `calendar_links` | `user_id`, `google_calendar_id`, `refresh_token_encrypted`, `access_token_encrypted`, `token_expires_at`, `sync_token`, `sync_enabled`, `last_synced_at`, `last_sync_error`, `created_at`, `updated_at` |
| `assistant_chunks` | `id`, `conversation_id`, `strategy`, `chunk_index`, `chunk_text`, `message_ids`, `token_count`, `starts_at`, `ends_at`, `parent_index`, `embedding`, `embedding_model`, `created_at` |
| `assistant_user_memory` | `id`, `user_id`, `conversation_id`, `kind`, `content`, `confidence`, `source_message_id`, `superseded_by`, `embedding`, `embedding_model`, `created_at` |
| `assistant_attempts` | `id`, `conversation_id`, `user_id`, `source_message_id`, `outcome`, `provider`, `model_configured`, `replans`, `tool_calls`, `tools_failed`, `tools_used`, `proposals_created`, `proposals_executed`, `memory_lines`, `memory_recalled`, `total_ms`, `error_code`, `created_at` |

**Ghi chú:**

1. `users.role` là quyền ở cấp hệ thống (`member` hoặc `admin`). Bảng `conversation_members` **không có cột `role`**: không tính năng nào trong F-01..F-06 dùng tới vai trò trong hội thoại, nên cột này đã được gỡ khỏi hợp đồng thay vì thêm một cột chết vào mã nguồn.
2. `conversation_members` dùng **khoá chính tổ hợp** `(conversation_id, user_id)`, không có cột `id` riêng. Một người chỉ thuộc một hội thoại đúng một lần, nên tổ hợp này vừa là định danh vừa là ràng buộc.
3. `conversations.type` nhận `direct` hoặc `group`, có `CheckConstraint` ở mức cơ sở dữ liệu.
4. `messages.client_message_id` do client sinh ra, cùng `sender_id` và `conversation_id` tạo thành ràng buộc duy nhất. Đây là cơ chế cho phép gửi lại an toàn khi mất kết nối — xem `docs/RECONNECT_CONTRACT.md`.
5. `messages.source_language` khi ghi là **giá trị tạm** (`preferred_language` của người gửi); node `detect_language` của Agent ghi đè bằng kết quả nhận diện thật (§4.3).
6. `translation_results` có ràng buộc duy nhất `(message_id, target_language, honorific_profile, translation_tone, version)`. Luồng dịch tự động (normal translation) hoạt động idempotent ở `version = 1`, đảm bảo an toàn dưới xử lý đồng thời. Khi người dùng bấm "Dịch lại" (Translate Again), hệ thống tạo một bản ghi dịch mới với phiên bản kế tiếp (`version = max_version + 1`) và `translation_id` (UUID) mới. Các bản ghi đánh giá (`feedbacks`) và bản góp ý riêng tư (`translation_edits`) trong lịch sử vẫn giữ nguyên liên kết tới đúng `translation_id` của phiên bản tương ứng. Khi tải tin nhắn hoặc tìm kiếm, hệ thống sắp xếp theo `version DESC, created_at DESC` để luôn chọn bản dịch mới nhất cho người đọc.
7. `translation_results.is_fallback` đúng khi văn bản **không** đến từ LLM đã cấu hình, bao gồm cả trường hợp provider dự phòng dịch thành công. `model` để rỗng khi không tầng nào dịch được và hệ thống trả nguyên bản (`ARCHITECTURE.md` §5.1).
8. **Alembic là nơi duy nhất định nghĩa schema** (sửa 15/08). Ứng dụng không còn tạo bảng lúc khởi động; container chạy `alembic upgrade head` trước `uvicorn`, còn trên máy phát triển là `make migrate`. Đổi schema nghĩa là sinh migration (`make revision m="..."`) rồi đọc lại bản sinh ra. `make reset-db` vẫn còn nhưng nay là `downgrade base` + `upgrade head` và **xoá sạch dữ liệu cục bộ**. Xem ADR-06.
9. `translation_attempts` là **nhật ký đo lường**, không phải trạng thái ứng dụng (ADR-16). Mỗi cặp (tin nhắn × ngôn ngữ đích) được thử ghi một dòng, **kể cả khi không sinh ra bản dịch nào**. Khác `translation_results` ở ba điểm có chủ đích: không có ràng buộc duy nhất (chạy lại là một lượt thử mới, đáng đếm riêng), `translation_id` cho phép `NULL` với `ON DELETE SET NULL` (xoá bản dịch không được xoá bằng chứng rằng đã dịch), và các cột được tự do thay đổi theo nhu cầu đo — **không** thành phần nào ngoài `src/services/metrics.py` và `scripts/report_metrics.py` được đọc bảng này.
10. `translation_attempts.outcome` nhận đúng bảy giá trị, có `CheckConstraint` ở mức cơ sở dữ liệu: `llm`, `secondary`, `original` (ba trường hợp có dòng trong `translation_results`), và `passthrough`, `timeout`, `error`, `empty` (bốn trường hợp không có). Bốn giá trị sau chính là mẫu số còn thiếu: mọi tỷ lệ fallback tính riêng trên các lượt thành công đều không phải là một tỷ lệ.
11. `translation_attempts.source_language_detected` để `NULL` khi nhận diện bị bỏ qua hoặc thất bại. Không được ghi giá trị khai báo vào đây: hai cột sẽ khớp nhau do cách xây dựng, và tỷ lệ đồng thuận của ADR-11 sẽ luôn đọc ra 100% bất kể nhận diện hoạt động thế nào.
12. `translation_edits` là **nhật ký chỉ ghi thêm** (đề xuất, §3.10): không có ràng buộc duy nhất trên `(translation_id, editor_id)` vì góp ý lại là một dòng mới chứ không phải sửa dòng cũ, và bản có hiệu lực là bản `created_at` lớn nhất **của từng người**. Chỉ mục `(translation_id, editor_id, created_at)` để lấy bản mới nhất của người đang gọi mà không quét cả bảng — thứ tự cột đúng theo cách truy vấn, vì mọi lần đọc đều lọc theo cả hai khoá. `editor_id` dùng `ON DELETE CASCADE`: dữ liệu này riêng tư của một người, xoá tài khoản thì xoá theo, không để lại dòng vô chủ mà không ai có quyền đọc. Khác `feedbacks.correction` đúng một điểm: bảng này giữ **toàn bộ lịch sử** góp ý thay vì một dòng mỗi người — cả hai đều riêng tư như nhau. `feedbacks.correction` sẽ **không còn được client ghi vào** kể từ khi giao diện chuyển sang endpoint mới (PR frontend của F-05); tới lúc đó nút bút chì vẫn ghi vào cột cũ. Cột giữ lại vĩnh viễn để đọc dữ liệu đã có.
13. `users.interface_language` (§1.2) `NOT NULL`; migration lấp giá trị ban đầu bằng chính `preferred_language` của từng dòng, nên không tài khoản nào thấy giao diện đổi ngôn ngữ sau khi nâng cấp. Không có ràng buộc khoá ngoại tới danh sách ngôn ngữ: danh sách đó là allowlist ở tầng ứng dụng (`GET /languages`), không phải bảng.
14. `translation_attempts.total_ms` đo bằng wall clock ở tầng service, bao trùm cả truy vấn ngữ cảnh và overhead LangGraph, nên **rộng hơn** `translation_results.latency_ms` (chỉ tính thời gian gọi model). Ngữ nghĩa của `latency_ms` giữ nguyên vì nó đã nằm trong sự kiện WebSocket và REST history; NFR-01 nói về `total_ms`.
15. `conversation_profiles` và `participant_profiles` giữ kết quả suy luận của LLM về **lĩnh vực**, **đối tượng** của hội thoại và **vị thế** của từng thành viên. Suy luận không chạy theo từng tin nhắn: chờ đủ 5 tin mới chạy lần đầu, sau đó lặp lại mỗi 20 tin, và dừng hẳn khi 3 lần liên tiếp cho cùng kết quả — lúc đó `locked_at` được đóng dấu. Cách này chặn hạn mức ở vài lượt gọi cho mỗi hội thoại, đồng thời không để đối tượng nhấp nháy giữa các tin nhắn, thứ mà người đọc sẽ thấy thành giọng văn đổi giữa chừng (ADR-24). `participant_profiles.honorific_profile` nhận đúng bốn giá trị có `CheckConstraint`: `senior`, `peer`, `junior`, `client`; `peer` là bậc trung tính và là bậc mặc định khi chưa suy ra được gì. Khoá theo `(conversation_id, user_id)` chứ không theo người: cùng một tài khoản là `junior` với quản lý của mình và là `client` trong hội thoại với nhà cung cấp.
16. `glossary_entries` là bảng ánh xạ thuật ngữ nguồn → đích, tồn tại để ép **tính nhất quán**: nếu để tự do, model dịch `staging environment` lúc thì "môi trường staging" lúc thì "môi trường dàn dựng", và người đọc không biết hai câu có nói về cùng một thứ không. `domain` và `audience` là thứ làm cùng một thuật ngữ ra hai kết quả — dòng gắn `audience` nội bộ giữ nguyên `UI`, dòng gắn `audience` khách hàng cho ra "giao diện". Chuỗi rỗng nghĩa là "áp dụng ở mọi nơi" và đóng vai trò bậc dự phòng, nên **cả hai cột đều nằm trong ràng buộc duy nhất và không được phép `NULL`**: `NULL` không so bằng `NULL` nên bản trùng sẽ lọt lưới. `status` nhận `active` hoặc `retired`; **không xoá dòng bao giờ** — một bản dịch giao tháng trước được định hình bởi thuật ngữ đang active lúc đó, xoá đi là xoá mất lời giải thích duy nhất cho câu chữ người đọc đang nhìn. **Từ vựng của hai cột là danh sách đóng (22/08):** `audience` nhận `internal` hoặc `client`, `domain` nhận `engineering`, `commercial` hoặc `support`, ngoài ra là chuỗi rỗng. Danh sách khai báo ở `src/database/models.py` (`GLOSSARY_AUDIENCES`, `GLOSSARY_DOMAINS`) và là **cùng bộ từ** mà lượt suy luận hồ sơ hội thoại bị buộc phải trả lời, vì tra cứu so hai bên bằng phép bằng — một hội thoại ghi là "an external client" không bao giờ gặp một mục xếp dưới `client` (ADR-24). Không đặt CheckConstraint: chuỗi rỗng là một giá trị thật, và quản trị viên vẫn được nhập tay một phạm vi mà danh sách chưa biết tới.
17. `correction_log` **tách riêng khỏi `translation_edits` một cách có chủ ý**. `translation_edits` giữ nguyên đúng những gì ADR-19 quy định: chỉ ghi thêm, riêng tư tuyệt đối với người viết, không ai khác đọc được. Khai thác thẳng bảng đó là âm thầm rút lại lời hứa ấy. `correction_log` chỉ giữ phần **dẫn xuất** — máy viết gì, người sửa thành gì — và chỉ những dòng mà tác giả đã đồng ý chia sẻ. `consent_to_share` khoá cả dòng chứ không riêng phần trích dẫn: đếm một bản sửa mà người ta không đồng ý chia sẻ thì vẫn là đang dùng nó. `glossary_proposals` dòng `rejected` **không bao giờ bị xoá**: chúng mang embedding để bộ khai thác đối chiếu ứng viên mới, nếu không thì tuần sau đúng thuật ngữ đó quay lại với cách viết hơi khác và hàng đợi duyệt biến thành nhiễu không ai đọc.
18. `message_embeddings` là bảng riêng chứ không phải một cột trên `messages`: `messages` là bảng nóng, được liệt kê từng trường trong §5 này, còn đây là dữ liệu dẫn xuất tính lại lúc nào cũng được — đúng cách tách và đúng lý do mà ADR-16 đã áp dụng cho `translation_attempts`. `conversation_id` được lặp lại ở đây để tìm kiếm láng giềng gần nhất giới hạn được trong một hội thoại mà không phải join: một index vector chỉ được dùng khi bộ lọc đi kèm là rẻ, và việc truy hồi **tuyệt đối không được** với sang hội thoại khác. Bốn cột `embedding` trong schema dùng kiểu `vector` của pgvector với index HNSW `vector_cosine_ops`, và mỗi bảng lưu kèm `embedding_model` để một vector do model khác sinh ra nhận ra được thay vì bị âm thầm so trong sai không gian (ADR-25).
19. `agent_consents` là **quyền**, không phải tuỳ chọn giao diện, nên nó là bảng riêng chứ không phải năm cột nữa trên `user_settings` (§3.15). Ba lý do đều mang tính cơ chế. Thứ nhất, quyền cần biết **thời điểm** cấp và thu (`granted_at`, `revoked_at`) — một cột boolean không kể lại được điều đó, mà "người này đã đồng ý từ lúc nào" đúng là câu hỏi phải trả lời được khi có tranh chấp. Thứ hai, `policy_version` gắn với **từng quyền**: thêm quyền thứ sáu chỉ được phép hỏi lại về quyền đó, không làm mất hiệu lực năm quyền đã cấp. Thứ ba, danh sách quyền sẽ còn dài ra, và mỗi lần dài ra mà phải chạy `ALTER TABLE` trên `user_settings` là mỗi lần đụng vào bảng mọi người đang đọc. **Không có hàng nghĩa là chưa cấp** — mặc định fail closed, giống hệt cách `consent_to_share` mặc định `false` ở ghi chú 17. Ràng buộc duy nhất `(user_id, scope)`; `scope` có `CheckConstraint` sinh từ `AGENT_CONSENT_SCOPES` trong `src/database/models.py`. Thu hồi **không xoá hàng**, chỉ đặt `is_granted = false` và đóng dấu `revoked_at`, vì xoá đi thì "chưa bao giờ được hỏi" và "đã hỏi rồi và bị từ chối" trở nên không phân biệt được — mà đó lại chính là thứ quyết định có nên hỏi lại hay không.

20. `messages.visibility` nhận `public` hoặc `private`, có `CheckConstraint`, `server_default` là `public` — một tin nhắn có trước cột này vốn ai trong hội thoại cũng đọc được, và đó đúng là nghĩa của `public`, nên không cần backfill. `private` nghĩa là **chỉ đúng tài khoản ghi ở `visible_to_user_id`**, và một `CheckConstraint` thứ hai cấm tồn tại tin riêng tư mà không nêu tên ai. Cột này tồn tại vì trợ lý trả lời `@assistant` ngay trong nhóm, mà câu trả lời có thể tóm tắt lại cam kết của người khác — đẩy cho cả nhóm vừa gây phiền vừa là tiết lộ về những thành viên không hề yêu cầu điều đó (ADR-31). **Lọc bắt buộc nằm trong mệnh đề `WHERE` của mọi lần đọc**, không phải bỏ hàng sau khi đã nạp: lọc ở tầng serialize thì văn bản vẫn được `SELECT` ra và vẫn đi qua mạng, còn lọc ở frontend thì mở DevTools là thấy — `docs/NewFeature.md` §3.3 gọi đó là lỗi bảo mật kinh điển. Điều kiện dùng chung nằm ở `src/services/message_visibility.py`: `visible_to(user_id)` cho mọi truy vấn trả lời **một người**, và `public_only()` cho hai chỗ mà người tiêu thụ là **tiến trình phục vụ nhiều người** — ngữ cảnh của agent dịch (dựng một lần rồi giao cho mọi thành viên) và suy luận hồ sơ hội thoại (kết luận áp cho cả hội thoại). Đặc biệt lưu ý ở bản xem trước tin nhắn cuối: bộ lọc phải nằm **bên trong** phép xếp hạng, vì xếp hạng trên toàn bộ rồi mới loại thì hội thoại sẽ mất hẳn dòng xem trước thay vì lùi về tin mới nhất mà người đọc được phép thấy.

21. `calendar_events` là **thứ mà một đề xuất đã duyệt trở thành**, và là lý do `action_proposals.status = 'confirmed'` thôi làm ngõ cụt — trước đó duyệt xong không có gì xảy ra tiếp. Hai bảng tách nhau vì chúng **rẽ nhánh về sau**: người dùng dời sự kiện, Google dời sự kiện, sự kiện bị huỷ — không việc nào trong đó thay đổi sự thật rằng cam kết đã được nêu ra và đã được duyệt. `action_proposal_id` dùng `ON DELETE SET NULL` chứ không `CASCADE`: nguồn gốc của một mục lịch phải sống lâu hơn hàng đề xuất, cùng lựa chọn mà ghi chú 9 đã giải thích cho `translation_id`. `source` nhận `assistant|manual|google` và `sync_state` nhận `local_only|pending_push|synced|remote_only`, đều có `CheckConstraint`; mục `remote_only` là **chỉ đọc trong ứng dụng** — sửa ở đây là đánh nhau với thứ đã tạo ra nó bên kia, và bên thua là bên đồng bộ sau. Huỷ thì đặt `status = 'cancelled'` **chứ không xoá hàng**: có thể đã có nhắc việc bắn đi rồi, và một việc duyệt tuần trước giải thích cho cái lịch người dùng đang nhìn. `timezone` giữ **múi giờ người dùng đã nói**, nằm cạnh mốc thời gian tuyệt đối chứ không thay nó: "9h sáng mai" và khoảnh khắc UTC mà nó quy ra là hai sự thật khác nhau, và chỉ cái thứ nhất còn đúng khi người đó bay sang múi giờ khác.

22. `reminders` là **một hàng cho mỗi lần nhắc**, không phải một cột trên `calendar_events`, vì một sự kiện có thể nợ nhiều lần nhắc (trước một ngày, rồi trước mười phút) và `delivered_at` thuộc về từng lần nhắc chứ không thuộc về sự kiện. Bảng này đồng thời **là hàng đợi của scheduler**: `scan_due_reminders` giành hàng bằng một `UPDATE ... WHERE remind_at <= now() AND delivered_at IS NULL RETURNING ...` duy nhất, nên hai lượt quét chồng nhau **không thể** cùng giành một hàng — mệnh đề `WHERE` của lượt sau không còn khớp. Đó là điều làm việc gửi trùng trở thành **không thể** thay vì *khó xảy ra*, và là điều cho phép một tiến trình vừa khởi động lại bắt kịp mọi thứ nó đã ngủ qua mà không nhắc lại từ đầu. Chỉ mục `ix_reminders_due` đúng là hai cột đó theo đúng thứ tự đó. APScheduler chỉ làm **đồng hồ**, **không dùng job store của nó**: một scheduler giữ job thì phải được báo mỗi khi có nhắc việc mới, phải được báo lại khi bị huỷ, và không biết gì về những cái đến hạn lúc tiến trình đang tắt — một bảng thì không cần thứ nào trong đó (ADR-33).

23. `calendar_links` khoá theo `user_id` như `user_settings`: một người có một liên kết Google hoặc không có, và một id thay thế sẽ cho phép hàng thứ hai mà hệ quả duy nhất là sự kiện bị đẩy lên hai lần. **Token được mã hoá khi lưu** (Fernet, `src/core/crypto.py`) và **thiếu khoá mã hoá thì tính năng tắt hẳn**, không bao giờ lưu dạng rõ: một refresh token không phải dữ liệu của ứng dụng mà là quyền truy cập thường trực vào lịch thật của một người, còn hiệu lực tới khi họ tự thu hồi (ADR-35). Cột `sync_token` là con trỏ incremental của Google — giữ nó là thứ biến mỗi lần kéo thành "có gì đổi từ lần trước" thay vì tải lại toàn bộ; Google cho nó hết hạn, và `410 Gone` nghĩa là bỏ con trỏ rồi chạy một lượt đầy đủ. `last_sync_error` được giữ lại để giao diện nói được **vì sao** lịch không nhúc nhích: im lặng sau một lần đồng bộ hỏng trông y hệt một cái lịch không có gì để đồng bộ.

24. `assistant_chunks` là **kho truy hồi riêng của agent trợ lý**, cố ý không dùng chung `message_embeddings` với agent dịch (ADR-37). Lý do là cơ chế chứ không phải sở thích. Thứ nhất, một chunk **không phải một tin nhắn**: nó có thể gom sáu tin ngắn mà thông tin bị chẻ ra, hoặc cắt một tin dài hai nghìn ký tự làm ba — nên `message_ids` là một mảng, và không có ràng buộc một-một nào với `messages` để đặt khoá ngoại lên. Thứ hai, hai agent chấm trên hai thứ khác nhau và được phép chạy **model nhúng khác nhau** (ADR-39); vector của hai model nằm ở hai không gian, nên mọi truy vấn ở bảng này **bắt buộc** lọc `embedding_model` — thiếu bộ lọc đó thì kết quả trả về vẫn có thứ hạng, chỉ là thứ hạng vô nghĩa, và không có lỗi nào được ném ra. Đây chính là thiếu sót đang tồn tại ở `src/services/semantic_search.py` mà `src/services/glossary.py` đã làm đúng. Thứ ba, `strategy` nằm **trong** ràng buộc duy nhất `(conversation_id, strategy, chunk_index)` để cùng một hội thoại tồn tại song song nhiều cách chunk — đó là điều kiện để so sánh các chiến lược trên đúng cùng một dữ liệu thay vì trên hai lần dựng khác nhau. `parent_index` chỉ có giá trị với chiến lược `parent_child`: chunk con nhỏ để trúng chính xác, rồi nở ra cửa sổ cha trước khi vào prompt. Như `message_embeddings`, đây là **dữ liệu dẫn xuất** — xoá và dựng lại lúc nào cũng được, và `conversation_id` được lặp lại để giới hạn tìm kiếm trong một hội thoại mà không phải join. `starts_at`/`ends_at` là mốc của tin đầu và tin cuối trong chunk, có để trả lời được câu hỏi theo thời gian ("tuần trước chốt gì") mà không phải nạp lại tin gốc.

25. `assistant_user_memory` giữ **ngữ cảnh dài hạn về một người**, thứ không thuộc về bất kỳ hội thoại nào: họ thích được nhắc trước bao lâu, họ phụ trách mảng nào, thứ Hai hằng tuần họ có buổi nào. `conversation_id` cho phép `NULL` đúng vì thế — một sự thật học được trong một nhóm vẫn có thể đúng ở mọi nơi. `kind` nhận `preference|fact|relationship|recurring`, có `CheckConstraint`. Sự thật cũ **không bị xoá và không bị ghi đè**: khi có thông tin thay thế, dòng cũ được trỏ `superseded_by` sang dòng mới. Ghi đè sẽ khiến "người này chưa từng nói gì về việc đó" và "người này từng nói khác và đã đổi ý" trở nên không phân biệt được — cùng lý do mà ghi chú 19 giữ lại hàng đã thu hồi ở `agent_consents`. `source_message_id` dùng `ON DELETE SET NULL`: xoá một tin nhắn không được xoá điều đã học được từ nó, nhưng cũng không được để lại một khoá ngoại trỏ vào hư không. `confidence` có mặt vì trí nhớ này do model suy ra chứ không do người dùng khai, và một suy luận yếu phải được xếp sau một suy luận chắc khi cả hai cùng được nhớ lại. Toàn bộ bảng nằm dưới quyền `store_memory` ở `agent_consents`; chưa cấp thì không có dòng nào được ghi.

26. `assistant_attempts` là **nhật ký đo lường** của agent trợ lý, đúng cách bố trí mà ghi chú 9 đã giải thích cho `translation_attempts` (ADR-16): không phải trạng thái ứng dụng, không có ràng buộc duy nhất (hỏi trợ lý cùng một câu hai lần là hai lượt chạy và đáng hai dòng), và **chỉ** `src/services/assistant_telemetry.py` cùng `scripts/report_metrics.py` được đọc bảng này — các cột được tự do thay đổi theo nhu cầu đo, không hợp đồng nào phụ thuộc vào chúng. `outcome` nhận đúng bảy giá trị có `CheckConstraint`: `answered`, `proposed`, `executed`, `clarified`, `refused`, `empty`, `error`. **Bốn giá trị sau chính là mẫu số còn thiếu** — một lượt bị từ chối vì thiếu quyền, một lượt hỏi ngược lại, một lượt chạy hết mà không thấy gì đều không sinh ra đề xuất nào; tính tỉ lệ "bao nhiêu phần trăm lượt chạy tới được cổng duyệt" mà chỉ đếm trên các lượt đã tới cổng thì không phải là một tỉ lệ. Ba khoá ngoại đều `ON DELETE SET NULL`: xoá một hội thoại, một tài khoản hay một tin nhắn **không được xoá bằng chứng rằng trợ lý đã được hỏi** — cùng lựa chọn ghi chú 9 nêu cho `translation_id`. `proposals_executed` chỉ đếm những đề xuất được duyệt **ngay trong lượt chạy đó**; đề xuất duyệt sau qua endpoint REST thuộc về request kia chứ không thuộc lượt chạy đã kết thúc (ADR-32), và gộp vào đây là gán một lần duyệt cho một lượt chạy đã xong từ trước. `memory_recalled` trên tổng `memory_lines` là thứ **duy nhất** trong hệ thống nói được rằng `assistant_chunks` đang rỗng: bằng 0 ở mọi dòng nghĩa là chưa ai backfill, và không có chỗ nào khác báo điều đó.

### 5.1. Hoàn thiện các điều khiển hội thoại và cài đặt

Các endpoint sau dùng access token của tài khoản đang thao tác. Mọi endpoint
theo `conversation_id` đều kiểm tra thành viên trước khi đọc hoặc thay đổi dữ
liệu.

| Endpoint | Hành vi hợp đồng |
|---|---|
| `GET /conversations/{id}/messages/search?q=...&limit=...&before_created_at=...&before_id=...` | Trả `MessageSearchResponse` gồm `items`, `has_more` và cursor kế tiếp. Kết quả không chứa tin đã gỡ. Có thể khớp `original_text` hoặc bản dịch mà **người gọi** được đọc; không trả cách xưng hô/bản dịch của thành viên khác. |
| `POST /conversations/{id}/messages/{message_id}/translate` | Trả `202 {"message_id", "status":"scheduled"}`. Chỉ thành viên của hội thoại và chỉ tin chưa gỡ. Tác vụ bỏ qua cache, tạo một lượt đo mới và lưu bản dịch mới với phiên bản tăng dần (`version = max_version + 1`) để bảo toàn nguyên vẹn bản dịch lịch sử cùng các đánh giá (feedback) và bản góp ý (translation edits) gắn với phiên bản cũ. Bản dịch mới nhất được ưu tiên hiển thị cho người đọc. Kết quả gửi về client qua `translation_completed`. |
| `PATCH /conversations/{id}/preferences` | Nhận ít nhất một trong `is_pinned`, `is_muted`; luôn là trạng thái đích tường minh, không toggle mù. Hai thuộc tính thuộc về chính `conversation_members` của người gọi. |
| `PUT` / `DELETE /conversations/{id}/messages/{message_id}/saved` | Lưu/bỏ lưu tin nhắn riêng cho người gọi, trả `{message_id, is_saved}`. |
| `PUT` / `DELETE /conversations/{id}/messages/{message_id}/reactions` | Thêm/bỏ một emoji, trả tổng hợp `reactions`. Sau commit server phát `message_reactions_updated` tới mọi thành viên với `conversation_id`, `message_id`, `reactions`. |
| `PATCH /auth/me` | Chỉ nhận `display_name` và/hoặc `bio`; đây là cập nhật một phần, không phải thay thế tài khoản. |
| `GET` / `PATCH /auth/me/settings` | Đọc/cập nhật các cài đặt `auto_translate`, `show_original_by_default`, `translation_tone`, `sound_enabled`, `read_receipts`, `ai_smart_assistance`. `auto_translate` thay đổi bucket nhận bản dịch mới; `read_receipts=false` vẫn cập nhật mốc đã đọc nhưng không phát biên nhận. |

`ConversationDTO` hiện có `is_pinned`, `pinned_at`, `is_muted`; `MessageDTO`
hiện có `is_saved`, `reactions`. Các trường này là trạng thái của **người gọi**
khi đọc danh sách/hội thoại và không được cache hoặc dùng chung giữa tài khoản.

### 5.2. Gọi thoại/video trực tiếp

Gọi chỉ hỗ trợ hội thoại `direct`. `POST /conversations/{id}/calls` tạo phiên
`ringing`, phát `call_incoming` cho đúng người nhận và trả thông tin phiên
nhưng không trả token phòng. Người nhận gọi `POST /calls/{call_id}/accept` hoặc
`reject`; người gọi nhận `call_accepted` rồi lấy token riêng qua
`GET /calls/{call_id}/join`. Cả hai phía kết thúc bằng `POST /calls/{call_id}/end`.
Các sự kiện `call_rejected`, `call_ended`, `call_failed` chỉ mang trạng thái
phiên, tuyệt đối không mang API key/token của nhà cung cấp RTC. Đây là media RTC
bình thường, không có dịch giọng nói, STT, TTS hay phụ đề trực tiếp.

### 5.3. Schema lifecycle của voice message

Migration `a3f1c7e9b2d4` (down revision `9c4d2e7f1a6b`) thêm
`messages.message_type` (`text|voice`, mặc định/backfill `text`) và
`messages.transcription_status` (`null|pending|completed|failed`). Ba CHECK
constraint thực thi bảng invariant ở §3.7.1 ngay tại PostgreSQL: text luôn có
status null; voice pending/failed luôn có text rỗng; completed bắt buộc
`length(trim(original_text)) > 0`.

Không có bảng transcript riêng. `messages.original_text` là canonical transcript
và cũng là nguồn duy nhất mà `DatabaseContextProvider`, search, translation và
các service text-dependent đọc. Vì pending/failed giữ chuỗi rỗng, chúng tự bị
loại khỏi context/search; completed voice tham gia mọi tổ hợp text→voice,
voice→text và voice→voice giống một dòng text. Attachment audio chỉ liên kết qua
`attachments.message_id`; provider file URI/name không được persist.

## 6. Đặc tả lỗi

Áp dụng thống nhất cho cả REST và WebSocket:

```json
{
  "type": "error",
  "code": "AUTH_FAILED | VALIDATION_ERROR | TRANSLATION_TIMEOUT | NOT_FOUND | CONSENT_REQUIRED | INTERNAL_ERROR",
  "message": "Thông điệp dành cho người dùng, không chứa stack trace"
}
```

Ánh xạ mã lỗi sang HTTP status trên giao diện REST:

| `code` | HTTP status |
|---|---|
| `AUTH_FAILED` | 401 |
| `VALIDATION_ERROR` | 422 |
| `NOT_FOUND` | 404 |
| `CONSENT_REQUIRED` | 403 |
| `TRANSLATION_TIMEOUT` | 500 |
| `INTERNAL_ERROR` | 500 |

**`CONSENT_REQUIRED` mang thêm trường `scope`** — tên quyền còn thiếu, lấy từ danh sách ở
§3.15:

```json
{"code": "CONSENT_REQUIRED", "message": "...", "scope": "read_conversations"}
```

Đây là lý do nó không dùng chung `403` trơn với lỗi phân quyền thường: hai lỗi cần hai
hành động khác nhau ở phía client. `403` vì không phải thành viên hội thoại là ngõ cụt,
còn `CONSENT_REQUIRED` là thứ người dùng tự sửa được ngay — giao diện đọc `scope` rồi mở
đúng ô cần bật thay vì bắt họ tự dò trong trang cài đặt.

## 7. Danh mục kiểm tra trước khi hiện thực hoá

- [ ] Tên trường dữ liệu tuân thủ đúng quy định tại §2, §3, §5
- [ ] Schema Pydantic mới được đặt trong `src/schemas/`, không bổ sung vào `src/models/`
- [ ] Mã ngôn ngữ tham chiếu hằng `SUPPORTED_LANGUAGES` (`src/schemas/auth.py`), không khai báo danh sách mới
- [ ] Trường hợp cần bổ sung trường, endpoint hoặc sự kiện: cập nhật tài liệu này và hoàn tất merge trước khi hiện thực hoá
- [ ] Mọi response REST và thông điệp WebSocket xác định được loại thông qua trường `type` hoặc cấu trúc rõ ràng
- [ ] Không phát triển tính năng mới trên hai endpoint kế thừa `/chat` và `/status`
