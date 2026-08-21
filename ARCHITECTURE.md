# TÀI LIỆU KIẾN TRÚC HỆ THỐNG

**Dự án:** LinguaFlow — AI Agent dịch tin nhắn đa ngôn ngữ real-time trong hội thoại
**Mã dự án:** P-217 · **Nhóm thực hiện:** 4U
**Phiên bản:** 1.0 · **Ngày cập nhật:** 10/08/2026 · **Trạng thái:** Đang áp dụng

---

## Mục lục

1. [Tổng quan hệ thống](#1-tổng-quan-hệ-thống)
2. [Phạm vi](#2-phạm-vi)
3. [Kiến trúc thành phần](#3-kiến-trúc-thành-phần)
4. [Luồng dữ liệu](#4-luồng-dữ-liệu)
5. [Yêu cầu phi chức năng](#5-yêu-cầu-phi-chức-năng)
6. [Bảo mật và chính sách lưu trữ dữ liệu](#6-bảo-mật-và-chính-sách-lưu-trữ-dữ-liệu)
7. [Quyết định kiến trúc (ADR)](#7-quyết-định-kiến-trúc-adr)
8. [Triển khai](#8-triển-khai)
9. [Định hướng mở rộng](#9-định-hướng-mở-rộng)
10. [Tài liệu liên quan](#10-tài-liệu-liên-quan)

---

## 1. Tổng quan hệ thống

LinguaFlow là AI Agent tích hợp vào luồng chat 1-1 và chat nhóm, thực hiện dịch tin nhắn giữa các ngôn ngữ theo thời gian thực trên cơ sở ngữ cảnh hội thoại. Hệ thống sử dụng các tin nhắn gần nhất trong cùng cuộc hội thoại làm ngữ cảnh cho mô hình ngôn ngữ, thay vì dịch độc lập từng câu.

Người dùng có thể đối chiếu bản gốc với bản dịch và gửi hiệu chỉnh bản dịch (cơ chế human-in-the-loop) nhằm cải thiện chất lượng theo thời gian.

## 2. Phạm vi

### 2.1. Phạm vi MVP

| Mã | Tính năng | Sprint |
|---|---|---|
| F-01 | Xác thực và thiết lập ngôn ngữ đích | Sprint 1 |
| F-02 | Chat real-time (1-1 và nhóm) | Sprint 1, 2 |
| F-03 | Dịch thuật theo ngữ cảnh (3-5 tin gần nhất) | Sprint 1 |
| F-04 | Chuyển đổi hiển thị bản gốc / bản dịch | Sprint 1 |
| F-05 | Human-in-the-loop (hiệu chỉnh bản dịch, gửi phản hồi) | Sprint 2 |
| F-06 | Chính sách lưu trữ và quyền riêng tư | Sprint 3 |

Định nghĩa chi tiết từng tính năng: xem tài liệu PRD của dự án.

### 2.2. Ngoài phạm vi MVP

Các hạng mục sau thuộc giai đoạn Post-MVP và không được thiết kế chi tiết trong tài liệu này:

- Nhận diện và chuẩn hoá tiếng Việt vùng miền, từ lóng, từ viết tắt
- Glossary doanh nghiệp (quản trị thuật ngữ và tìm kiếm ngữ nghĩa)
- Dịch tin nhắn thoại (pipeline Speech-to-Text)
- Dashboard theo dõi chi phí token
- Tối ưu fan-out theo nhóm ngôn ngữ trong hội thoại nhiều thành viên (xem ADR-03)

## 3. Kiến trúc thành phần

### 3.1. Frontend (React)

| Hạng mục | Mô tả |
|---|---|
| Chức năng | Giao diện chat real-time, hiển thị song ngữ |
| Phạm vi tính năng | Đăng nhập và chọn ngôn ngữ đích (F-01); khung chat 1-1 và nhóm (F-02); chuyển đổi hiển thị bản gốc/bản dịch trên từng tin nhắn (F-04); giao diện hiệu chỉnh bản dịch và gửi phản hồi (F-05) |
| Kết nối real-time | WebSocket client, hỗ trợ tự động kết nối lại khi mất kết nối |
| Quản lý trạng thái | Local component state. Phạm vi MVP chưa yêu cầu store toàn cục (Redux/Zustand) |

### 3.2. Backend (FastAPI)

Backend được tách thành hai tầng với trách nhiệm phân biệt:

**a) WebSocket Gateway** (`src/api/`)

Chỉ đảm nhiệm tầng truyền tải: tiếp nhận và gửi frame WebSocket, xác thực JWT tại thời điểm thiết lập kết nối. Không chứa logic nghiệp vụ.

**b) Chat Service** (`src/services/chat_service.py`)

Đảm nhiệm logic nghiệp vụ: kiểm tra quyền thành viên trong cuộc hội thoại, lưu tin nhắn gốc, truy vấn `preferred_language` của người nhận, gọi Agent, chuyển tiếp các sự kiện từ Agent (chunk, completed) tới Gateway.

Agent không phụ thuộc trực tiếp vào WebSocket mà trao đổi dữ liệu thông qua Chat Service. Thiết kế này giữ Agent độc lập với tầng truyền tải, thuận lợi cho việc kiểm thử và tái sử dụng trên kênh giao tiếp khác.

**c) Thiết kế API**

| Giao thức | Phạm vi sử dụng |
|---|---|
| WebSocket | Luồng chat và streaming bản dịch. REST không đáp ứng được yêu cầu truyền hai chiều theo thời gian thực |
| REST | Các thao tác không yêu cầu real-time: đăng nhập, cấu hình ngôn ngữ, gửi phản hồi, truy xuất lịch sử hội thoại |

**d) Xác thực**

Cơ chế JWT (`src/core/security.py`), tài khoản được định danh sẵn qua script seed. Chi tiết endpoint: xem [`docs/CONTRACT.md`](docs/CONTRACT.md) §3.

Trình tự gọi giữa các tầng: xem [Sequence Diagram](docs/architecture_diagram.md#5-sequence-diagram).

### 3.3. AI Agent (LangGraph)

| Hạng mục | Mô tả |
|---|---|
| Loại agent | State machine tuỳ biến. Không áp dụng pattern ReAct do luồng dịch không yêu cầu agent tự quyết định gọi tool lặp lại, chỉ cần pipeline có rẽ nhánh điều kiện và đường fallback |
| State | `source_language`, `target_language`, `original_text`, `context_messages`, `translated_text`, `translation_id`, `is_valid`, `is_fallback`, `model`, `latency_ms`, `error`, `telemetry`. Định nghĩa bắt buộc tại [`docs/CONTRACT.md`](docs/CONTRACT.md) §2. Riêng các khoá **bên trong** `telemetry` không thuộc hợp đồng — xem ADR-16 |
| Chuỗi node | `detect_language` (hai tầng: langdetect rồi LLM khi mâu thuẫn, xem ADR-11) → rẽ nhánh theo `source_language == target_language` → `build_context` → `customize` → `translate` → `validate_output`, song song với ghi CSDL bất đồng bộ. `customize` **không gọi model**: nó chỉ đọc lĩnh vực và đối tượng đã được suy luận sẵn ở nền (ADR-24) và dựng mục `# Audience` của prompt; mọi lỗi ở đó suy giảm về prompt không có mục này |
| Cơ chế fallback | Khi `validate_output` thất bại hoặc LLM timeout, hệ thống trả về `original_text` và không chặn luồng chat |
| Mô hình ngôn ngữ | Lựa chọn qua biến môi trường `LLM_PROVIDER`. Mặc định Groq (`llama-3.3-70b-versatile`); hỗ trợ `deepseek`, `gemini`, `openai`. Xem ADR-10 |

Việc lựa chọn provider chính thức được quyết định trên cơ sở kết quả đánh giá Golden Set.

### 3.4. Cơ sở dữ liệu

| Hạng mục | Mô tả |
|---|---|
| Hệ quản trị | PostgreSQL (`postgresql+asyncpg`) kèm extension `pgvector` ở **mọi** môi trường, kể cả máy phát triển và bộ kiểm thử (ADR-22). Máy phát triển lấy nó bằng `docker compose up -d postgres`; production trỏ `DATABASE_URL` sang Railway/Supabase. SQLite không còn dùng được: schema có cột `vector` |
| ORM | SQLAlchemy 2.0 async (`src/database/`) |
| Vai trò | Vừa lưu trữ lịch sử hội thoại dài hạn, vừa là nguồn cung cấp ngữ cảnh cho Agent (xem ADR-01) |
| Bảng dữ liệu | `users`, `conversations`, `conversation_members`, `messages`, `translation_results`, `feedbacks`, `translation_attempts` |
| Vector Store | Không sử dụng trong phạm vi MVP (xem ADR-01) |

`translation_attempts` là nhật ký đo lường, không phải trạng thái ứng dụng: nó tồn tại để trả lời NFR-03 và chỉ được đọc bởi `src/services/metrics.py` cùng `scripts/report_metrics.py`. Xem ADR-16.

Schema chi tiết: xem [ER Diagram](docs/architecture_diagram.md#4-er-diagram).

## 4. Luồng dữ liệu

1. Client gửi tin nhắn qua WebSocket. Gateway chuyển tiếp tới Chat Service.
2. Chat Service kiểm tra quyền thành viên và **lưu tin nhắn gốc đồng bộ** vào bảng `messages`. Bước này bắt buộc đồng bộ do các bước sau cần `message_id`. Trường `source_language` tại thời điểm này là giá trị tạm (xem [`docs/CONTRACT.md`](docs/CONTRACT.md) §4).
3. Chat Service truy vấn tập `DISTINCT preferred_language` của các thành viên trong cuộc hội thoại và gọi Agent một lần cho mỗi ngôn ngữ đích.
4. Agent xác định ngôn ngữ nguồn. Nếu trùng ngôn ngữ đích, hệ thống trả về bản gốc và bỏ qua bước 5-7.
5. Trường hợp khác ngôn ngữ, Chat Service phát `original_text` kèm `translation_status = "streaming"` tới toàn bộ thành viên trong cuộc hội thoại, bao gồm cả người gửi, không chờ kết quả dịch.
6. Agent truy vấn 3-5 tin nhắn gần nhất cùng `conversation_id` làm ngữ cảnh, xây dựng prompt và gọi LLM ở chế độ streaming. Mỗi chunk được chuyển tiếp qua Chat Service tới client.
7. Kết quả dịch được kiểm tra tính hợp lệ. Khi xảy ra lỗi hoặc timeout, hệ thống trả về bản gốc với `is_fallback = true`.
8. Sau khi hoàn tất, bản dịch được **ghi bất đồng bộ** vào `translation_results`. Giá trị `translation_id` được gửi kèm sự kiện `translation.completed` phục vụ tính năng F-05.
9. Trường hợp người dùng hiệu chỉnh bản dịch (F-05), dữ liệu được ghi vào bảng `feedbacks` và liên kết qua `translation_id`.

Trình tự đầy đủ bao gồm giao thức streaming: xem [Sequence Diagram](docs/architecture_diagram.md#5-sequence-diagram).

## 5. Yêu cầu phi chức năng

| Mã | Yêu cầu | Chỉ tiêu | Biện pháp |
|---|---|---|---|
| NFR-01 | Độ trễ dịch | Dưới 1 giây cho một câu văn bản thông thường | Sử dụng streaming API, hiển thị bản dịch theo từng chunk |
| NFR-02 | Khả năng chịu lỗi | Lỗi hoặc timeout của LLM không làm mất tin nhắn | Luồng gửi tin gốc độc lập với luồng dịch (bước 2 và bước 5-7 không phụ thuộc nhau); chuỗi dự phòng hai tầng mô tả ở §5.1 |
| NFR-03 | Khả năng giám sát | Mọi lượt thử dịch đều để lại một dòng dữ liệu, đủ để trả lời bằng SQL: chất lượng ra sao, provider và model nào thực sự phục vụ, cặp ngôn ngữ nào | Bảng `translation_attempts` ghi một dòng cho mỗi cặp (tin nhắn × ngôn ngữ đích) được thử, **kể cả bốn trường hợp không sinh ra bản dịch** (ADR-16); `translation_results` giữ `latency_ms` và `model` phục vụ hiển thị; Langfuse cung cấp trace và chi phí token, có kiểm tra xác thực lúc khởi động. Đọc số liệu bằng `make metrics` hoặc `GET /api/v1/stats` |

### 5.1. Chuỗi dự phòng khi dịch thất bại

Khi LLM lỗi, timeout, hoặc trả về bản dịch không hợp lệ (rỗng, hoặc dài bất thường do mô hình giải thích thay vì dịch), Agent đi lần lượt qua hai tầng:

| Tầng | Thành phần | Kết quả | `model` | `is_fallback` |
|---|---|---|---|---|
| 1 | LLM đã cấu hình qua `LLM_PROVIDER` | Bản dịch chính | Tên model thật | `false` |
| 2 | `deep-translator` (ADR-07) | Bản dịch dự phòng | `deep-translator:google` | `true` |
| 3 | Không gọi ai | Nguyên văn bản gốc | Rỗng | `true` |

Ba ràng buộc bắt buộc giữ khi sửa `src/services/fallback_translator.py`:

1. **Không bao giờ raise.** Thiếu package, mất mạng, bị giới hạn tần suất, cặp ngôn ngữ không hỗ trợ — tất cả đều trả `None`, và node giữ nguyên bản gốc đã ghi sẵn trong state.
2. **Không chặn event loop.** `deep-translator` là thư viện đồng bộ nên phải chạy trong worker thread kèm timeout (`FALLBACK_TRANSLATOR_TIMEOUT_SECONDS`). Timeout giải phóng coroutine nhưng không huỷ được thread — chấp nhận được vì thread chỉ giữ một request HTTP.
3. **`is_fallback` vẫn là `true` khi tầng 2 thành công.** Kết quả không đến từ LLM đã cấu hình, nên Frontend phải tiếp tục hiển thị chỉ báo chất lượng suy giảm. Trường `model` cho biết bản dịch do tầng nào tạo ra.

**Điều kiện chuyển sang tầng 2.** Ngoài lỗi và timeout của LLM, `validate_output` còn đẩy sang tầng dự phòng khi bản dịch rỗng, dài bất thường so với bản gốc, **đọc lại chính chỉ dẫn của agent**, **là câu từ chối của model thay vì bản dịch**, **chứa định danh mà tin nhắn gốc không có**, **thiếu định danh mà tin nhắn gốc có**, hoặc **không đúng ngôn ngữ đích** (ADR-13, ADR-21). Trường hợp cuối bắt được câu từ chối của model — vốn quá ngắn để lọt quy tắc độ dài. Đầu ra của tầng 2 cũng chịu đúng kiểm tra ngôn ngữ đó trước khi được chấp nhận, vì nó không quay lại `validate_output`; hai kiểm tra rò rỉ thì không lặp lại, do tầng 2 chỉ nhận tin nhắn gốc chứ không nhận ngữ cảnh.

**Timeout ở mức toàn bộ lượt chạy không thuộc Agent.** Hệ thống chỉ có timeout theo từng lần gọi (`LLM_TIMEOUT_SECONDS`, `FALLBACK_TRANSLATOR_TIMEOUT_SECONDS`). Hạn thời gian cho cả lượt dịch thuộc về bên gọi — Chat Service bọc `graph.ainvoke` trong `asyncio.wait_for` — vì chỉ bên gọi mới biết người dùng còn chờ được bao lâu. Xem ADR-14.

### 5.2. Guardrail đầu vào và đầu ra

Các lớp kiểm tra, cài đặt trong `src/agents/guardrails.py` (ADR-12, ADR-13, ADR-21). Tổng chi phí trên đường thành công khoảng 2ms, tức 0,2% ngân sách của NFR-01. Bản rà soát đầy đủ theo **kênh dữ liệu** — gồm cả những kênh nằm ngoài agent (log, tracing, cache, fan-out) và những gì cố ý không làm — ở [`docs/GUARDRAILS.md`](docs/GUARDRAILS.md).

| Lớp | Kiểm tra | Khi vi phạm |
|---|---|---|
| Đầu vào | `original_text` tối đa 2000 ký tự | Ghi `error`, trả nguyên bản. Không cắt bớt — nửa bản dịch tệ hơn không dịch |
| Đầu vào | `target_language` phải đúng dạng ISO 639-1 hai chữ cái thường | Ghi `error`, trả nguyên bản. Giá trị này đi thẳng vào system prompt và đến từ trường hồ sơ người dùng tự sửa được |
| Prompt | Mỗi dòng ngữ cảnh bị gộp xuống dòng, escape dấu ngoặc nhọn, cắt còn 500 ký tự | Áp dụng im lặng tại `build_context_block` |
| Prompt | Thẻ bao tin nhắn mang nonce ngẫu nhiên theo từng request | Không có "vi phạm": người gửi đơn giản là không đoán được thẻ để đóng sớm |
| Đầu ra | Lớp bọc do model tự thêm (khối suy luận, thẻ lặp lại, code fence, nhãn, ngoặc kép, ghi chú cuối) bị gỡ | Áp dụng im lặng tại `strip_translation_scaffolding`, ghi cờ `scaffolding_stripped` vào telemetry |
| Đầu ra | Bản dịch không được đọc lại chỉ dẫn của agent | Chuyển sang tầng dự phòng, `fallback_reason = prompt_disclosure` |
| Đầu ra | Bản dịch chỉ được chứa định danh (email, dãy ≥ 9 chữ số, token dạng khoá) mà tin nhắn gốc đã có | Chuyển sang tầng dự phòng, `fallback_reason = leaked_identifier`. Chỉ ghi log **số lượng**, không ghi giá trị — nhật ký không phải chỗ để lộ tiếp |
| Đầu ra | Bản dịch không được là câu từ chối của model (chỉ khớp dấu hiệu model tự xưng, chỉ xét khi bản dịch ≤ 200 ký tự, và bỏ qua nếu chính tin gốc cũng từ chối) | Chuyển sang tầng dự phòng, `fallback_reason = refusal` |
| Đầu ra | Email, URL và dãy ≥ 9 chữ số **có trong tin gốc** phải còn trong bản dịch | Chuyển sang tầng dự phòng, `fallback_reason = dropped_identifier` |
| Đầu ra | Đoạn văn xuôi ≥ 40 ký tự trùng nguyên văn với một dòng ngữ cảnh mà tin gốc không có | **Chỉ đo, chưa chặn**: ghi `context_echo` vào telemetry và ghi log *độ dài* đoạn trùng, bản dịch vẫn được giao |
| Ngữ cảnh | Tin đã thu hồi (`deleted_at`) và tin không có văn bản không được nạp vào prompt | Lọc ngay trong truy vấn của `DatabaseContextProvider` |
| Đầu ra | Ngôn ngữ bản dịch phải khớp `target_language`, kiểm khi bản dịch dài từ 20 ký tự | Chuyển sang tầng dự phòng |

Hàm phụ thuộc thư viện ngoài thì **fail open** (langdetect lỗi → chấp nhận bản dịch), hàm thuần số học và regex thì **fail closed**. Nguyên tắc này giữ cho một lỗi phụ thuộc không đẩy toàn bộ lưu lượng sang provider dự phòng.

## 6. Bảo mật và chính sách lưu trữ dữ liệu

> **Ghi chú về bảo mật:** Hệ thống áp dụng chính sách lưu trữ an toàn và kiểm soát truy cập. Agent yêu cầu đọc nội dung tin nhắn dạng plaintext để thực hiện dịch thuật và cung cấp ngữ cảnh cho mô hình ngôn ngữ.

### 6.1. Phạm vi lưu trữ

- Toàn bộ nội dung hội thoại (bản gốc và bản dịch) được lưu dài hạn trong `messages` và `translation_results`. Đây là hành vi tiêu chuẩn của ứng dụng chat nhằm phục vụ nhu cầu tra cứu lịch sử của người dùng.
- Ngữ cảnh cung cấp cho LLM không phải là kho lưu trữ độc lập mà là kết quả truy vấn 3-5 bản ghi gần nhất từ bảng `messages`. Do không tồn tại bản sao độc lập, hệ thống không cần cơ chế xoá ngữ cảnh khi kết thúc phiên.

### 6.2. Kiểm soát truy cập

- Mã hoá at-rest được áp dụng ở môi trường production (Supabase bật mặc định). Môi trường phát triển sử dụng SQLite không có mã hoá, do đó không được đưa dữ liệu thật vào môi trường này.
- API key và secret được cấu hình qua tệp `.env`, không hard-code trong mã nguồn.
- Kiểm tra quyền truy cập theo `conversation_id` và `user_id` được thực hiện tại tầng Chat Service.

### 6.3. Xoá dữ liệu theo yêu cầu

Tính năng xoá hội thoại theo yêu cầu người dùng (right-to-be-forgotten) không thuộc phạm vi MVP. Schema hiện tại với khoá ngoại xác định rõ ràng cho phép hiện thực hoá tính năng này theo `conversation_id` khi cần.

### 6.4. Chuyển dữ liệu ra dịch vụ bên thứ ba

Nội dung tin nhắn của người dùng rời khỏi hệ thống qua ba kênh. Cả ba đều tắt được bằng cấu hình, nhưng chỉ kênh đầu tiên là bắt buộc để tính năng dịch hoạt động.

| Kênh | Dữ liệu gửi đi | Ràng buộc pháp lý | Cơ chế tắt |
|---|---|---|---|
| LLM provider theo `LLM_PROVIDER` (Groq, DeepSeek, Gemini, OpenAI) | `original_text` và tối đa 5 tin nhắn ngữ cảnh gần nhất | Theo điều khoản dịch vụ của từng nhà cung cấp; truy cập bằng API key của tài khoản | Không tắt được — đây là kênh thực hiện việc dịch |
| `deep-translator` → endpoint web của Google Translate (ADR-07) | Toàn văn `original_text` | **Endpoint không chính thức, không dùng API key, do đó không có hợp đồng và không có thoả thuận xử lý dữ liệu (DPA)** | `FALLBACK_TRANSLATOR_ENABLED=false` |
| Langfuse (F-03.4) | Toàn bộ prompt và completion, tức bao gồm cả tin nhắn lẫn ngữ cảnh | Theo điều khoản của Langfuse Cloud | Để trống `LANGFUSE_PUBLIC_KEY` và `LANGFUSE_SECRET_KEY` |

**Hệ quả cần lưu ý khi vận hành:**

1. Kênh dự phòng kích hoạt trên *mọi* đường fallback — thiếu API key, bị giới hạn tần suất, lỗi mạng, timeout, hoặc bản dịch không hợp lệ. Một sự cố tạm thời ở LLM provider vì vậy làm toàn bộ tin nhắn đang xử lý được gửi sang Google.
2. Người nhận chỉ thấy `is_fallback = true`, và theo `docs/CONTRACT.md` §4 Frontend hiển thị cờ này như chỉ báo chất lượng, không phải chỉ báo về quyền riêng tư. Hệ thống hiện không thông báo cho người dùng về việc chuyển dữ liệu này.
3. **Không được xử lý dữ liệu người dùng thật khi `FALLBACK_TRANSLATOR_ENABLED=true` ở bất kỳ môi trường nào chịu yêu cầu về thoả thuận xử lý dữ liệu.** Với môi trường phát triển, ràng buộc tại §6.2 về việc không đưa dữ liệu thật vào vẫn áp dụng đầy đủ.

## 7. Quyết định kiến trúc (ADR)

| Mã | Nội dung quyết định | Lựa chọn | Căn cứ |
|---|---|---|---|
| ADR-01 | Nguồn ngữ cảnh cho LLM | Truy vấn trực tiếp bảng `messages`; không sử dụng Vector Store trong MVP | Yêu cầu "3-5 tin gần nhất" là truy vấn tuần tự theo thời gian, không cần tìm kiếm theo độ tương đồng ngữ nghĩa. Vector Store chỉ cần thiết cho Glossary ở giai đoạn Post-MVP. Việc duy trì một nguồn dữ liệu duy nhất loại bỏ rủi ro sai lệch giữa hai hệ thống và giảm số thành phần phải vận hành |
| ADR-02 | Giao thức real-time | WebSocket | Yêu cầu truyền hai chiều liên tục. SSE chỉ hỗ trợ chiều server đến client, không phù hợp với luồng chat |
| ADR-03 | Tối ưu fan-out theo nhóm ngôn ngữ | Không thực hiện trong Sprint 1 | Đây là cải tiến hiệu năng, không phải yêu cầu chức năng. Việc tối ưu được thực hiện sau khi có số liệu đo thực tế, tránh thiết kế vượt nhu cầu khi luồng end-to-end chưa hoàn chỉnh |
| ADR-04 | Framework Backend | FastAPI | Hỗ trợ async nguyên bản, phù hợp với tác vụ I/O-bound (chờ phản hồi LLM); tự động sinh tài liệu API |
| ADR-05 | Điều phối Agent | LangGraph | Luồng xử lý yêu cầu rẽ nhánh điều kiện và đường fallback. Chain tuyến tính không đáp ứng được |
| ADR-06 | Cơ sở dữ liệu | SQLite async (dev) và PostgreSQL (prod), ORM SQLAlchemy 2.0 async. **Alembic là nơi duy nhất định nghĩa schema** (sửa ngày 15/08, xem ADR-18) | Môi trường phát triển không yêu cầu cài đặt PostgreSQL cục bộ, chỉ thay đổi `DATABASE_URL` khi triển khai. PostgreSQL hỗ trợ kiểu JSON và có thể bật `pgvector` cho Glossary mà không phải thay đổi hệ quản trị. **Quyết định ban đầu là không dùng Alembic trong MVP** — dữ liệu phát triển chỉ gồm vài tài khoản seed nên `make reset-db` (xoá và tạo lại) là đủ. Điều kiện xem xét lại ghi ngay trong quyết định đó, "khi cơ sở dữ liệu production được cấp phát", đã xảy ra: có người dùng thật thì mỗi lần đổi schema sẽ xoá sạch tài khoản và lịch sử trò chuyện của họ, và trên một cơ sở dữ liệu quản lý thì cũng không có "tệp" nào để xoá. Từ nay `alembic upgrade head` chạy trong `CMD` của container trước `uvicorn`, `create_tables()` đã bị gỡ khỏi mã nguồn, và `make reset-db` là `downgrade base` + `upgrade head`. Bộ kiểm thử vẫn dùng `Base.metadata.create_all` trên SQLite trong bộ nhớ: kiểm thử kiểm tra mã nguồn hiện tại, không kiểm tra lịch sử migration |
| ADR-07 | Provider dịch dự phòng | **Tích hợp `deep-translator` (Google Translate) làm tầng dự phòng khi LLM lỗi** | Đề bài yêu cầu hệ thống có cơ chế dịch dự phòng, nên đây là ràng buộc phạm vi chứ không phải lựa chọn kỹ thuật. So với NLLB, `deep-translator` không cần API key, không cần self-host mô hình và cài bằng một dòng `pip`, phù hợp với hạ tầng gói miễn phí của nhóm. Đánh đổi đã chấp nhận: endpoint web của Google Translate là không chính thức nên phải coi việc gián đoạn là tình huống thường gặp — vì vậy đường trả về nguyên bản vẫn được giữ nguyên phía sau, và toàn bộ lỗi của provider này đều bị nuốt thành `None` (NFR-02). Tắt bằng `FALLBACK_TRANSLATOR_ENABLED=false`. Chi tiết §5.1 |
| ADR-08 | Lớp cache (Redis) | Không sử dụng trong MVP | Truy vấn 3-5 bản ghi gần nhất đáp ứng yêu cầu hiệu năng ở quy mô MVP. Việc bổ sung Redis làm tăng số thành phần phải vận hành khi chưa có số liệu chứng minh nhu cầu. Sẽ xem xét lại nếu đo được độ trễ truy vấn CSDL là điểm nghẽn |
| ADR-09 | Ngôn ngữ Backend | Python/FastAPI thống nhất toàn hệ thống | LangGraph và các SDK của LLM đều là Python. Sử dụng thống nhất một ngôn ngữ với Agent giúp giảm số runtime phải vận hành, phù hợp với quy mô nhóm hiện tại |
| ADR-10 | Provider LLM | Factory đa provider điều khiển qua `LLM_PROVIDER`; **mặc định và khuyến nghị dùng Groq** | Số liệu đo trên cùng 3 mẫu: Groq 2610ms so với Gemini 8441ms cho một tin nhắn, tức nhanh hơn 3.2 lần. Ngoài ra gói miễn phí của Gemini chỉ cho **20 request mỗi ngày** cho `gemini-2.5-flash`, không đủ cho một buổi demo, nên Gemini chỉ giữ vai trò dự phòng khi thử nghiệm. OpenAI yêu cầu tài khoản còn credit. Cơ chế factory cho phép chuyển provider mà không sửa mã nguồn. DeepSeek tuân thủ chuẩn OpenAI-compatible nên tái sử dụng `langchain-openai` qua tham số `base_url` |
| ADR-11 | Xác định ngôn ngữ nguồn | Hai tầng: `langdetect` cục bộ trước, chỉ gọi LLM khi kết quả mâu thuẫn với `preferred_language` của người gửi | LLM detect tốn 1285ms mỗi tin nhắn, chiếm 49% tổng thời gian xử lý. `langdetect` chạy cục bộ hết khoảng 2ms. Trường hợp phổ biến nhất là người dùng viết đúng ngôn ngữ đã cài đặt, khi đó hai nguồn trùng nhau và không cần gọi LLM. Không dùng `langdetect` một mình vì độ chính xác kém với câu ngắn (chuỗi "Ok anh" bị nhận nhầm thành tiếng Tagalog), nên khi có mâu thuẫn phải để LLM phân xử. Kết quả đo: tổng thời gian giảm từ 2610ms xuống 1501ms |
| ADR-12 | Xử lý nội dung không tin cậy trong prompt | Cô lập bằng thẻ phân định `<conversation_history>` và `<message>`, kèm làm sạch từng dòng ngữ cảnh (gộp xuống dòng và ký tự điều khiển thành khoảng trắng, **escape dấu ngoặc nhọn thành `&amp;lt;`/`&amp;gt;`**, giới hạn 500 ký tự mỗi dòng) và giới hạn 2000 ký tự cho tin nhắn. **Không** cố phát hiện ý đồ tấn công | `build_context_block` trước đây nối các dòng ngữ cảnh bằng ký tự xuống dòng, nên một tin nhắn chứa xuống dòng có thể giả mạo tiêu đề phần thứ hai và chiếm quyền điều khiển bản dịch. Nguy hiểm hơn dạng tự tấn công thông thường ở chỗ ngữ cảnh do **người khác** trong hội thoại viết ra, tức A có thể chiếm quyền bản dịch của B. Gộp xuống dòng một mình là chưa đủ — thẻ giả mạo vẫn nằm inline và vẫn đọc được như cấu trúc, nên phải escape dấu ngoặc nhọn; việc escape không tốn gì vì dòng ngữ cảnh chỉ được model *đọc*, không bao giờ xuất hiện trong bản dịch trả cho người nhận. Riêng phần thân tin nhắn không escape (sẽ làm hỏng bản dịch đầu ra) — rủi ro ở đây thấp hơn hẳn vì đó là tự tấn công: người gửi chỉ thao túng được bản dịch tin nhắn của chính mình, và phần này nằm cuối prompt nên không có chỉ dẫn tin cậy nào phía sau để ghi đè. **Phần rủi ro còn lại đó nay được đóng bằng nonce:** thẻ bao tin nhắn mang một định danh ngẫu nhiên sinh lại cho từng request (`<message_1a2b3c4d>`, `new_prompt_nonce`), và system prompt gọi đúng tên thẻ đó, nên người gửi không đoán được thẻ để đóng sớm. Cách này giữ nguyên quyết định *không* escape thân tin nhắn — văn bản vẫn đi qua nguyên vẹn, chỉ có ranh giới là không giả mạo được. Việc làm sạch loại bỏ chính khả năng giả mạo cấu trúc, nên nó là biện pháp giảm thiểu thực sự; còn một bộ phát hiện ý đồ sẽ thêm độ trễ và dương tính giả vào một pipeline mà trường hợp xấu nhất vốn đã là trả nguyên bản an toàn. `target_language` cũng được kiểm tra hình dạng ISO 639-1 trước khi nội suy vào system prompt, do giá trị này đến từ trường hồ sơ người dùng tự sửa được |
| ADR-13 | Kiểm tra tính hợp lệ của bản dịch đầu ra | Bản dịch bị từ chối khi `langdetect` nhận ra nó **vẫn đúng ngôn ngữ nguồn** trong khi đích khác nguồn. **Không** kiểm theo kiểu "có đúng ngôn ngữ đích không", **không** gọi LLM lần hai, **không** dùng danh sách cụm từ từ chối. Áp dụng cho cả `validate_output` lẫn `fallback_translate` | Bắt được ba dạng hỏng mà quy tắc tỷ lệ độ dài bỏ sót khi phản hồi ngắn: model từ chối (`"I can't help with that."` chỉ 24 ký tự, dưới ngưỡng 200 nên trước đây được giao cho người nhận với `is_valid = true`), trả lại nguyên văn chưa dịch, và trả lời tin nhắn thay vì dịch. **Phương án đầu tiên — so bản dịch với `target_language` — đã bị bác bỏ sau khi đo thực tế.** `langdetect` sai một cách tự tin trên đúng loại văn bản sản phẩm này nhắm tới: chuỗi `"Hotfix merged, CI green now"` bị nhận là tiếng Hà Lan ở mức 0.86, `"Docker Kubernetes Jenkins CI/CD pipeline"` bị nhận là tiếng Đức ở mức 0.9999. Cách đó loại bỏ chính những bản dịch đúng của tin nhắn kỹ thuật rồi trả về nguyên bản chưa dịch — ngược hẳn mục đích. Nâng ngưỡng độ dài không cứu được (ca tiếng Đức dài 40 ký tự) và đòi thêm biên tin cậy cũng không. Cách hiện tại chỉ yêu cầu bộ nhận diện **đồng ý với một giá trị đã biết** là ngôn ngữ nguồn do `detect_language` xác định; một lần nhận nhầm sang ngôn ngữ thứ ba bất kỳ không còn chứng minh điều gì và không gây hậu quả gì. Chấp nhận bỏ sót hơn là báo nhầm: bỏ sót một câu từ chối chỉ hỏng một tin nhắn, còn báo nhầm làm giảm chất lượng mọi tin nhắn kỹ thuật trong hội thoại. Chỉ chạy khi bản dịch dài từ 20 ký tự; khi thư viện lỗi hoặc không nhận diện được thì bản dịch được chấp nhận, tránh việc một lỗi phụ thuộc đẩy toàn bộ lưu lượng sang provider dự phòng. **Sửa đổi 19/08 — bổ sung một bộ dò từ chối hẹp, đảo lại phần "không dùng danh sách cụm từ từ chối" ở trên.** Lý do: quy tắc ngôn ngữ chỉ nhìn thấy câu từ chối viết bằng *ngôn ngữ nguồn*. Câu từ chối viết bằng đúng *ngôn ngữ đích* — dạng phổ biến nhất, vì model vừa được yêu cầu trả lời bằng ngôn ngữ đó — có `detected == target`, tức giống hệt một bản dịch đúng, lại ngắn hơn ngưỡng 200 ký tự của quy tắc độ dài, nên nó đi lọt toàn bộ hàng rào và được giao cho người nhận với `is_valid = true`: nội dung thật của người gửi biến mất mà không để lại dấu vết nào. Đây đúng là ca mà tin nhắn nghe có vẻ nhạy cảm (hỏi mật khẩu, hỏi quyền truy cập) tạo ra, tức nó tấn công thẳng vào yêu cầu "bản dịch phải giữ nguyên thông tin". Danh sách được thu hẹp tới mức chỉ còn các cụm mà **model nói về chính nó** (`as an ai`, `i can't assist`, `tôi không thể dịch`, `với tư cách là một AI`, …) chứ không phải mọi phủ định — "tôi không đi họp được" là từ vựng hội thoại bình thường và phải dịch như thường. Hai chốt chặn dương tính giả là điều kiện để quyết định này còn giá trị: (a) nếu **chính tin gốc** cũng khớp một dấu hiệu thì bỏ qua, để người dùng vẫn từ chối được trong hội thoại; (b) chỉ xét bản dịch ≤ 200 ký tự, vì dài hơn thế thì cụm đó là nội dung chứ không phải model đang thoái thác. Phần phòng ngừa nằm ở prompt (ràng buộc 7 và 8 trong `prompts.py`: tin nhắn là dữ liệu cần dịch, không được từ chối/che/lược bớt) — bộ dò chỉ bắt phần lọt lưới |
| ADR-14 | Ranh giới an toàn AI trong phạm vi MVP | Guardrail giới hạn ở ba lớp: chặn kích thước đầu vào, cô lập văn bản không tin cậy trong prompt, và kiểm tra tính hợp lệ của đầu ra. **Không** có bộ phân loại kiểm duyệt nội dung, phát hiện độc hại hay PII; **không** giới hạn tần suất theo người dùng; **không** ngân sách token; **không** timeout ở mức agent | Hệ thống *dịch* nội dung người dùng chứ không *sinh* nội dung mới, nên bề mặt rủi ro hẹp hơn một trợ lý hội thoại: mô hình không được yêu cầu đưa ra quan điểm hay lời khuyên. Mọi đường lỗi đều đã suy giảm về việc trả nguyên bản (NFR-02), tức trường hợp xấu nhất là người nhận đọc tin chưa dịch chứ không phải nhận nội dung sai lệch. Ba hạng mục bị loại đều thuộc tầng API (`src/api/routes.py`, do nhánh khác sở hữu) hoặc thuộc Post-MVP theo phạm vi F-01..F-06. Timeout ở mức agent thuộc về bên gọi (`asyncio.wait_for` quanh `graph.ainvoke`), mà Chat Service chưa tồn tại. Sẽ xem xét lại khi hệ thống phục vụ người dùng ngoài nhóm |
| ADR-15 | Công bố luồng dữ liệu ra dịch vụ bên thứ ba | Ghi đầy đủ ba kênh chuyển dữ liệu tại §6.4, mỗi kênh kèm cơ chế tắt bằng cấu hình | Trước thay đổi này, `deep-translator` chỉ được mô tả như kỹ thuật bảo đảm sẵn sàng tại ADR-07 và §5.1; không tài liệu nào nêu rằng nó gửi toàn văn tin nhắn tới một endpoint không có hợp đồng xử lý dữ liệu. Langfuse cũng gửi toàn bộ prompt nhưng không xuất hiện ở mục bảo mật. Một luồng dữ liệu không được ghi nhận thì không thể được đánh giá rủi ro, nên việc công bố là điều kiện cần trước khi hệ thống nhận dữ liệu thật |
| ADR-16 | Nơi lưu số liệu đo của Agent | **Bảng mới `translation_attempts`**, tách khỏi `translation_results`; không dùng Prometheus/Grafana | Bốn đường ra của luồng dịch — timeout, exception, passthrough và bản dịch rỗng — **không sinh dòng nào** trong `translation_results`. Mọi tỷ lệ tính trên bảng đó vì thế đều chia cho một mẫu số đã loại sẵn phần lớn các ca hỏng: "tỷ lệ fallback" không đo được vì chính cái bị fallback lại không được ghi. Thêm cột vào `translation_results` không giải quyết được điều này *và* còn đòi `make reset-db` (ADR-06), trong khi bảng mới thì `create_all` tạo được mà không đụng dữ liệu cũ. Hai bảng cũng khác nhau về bản chất: `translation_results` là trạng thái ứng dụng, có ràng buộc duy nhất, cột nằm trong hợp đồng và được client đọc; `translation_attempts` là nhật ký chỉ ghi thêm, không ràng buộc duy nhất (chạy lại là một lượt thử mới), và cột được tự do đổi theo nhu cầu đo. Không chọn Prometheus/Grafana vì dự án chưa có scraper — một endpoint không ai đọc chỉ là hình thức, còn hai service trong compose là chi phí vận hành thật cho một dự án 6 tuần. Khoá `attempt_id` được sinh trước khi chạy graph và dùng làm cả PK lẫn thuộc tính trace, nên tra được hai chiều giữa Langfuse và cơ sở dữ liệu |
| ADR-17 | Phương pháp đánh giá chất lượng dịch | LLM-as-judge, **chấm một lần mỗi mẫu**, có cho judge xem ngữ cảnh hội thoại; không chấm điểm thành phần, không chạy lặp để đo dao động | Không có bộ tham chiếu do người chấm, và việc thuê người chấm 53 mẫu × mỗi lần đổi provider nằm ngoài khả năng của nhóm. Judge **phải** được xem `context_messages`: tiêu chí chấm vốn có mục "đại từ và chủ ngữ được khôi phục đúng theo ngữ cảnh", mà trước đây judge chưa bao giờ được cho xem ngữ cảnh nào — với một sản phẩm dịch theo ngữ cảnh thì đó là lỗ hổng đo lường lớn nhất. Ba hạn chế đã biết, ghi ra để người đọc báo cáo không diễn giải quá mức: (1) judge và model dịch đều chạy ở `temperature=0.3` và mỗi mẫu chỉ chấm một lần, nên hai lần chạy cùng mã nguồn vẫn lệch nhau — vì vậy `--compare` chỉ báo "thay đổi" khi vượt ngưỡng đã công bố (0.05 với điểm trung bình, 5 điểm phần trăm với tỷ lệ đạt), còn lại ghi "trong khoảng nhiễu", và **không** tính p-value giả vờ có ý nghĩa với n=53; (2) chấm điểm thành phần và chạy lặp sẽ tốn gấp 3-5 lần hạn mức mỗi lần chạy (~318 request), vượt xa gói miễn phí — xem xét lại khi có hạn mức trả phí; (3) khi provider chấm trùng provider dịch thì model tự chấm chính nó, báo cáo in cảnh báo nhưng không chặn. Mẫu passthrough (nguồn trùng đích) bị loại khỏi mọi chỉ số chất lượng vì không model nào được gọi mà judge vẫn cho ~1.0. **Bổ sung 20/08:** golden set thêm hai category `glossary_audience` và `honorific_recipient`, nên `golden_set_sha()` đổi và `--compare` **không còn so được** với hai run đã lưu trong `eval/results/`. Đây là hệ quả đã lường trước của chính quyết định này chứ không phải sự cố: mốc so sánh gắn với bộ mẫu, và đổi bộ mẫu thì mốc cũ không còn nói lên điều gì. Cách xử lý là chạy một run nền mới ngay sau khi đổi. Judge nhận thêm hai tiêu chí — xưng hô đúng vai như bản tham chiếu, và thuật ngữ nội bộ dịch đúng theo đối tượng — vì hai category mới sẽ chấm gần như nhau nếu tiêu chí không nhắc tới chúng. Hai mẫu `glossary_audience` cố ý **giống hệt nhau trừ trường `audience`**: nếu điểm của chúng bằng nhau thì tính năng không làm gì cả, và đó là phép đo chứ không phải hai mẫu rời rạc |
| ADR-18 | Nơi chạy sản phẩm và nơi lưu tệp đính kèm | Backend (Docker) và PostgreSQL trên **Railway**, frontend trên **Vercel**; tệp đính kèm nằm trên **volume gắn vào container**, không dùng object storage | `ConnectionManager` giữ danh sách socket trong bộ nhớ tiến trình (`src/api/websocket.py`), nên hệ thống chỉ chạy đúng **một tiến trình, một bản sao** — không `--workers`, không autoscale — cho tới khi có backplane kiểu Redis (ADR-08 đã bác trong MVP). Điều đó loại các nền tảng ngủ khi không có lưu lượng: gói miễn phí của Render ngủ sau 15 phút và cắt mọi WebSocket đang mở, đồng thời không cho gắn đĩa. Railway chạy liên tục, tiêm `$PORT`, và cho gắn volume. Vì chỉ có một bản sao nên volume là đủ cho tệp đính kèm và **rẻ hơn hẳn** việc viết lại tầng lưu trữ cho S3/R2 — đổi lại, ngày nào cần nhân bản thì phải làm cả hai việc cùng lúc. Supabase dùng được không đổi mã (chỉ là một `DATABASE_URL` khác), nhưng cổng pooler 6543 cần tắt prepared statement của asyncpg, xem `docs/DEPLOY.md`. Không thêm job deploy vào GitHub Actions: cả Railway lẫn Vercel đều tự triển khai theo nhánh |
| ADR-19 | Nơi lưu bản góp ý bản dịch của người dùng | **Bảng mới `translation_edits`**, chỉ ghi thêm và **riêng tư theo người viết**; `translation_results.translated_text` không bao giờ bị ghi đè; ở chat 1-1 người gửi cũng được góp ý | Mục đích của tính năng là so người với máy, nên cả hai văn bản phải cùng tồn tại — ghi đè bản máy sẽ xoá đúng cái đang cần đo, và sau vài tuần sẽ không còn cách nào biết bản dịch nào từng bị sửa. Chọn bảng riêng chứ không thêm cột `edited_text` vào `translation_results` vì người dùng được góp ý nhiều lần: một cột chỉ giữ được bản cuối, trong khi chuỗi các lần sửa mới cho thấy người ta sửa lại chỗ nào — dữ liệu duy nhất đáng giá cho tính năng quản trị về sau. Cũng không tái dùng `feedbacks.correction`, vốn chỉ giữ được một dòng mỗi người nên lần góp ý thứ hai sẽ xoá mất lần thứ nhất. **Góp ý là riêng tư**, đúng như `feedbacks` xưa nay: người đọc không biết ngôn ngữ gốc thì bản họ gõ ra là cảm nhận về câu chữ, không phải một bản dịch đã được kiểm chứng — phát nó cho cả phòng sẽ biến phỏng đoán của một người thành nội dung chính thức của người khác. Vì thế tính năng này **không sinh sự kiện WebSocket nào**; việc cả phòng thấy nội dung mới là chuyện của F-06 sửa tin nhắn gốc (§3.6), một luồng đã có sẵn và rất dễ bị lẫn với luồng này. Quyền góp ý của người gửi giới hạn ở hội thoại `direct` vì chỉ ở đó tin nhắn có đúng một bản dịch và người gửi nhìn thấy trọn vẹn cả hai bản; đổi lại, người gửi phải nhận được sự kiện dịch của chính tin mình gửi trong `direct` — xem sửa đổi §4.4 quy tắc 3 |
| ADR-20 | Ngôn ngữ giao diện tách khỏi ngôn ngữ đọc tin nhắn | Thêm cột **`users.interface_language`**, lưu ở server theo tài khoản, độc lập với `preferred_language` | Hai lựa chọn này trả lời hai câu hỏi khác nhau — "tôi muốn đọc tin nhắn bằng gì" và "tôi muốn menu bằng gì" — và người học ngoại ngữ, đúng nhóm người dùng của sản phẩm này, thường trả lời khác nhau cho hai câu. Dùng chung một cột sẽ buộc người muốn luyện đọc tiếng Nhật phải nuốt luôn cả giao diện tiếng Nhật. Quan trọng hơn, hai trường khác nhau về hiệu lực: đổi ngôn ngữ đọc **chỉ áp dụng cho tin nhắn mới** (bản dịch cũ đã nằm trong `translation_results`, dịch lại là tốn hạn mức LLM cho thứ người dùng đã đọc rồi), còn đổi ngôn ngữ giao diện phải thấy **ngay lập tức** và không tốn gì cả. Gộp vào một cột thì một hành động sẽ mang hai ngữ nghĩa hiệu lực trái nhau. Lưu ở server chứ không phải `localStorage` để lựa chọn theo người dùng qua mọi thiết bị, và để lần render đầu tiên không loé lên tiếng Việt rồi mới đổi |
| ADR-21 | Chặn rò rỉ dữ liệu qua đầu ra của bản dịch | Ba biện pháp ở phía đầu ra, cài trong `src/agents/guardrails.py`: (1) `strip_translation_scaffolding` gỡ bỏ mọi lớp bọc model tự thêm (khối suy luận `<think>`, thẻ phân định bị lặp lại, code fence, nhãn `Translation:`, dấu ngoặc kép, dòng ghi chú cuối) **một cách tất định**; (2) `find_leaked_identifiers` từ chối bản dịch chứa email, dãy số từ 9 chữ số trở lên, hoặc token dạng khoá **mà tin nhắn gốc không có**; (3) `discloses_prompt_instructions` từ chối bản dịch đọc lại chính chỉ dẫn của agent. Vi phạm nào cũng chuyển sang tầng dự phòng theo NFR-02 | Agent cố tình cho model đọc tin nhắn của **người khác** làm ngữ cảnh (ADR-01), nên đầu ra chính là kênh mà dữ liệu đó có thể thoát ra tới một người nhận chưa từng được xem: một tin nhắn được dàn dựng để model đọc lại lịch sử, hoặc đơn giản là model trôi ý, sẽ giao số điện thoại hay email của người thứ ba. Quy tắc tỷ lệ độ dài (ADR-13) không bắt được vì một số điện thoại lọt vào bản dịch không làm nó dài thêm bao nhiêu. Chỉ so **các token có hình dạng định danh**, không bao giờ so văn phong: bản dịch nào cũng viết lại câu chữ nên mọi quy tắc về *từ ngữ* đều báo nhầm, còn một địa chỉ email chưa từng có trong tin nhắn thì không thể giải thích khác. So sánh bỏ qua định dạng (`0912 345 678` và `0912.345.678` là một) và bỏ qua dãy dưới 9 chữ số, để ngày tháng bị đảo thứ tự (`16/08/2026` → `08/16/2026`, 8 chữ số) và số phiên bản không bị tính là rò rỉ. Biện pháp (1) tồn tại vì "chỉ trả bản dịch" trong prompt là một *yêu cầu*, không phải một *bảo đảm* — nó thay đổi theo provider và theo phiên bản model, nên phần bảo đảm phải nằm trong code; mọi quy tắc gỡ bỏ đều đối chiếu với tin nhắn gốc trước (tin nhắn vốn đã nằm trong ngoặc kép thì bản dịch vẫn giữ ngoặc kép) và không bao giờ được phép làm rỗng đầu ra. Tầng dự phòng thứ hai không lặp lại (2) và (3) vì nó chỉ nhận đúng tin nhắn gốc, không có ngữ cảnh để rò và không có prompt để đọc lại. **Bổ sung 19/08, ba mục.** (4) `find_dropped_identifiers` — ảnh phản chiếu của (2): email, URL và dãy ≥ 9 chữ số **có trong tin gốc** mà biến mất khỏi bản dịch cũng chuyển sang tầng dự phòng. Một model "cẩn thận" tự ý che số điện thoại tạo ra đầu ra trôi chảy, đúng độ dài, đúng ngôn ngữ, chỉ thiếu đúng chi tiết mà người nhận cần — không lớp nào khác thấy được. So sánh bỏ qua định dạng và chấp nhận cả dạng quốc tế hoá (`0912 345 678` → `(+84) 912 345 678`), vì số 0 đầu là tiền tố nội hạt chứ không phải thông tin mất đi. (5) `classify_leak_source` — chia kết quả của (2) thành `context` (giá trị có thật trong lịch sử: rò rỉ riêng tư) và `invented` (model bịa: lỗi đúng-sai), ghi vào telemetry; hai loại này cần hai cách sửa khác nhau nên gộp chung sẽ không đo được gì. (6) `find_context_echo` — bắt **văn xuôi** chép nguyên từ một dòng ngữ cảnh (trùng ≥ 40 ký tự sau khi chuẩn hoá hoa/thường và khoảng trắng, và không có trong tin gốc), khoảng trống mà (2) không thấy vì không phải định danh còn quy tắc độ dài chỉ thấy khi model chép cả khối. **Mục (6) hiện chỉ đo, chưa chặn**: hội thoại có tính lặp lại tự nhiên — hai người bàn cùng một lần deploy viết gần như cùng một câu — nên phải có số liệu dương tính giả trên lưu lượng thật rồi mới bật chặn, đúng nguyên tắc "dương tính giả cũng là một tin nhắn không được dịch". Log chỉ ghi **độ dài** đoạn trùng và **số lượng** định danh, không bao giờ ghi giá trị: log máy chủ do người ngoài hội thoại đọc |
| ADR-22 | Hệ quản trị cho môi trường phát triển và kiểm thử | **PostgreSQL kèm extension `pgvector` ở mọi môi trường**, kể cả máy lập trình viên và bộ kiểm thử. Cung cấp bằng `docker compose up -d postgres` (image `pgvector/pgvector:pg16`), CI dùng service container cùng image. SQLite bị gỡ khỏi đường chạy; `conftest.py` cấp cho mỗi test một schema riêng rồi `DROP SCHEMA ... CASCADE` khi xong | **Sửa ADR-06**, vốn chọn SQLite async cho môi trường phát triển. Điều kiện xem xét lại đã ghi ngay trong ADR-06 — "có thể bật `pgvector` cho Glossary mà không phải thay đổi hệ quản trị" — nay đã xảy ra: glossary, `correction_log` và `message_embeddings` đều có cột `vector` và được tìm theo khoảng cách cosine (ADR-25). SQLite **không có kiểu `vector`**, nên trên SQLite schema còn không tạo nổi chứ chưa nói tới tìm kiếm. Hai lựa chọn còn lại đều bị bác: giữ SQLite cho kiểm thử và PostgreSQL cho production nghĩa là **hai đường mã truy hồi**, mà đường chạy thật lại chính là đường không có test nào chạm tới; còn đặt vector ra ngoài cơ sở dữ liệu (Chroma, đã có sẵn `chroma_persist_dir` trong `src/config.py`) tạo ra hai nguồn sự thật phải đồng bộ tay và đi ngược lý do chọn pgvector là không phải vận hành thêm service. Giá phải trả, ghi ra để không ai ngạc nhiên: mỗi người trong nhóm cần một Docker Engine (không cần Docker Desktop — bản CLI trong WSL2 là đủ), và bộ kiểm thử chậm hơn hẳn SQLite tệp cục bộ vì mỗi test phải dựng và xoá một schema. Cô lập theo schema chứ không theo cơ sở dữ liệu vì `CREATE DATABASE` tốn khoảng một giây mỗi lần, còn `CREATE SCHEMA` gần như không tốn gì. Bộ kiểm thử vẫn dùng `Base.metadata.create_all` chứ không chạy migration, đúng nguyên tắc của ADR-06: kiểm thử kiểm tra mã nguồn hiện tại, không kiểm tra lịch sử migration — nên extension `vector` phải được tạo ở cả hai nơi, trong migration cho production và trong `conftest.py` cho kiểm thử. **Lưu ý vận hành trên Windows:** khi Docker Engine chạy trong WSL2, máy ảo WSL tự tắt sau khoảng 60 giây không hoạt động và kéo PostgreSQL tắt theo, biểu hiện là `ConnectionRefusedError` giữa chừng một lần chạy test — giữ một tiến trình sống trong WSL hoặc nâng `vmIdleTimeout` trong `.wslconfig` |
| ADR-23 | Xưng hô theo vị thế người nhận | Bản dịch gom nhóm theo cặp **`(ngôn ngữ đích, vị thế)`** thay vì chỉ theo ngôn ngữ đích. Vị thế là enum thô **bốn** bậc — `senior`, `peer`, `junior`, `client` — lưu ở `participant_profiles` theo cặp `(hội thoại, người dùng)`, và cột `honorific_profile` vào thẳng ràng buộc duy nhất của `translation_results` | Tiếng Việt, tiếng Nhật và tiếng Hàn **không dựng được câu mà không chọn cách xưng hô** với người đọc. Hợp đồng cũ (§4.4 quy tắc 2) gom mọi người đọc cùng một ngôn ngữ vào một bản dịch, nên trong một nhóm có cả quản lý lẫn khách hàng thì bắt buộc có người đọc sai vai. Hai phương án ở hai đầu đều bị bác. **Dịch riêng cho từng người nhận** cho kết quả đúng nhất nhưng nhân số lượt gọi model theo số thành viên, đồng thời phá mô hình phản hồi của F-05 vốn gắn góp ý vào `translation_id` dùng chung chứ không vào người nhận. **Chỉ hai bậc nội bộ/khách hàng** thì rẻ nhất nhưng bỏ mất đúng phần khó: anh/em/chị trong cùng một nhóm nội bộ vẫn phải phân biệt. Bốn bậc là điểm giữa: một nhóm 10 người đọc 3 ngôn ngữ đi từ 3 lượt gọi lên **tối đa** 9 chứ không phải 10, và chat `direct` **không đổi gì** vì mỗi ngôn ngữ ở đó vốn chỉ có một người nhận. Thô là cố ý ở cả chiều khác: thang mịn hơn thì LLM không suy ra ổn định, mà một enum thì viết được `CheckConstraint` và viết được test. `honorific_profile` **ghi một lần, không ghi đè**, và đường đọc có thang dự phòng qua `peer`: hồ sơ vị thế thay đổi được, nên nếu tra theo hồ sơ hiện tại thì một lần suy lại sẽ làm biến mất bản dịch của cả một luồng hội thoại mà không có lỗi nào được ghi. **Số đo sau khi hiện thực fan-out:** số lượt gọi model bằng đúng số bucket khác nhau trong hội thoại, không hơn — khẳng định bằng test (`tests/test_services/test_bucket_fanout.py`): hai người cùng đọc tiếng Việt nhưng khác vị thế cho **hai** lượt gọi, còn hai người cùng đọc tiếng Việt và **cùng** vị thế chỉ tốn **một** lượt và dùng chung một `translation_id`. Nói cách khác chi phí tăng theo số *vai vế thật sự khác nhau* trong hội thoại chứ không theo số thành viên: một nhóm mà mọi người ngang hàng nhau thì không đắt thêm đồng nào so với trước. Con số token và độ trễ thật vẫn còn thiếu — chúng cần một lượt chạy với LLM thật, tốn hạn mức, và sẽ được bổ sung sau khi node `customize` khiến bốn bucket thực sự sinh ra bốn prompt khác nhau; tới lúc này bốn bucket vẫn nhận cùng một prompt nên đo cũng chỉ ra bốn lần cùng một thứ |
| ADR-24 | Xác định lĩnh vực và đối tượng của hội thoại | Một lượt LLM chạy **nền** suy ra `domain`, `audience` của hội thoại và vị thế của từng thành viên cùng lúc. Nhịp: chờ đủ **5 tin** mới chạy lần đầu, lặp lại mỗi **20 tin**, **khoá vĩnh viễn khi 3 lần liên tiếp trùng kết quả**. Agent dịch chỉ *đọc* kết quả qua node `customize`, không tự suy luận | Đây là thứ quyết định `UI` giữ nguyên hay thành "giao diện", nên nó phải **ổn định** hơn là nhanh: nếu đoán lại theo từng tin nhắn thì đối tượng nhấp nháy và người đọc thấy giọng văn đổi giữa chừng cuộc trò chuyện. Chờ 5 tin vì dưới ngưỡng đó không có đủ bằng chứng để đoán gì; khoá sau 3 lần trùng vì đến lúc đó thêm bằng chứng không còn đổi kết luận, và tiếp tục gọi model chỉ là tiêu hạn mức. Nhịp tính theo **số tin nhắn** chứ không theo đồng hồ: một hội thoại im lặng không nên tốn hạn mức để quyết lại thứ chưa ai thêm bằng chứng vào. Suy luận chạy ở tầng service chứ **không** đặt trong graph dịch: graph chạy một lần cho mỗi nhóm người nhận, nên đặt trong đó là suy luận lặp lại nhiều lần cho cùng một tin nhắn. **Sửa ADR-14**, vốn ghi hệ thống không gọi LLM ngoài luồng dịch — ranh giới cũ dựa trên lập luận "chỉ dịch, không sinh nội dung", mà lượt gọi này cũng không sinh nội dung cho người đọc: nó phân loại, đầu ra không bao giờ tới tay ai, và mọi lỗi đều suy giảm về hồ sơ mặc định `peer` với `domain`/`audience` rỗng. Hạn chế đã biết, ghi ra để không ai ngạc nhiên: chưa có giao diện cho người dùng sửa tay vị thế, nên cơ chế khoá sau 3 lần trùng sẽ **đóng đinh cả một kết luận sai** cho tới khi có ai xoá dòng trong cơ sở dữ liệu |
| ADR-25 | Nguồn sinh vector nhúng | Factory đa provider `src/services/embeddings.py` theo đúng khuôn `src/services/llm.py`, chọn bằng biến `EMBEDDING_PROVIDER` (`gemini` | `openai` | `local`). Số chiều **ghim cứng** trong `EMBEDDING_DIM` ở `src/database/models.py`, mỗi bảng lưu kèm cột `embedding_model`. Mọi lỗi suy giảm về `None` | pgvector chỉ **lưu và đo khoảng cách**; nó không sinh ra vector, nên vẫn phải chọn một mô hình. Yêu cầu quyết định là **đa ngữ xuyên ngôn ngữ**: nếu "staging env" và "môi trường stg" không nằm gần nhau thì toàn bộ việc gom nhóm theo ngữ nghĩa mất ý nghĩa. Factory thay vì chọn cứng một nhà cung cấp, vì cả ba lựa chọn đều có nhược điểm thật: Gemini rẻ và đã có sẵn khoá trong dự án nhưng phụ thuộc hạn mức, OpenAI chất lượng cao nhất nhưng cần tài khoản còn credit (đúng lý do ADR-10 đã loại nó khỏi đường chính), còn `sentence-transformers` chạy cục bộ thì không tốn hạn mức và **không gửi dữ liệu ra ngoài** nhưng kéo theo ~500MB torch vào image, một rủi ro thật với gói miễn phí một bản sao của Railway (ADR-18). Số chiều **không** đọc từ cấu hình: đọc từ đó thì hai người với hai tệp `.env` khác nhau sẽ mô tả hai schema khác nhau, và `alembic --autogenerate` sẽ đề nghị migration ở máy này mà không ở máy kia. Đổi provider vì thế là **một migration cộng một lượt nhúng lại toàn bộ**, không phải một dòng cấu hình; cột `embedding_model` tồn tại để một vector cũ nhận ra được thay vì bị âm thầm so trong sai không gian và trả về một câu trả lời sai đầy tự tin. **Bổ sung §6.4 và ADR-15:** đây là **luồng dữ liệu bên thứ tư** — mỗi tin nhắn được gửi tới nhà cung cấp nhúng. Cơ chế tắt là `EMBEDDING_PROVIDER=local` cộng hai cờ `SEMANTIC_GLOSSARY_ENABLED` và `RAG_CONTEXT_ENABLED`, cả hai **mặc định tắt** |
| ADR-26 | Cách tra thuật ngữ trong glossary | **Hai tầng**: khớp chuỗi đã chuẩn hoá theo **ranh giới từ** trước, rồi mới tới láng giềng gần nhất theo cosine, và chỉ khi bật `SEMANTIC_GLOSSARY_ENABLED` (mặc định **tắt**). Khớp chuỗi luôn thắng khớp ngữ nghĩa. Phạm vi chọn theo `(domain, audience)`, trong đó `audience` xếp trên `domain`, và chuỗi rỗng nghĩa là "áp dụng ở mọi nơi" | Tầng một trả lời được phần lớn trường hợp mà **không tốn lượt gọi nào**, tất định, và test được không cần mô hình. Tầng hai tồn tại vì người ta gõ `stg` chứ không gõ `staging environment`, tức đúng những biến thể mà khớp chuỗi không bao giờ tìm ra — nhưng nó cũng là tầng **có thể sai**, và một thuật ngữ khớp sai thì bị **ép** vào bản dịch chứ không phải chỉ bị bỏ lỡ. Vì thế ngưỡng đặt bảo thủ (`GLOSSARY_SIMILARITY_THRESHOLD`, mặc định 0.82) và khớp chuỗi thắng tuyệt đối. Khớp theo **ranh giới từ** chứ không phải chuỗi con: `UI` nằm trong `building` mà khớp thì hệ thống sẽ ép một cách dịch vào một từ chẳng liên quan gì. So sánh cosine thực hiện **trong Python** trên tập ứng viên đã chặn ở `MAX_CANDIDATES`, không phải bằng truy vấn index: index HNSW đáng giá khi quét cả bảng, còn vài trăm dòng thì không, và làm ở một chỗ giữ toàn bộ quyết định — phạm vi, độ chính xác, ngưỡng — đọc được liền mạch. `audience` xếp trên `domain` vì đó chính là trục mà tính năng sinh ra để phục vụ: khách hàng vẫn được "giao diện" bất kể lĩnh vực là gì, còn lĩnh vực một mình không đổi ai đang đọc. Cả hai cột **không cho phép `NULL`** mà dùng chuỗi rỗng, vì `NULL` không so bằng `NULL` nên bản trùng sẽ lọt qua ràng buộc duy nhất. **Sửa ADR-01**, vốn nói Vector Store chỉ cần cho Glossary ở giai đoạn Post-MVP: nay nó cần, và nó là pgvector trong chính cơ sở dữ liệu đang dùng chứ không phải một service thứ hai (ADR-22). Hai giới hạn đã biết: tầng dự phòng `deep-translator` **không nhận glossary** — nó chỉ nhận nguyên văn tin nhắn — nên một tin rơi xuống tầng đó mất tính nhất quán về thuật ngữ; và mỗi tin chỉ được mang tối đa `MAX_TERMS_PER_MESSAGE` thuật ngữ, vì một prompt chở năm mươi cách dịch bắt buộc thôi là chỉ dẫn dịch mà thành một cuốn từ điển model phải đọc trước |
| ADR-27 | Truy hồi ngữ cảnh theo ngữ nghĩa | `build_context` giữ nguyên cửa sổ 3-5 tin gần nhất và **thêm** tối đa `RAG_TOP_K` tin cũ gần nghĩa nhất với tin đang dịch, gộp thành một danh sách theo thứ tự thời gian. Vector truy vấn là embedding **đã lưu sẵn** của chính tin đó, không nhúng lại lúc dịch. Tắt mặc định qua `RAG_CONTEXT_ENABLED`, và cờ đó cũng khoá luôn đường **ghi** | Cửa sổ theo thời gian trả lời được "vừa nãy đang nói gì" — thứ giải quyết đại từ và chủ ngữ bị lược — nhưng không trả lời được "đã chốt gì về vụ migration", vì việc đó xảy ra bốn mươi tin trước. Người đọc biết "vụ migration" là gì; model, khi chỉ được cho bốn dòng cuối, thì không. Đây đúng là thứ **sửa ADR-01**, vốn nói ngữ cảnh chỉ là truy vấn tuần tự theo thời gian trên `messages` và Vector Store chỉ cần cho Glossary ở Post-MVP. Nay cần, và nó vẫn là **cùng một bảng `messages`** — `message_embeddings` chỉ là dữ liệu dẫn xuất tính lại được, không phải nguồn thứ hai để lệch với bản gốc, nên lý lẽ cốt lõi của ADR-01 (một nguồn sự thật) còn nguyên. Vector truy vấn lấy từ bảng chứ không nhúng tại chỗ vì đây là đường request và NFR-01 là con số chặt nhất dự án; đường ghi chạy nền, sau khi tin nhắn đã tới tay người nhận. **Ba ràng buộc không được nới:** (1) tin đã thu hồi bị loại ở **cả hai** đường — một lối vào thứ hai cùng bảng là một lối thứ hai để tin đã thu hồi quay lại, và là lối khó nhận ra hơn vì dòng đó trông y hệt mọi dòng khác; (2) truy hồi **giới hạn trong một hội thoại**, không phải để tối ưu mà vì với sang hội thoại khác là lấy chữ từ một luồng người đọc chưa từng tham gia rồi đặt trước mặt model — đúng cái rò rỉ mà ADR-21 canh ở đầu ra, nhưng đưa vào từ đầu vào; (3) `limit` chỉ chặn cửa sổ thời gian, không chặn tổng: mục đích của đường thứ hai là **với ra ngoài** cửa sổ đó, chặn tổng sẽ đẩy văng chính những dòng gần nhất đang giải quyết đại từ. Cái giá đã biết của việc để cờ khoá cả đường ghi: bật cờ lên là bắt đầu nhớ **từ lúc đó**, tin cũ vẫn vô hình với truy hồi cho tới khi có ai chạy backfill |
| ADR-28 | Khai thác thuật ngữ từ bản góp ý của người dùng | Bảng **`correction_log` tách riêng**, chỉ ghi khi người góp ý **đồng ý chia sẻ**; `translation_edits` không bị đọc tới. Trích cặp sửa bằng **luật** lúc lưu góp ý, gom nhóm theo **embedding** chứ không theo chữ, và chỉ đề xuất khi một cụm đạt cả `--min-count` lần sửa lẫn `--min-users` người khác nhau. Chạy ngoài đường request bằng `make glossary-mine` | ADR-19 định nghĩa `translation_edits` là **riêng tư tuyệt đối với người viết**. Khai thác thẳng bảng đó là âm thầm rút lại lời hứa ấy, nên thứ được khai thác là một bản **dẫn xuất, hẹp hơn, và có đồng ý**: máy viết gì, người viết gì thay vào, cùng vài từ xung quanh đã bỏ email, link và dãy số dài. `consent_to_share` khoá **cả dòng** chứ không riêng phần trích dẫn — đếm một bản sửa mà người ta không đồng ý chia sẻ thì vẫn là đang dùng nó. Gom nhóm theo ngữ nghĩa là điều kiện để cơ chế này hoạt động: "staging env" và "môi trường stg" là hai chuỗi cho một ý, đếm theo chuỗi thì mỗi cái một lần và không cái nào vượt ngưỡng; mà nếu cả hai cùng vượt thì glossary lại có hai mục gần trùng cho một khái niệm. Ngưỡng **số người** quan trọng hơn ngưỡng số lần: năm lần sửa của một người là sở thích cá nhân, hai lần của hai người là một quy ước đang hình thành. Trích xuất bằng luật chứ không bằng model vì nó chạy lúc lưu góp ý, nơi một lượt gọi API không có chỗ — và trích sai không tốn gì, do miner chỉ đề xuất thứ lặp lại. Đề xuất ở trạng thái `pending` **cũng chặn** đề xuất mới, không chỉ `rejected` và `active`: nếu không, chạy miner hai lần trong một tuần sẽ sinh hai đề xuất trùng nhau. Bước cuối cho phép model trả `{"skip": true}` cho phần lớn bản sửa vốn chỉ là viết lại câu — một đề xuất không hành động được còn tệ hơn không có đề xuất, vì nó dạy người duyệt ngừng đọc hàng đợi |


## 8. Triển khai

Quy trình chi tiết, biến môi trường và cách khắc phục sự cố: **`docs/DEPLOY.md`**.

| Thành phần | Nền tảng |
|---|---|
| Backend và Agent | Docker container trên Railway, **1 bản sao duy nhất** (ADR-18) |
| Frontend | Vercel (thư mục gốc `frontend/`) |
| Cơ sở dữ liệu | PostgreSQL của Railway; Supabase thay thế được mà không sửa mã |
| Tệp đính kèm | Volume gắn vào `/app/data` của container backend |
| Schema | Alembic, chạy trong `CMD` trước `uvicorn` (ADR-06) |
| CI/CD | GitHub Actions chạy lint + test; triển khai do Railway/Vercel tự làm theo nhánh |

## 9. Định hướng mở rộng

Các hạng mục Post-MVP, chưa được thiết kế chi tiết:

1. Nhận diện và chuẩn hoá tiếng Việt vùng miền, từ lóng, từ viết tắt
2. Glossary doanh nghiệp (CRUD và tìm kiếm ngữ nghĩa; yêu cầu bật `pgvector` hoặc bổ sung Vector Store)
3. Dịch tin nhắn thoại (pipeline Speech-to-Text)
4. Dashboard theo dõi chi phí token
5. Tối ưu fan-out theo nhóm ngôn ngữ (xem ADR-03)

## 10. Tài liệu liên quan

### 10.1. Tài liệu trong kho mã nguồn

| Tài liệu | Nội dung |
|---|---|
| [`docs/architecture_diagram.md`](docs/architecture_diagram.md) | Sơ đồ kiến trúc, luồng Agent, luồng dữ liệu, ER, sequence, use case |
| [`docs/CONTRACT.md`](docs/CONTRACT.md) | Đặc tả giao diện API, WebSocket, schema cơ sở dữ liệu |
| [`CONTRIBUTING.md`](CONTRIBUTING.md) | Quy định làm việc nhóm và quy trình quản lý mã nguồn |

### 10.2. Tài liệu quản trị dự án

Các tài liệu quản trị và đặc tả ban đầu được lưu trữ trên kênh nội bộ của nhóm:

| Tài liệu | Nội dung |
|---|---|
| PRD | Đặc tả yêu cầu sản phẩm, xác định phạm vi F-01 đến F-06 |
| Project Brief | Bối cảnh bài toán, phân tích cạnh tranh, khoảng trống thị trường |
| Project Charter | Mục tiêu, phạm vi, mốc dự án, rủi ro, tiêu chí thành công |
| Team Project Management | Backlog, User Story, đặc tả tính năng, theo dõi lỗi |

