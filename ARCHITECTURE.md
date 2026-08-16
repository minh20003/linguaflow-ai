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
| Chuỗi node | `detect_language` (hai tầng: langdetect rồi LLM khi mâu thuẫn, xem ADR-11) → rẽ nhánh theo `source_language == target_language` → `build_context` → `translate` → `validate_output`, song song với ghi CSDL bất đồng bộ |
| Cơ chế fallback | Khi `validate_output` thất bại hoặc LLM timeout, hệ thống trả về `original_text` và không chặn luồng chat |
| Mô hình ngôn ngữ | Lựa chọn qua biến môi trường `LLM_PROVIDER`. Mặc định Groq (`llama-3.3-70b-versatile`); hỗ trợ `deepseek`, `gemini`, `openai`. Xem ADR-10 |

Việc lựa chọn provider chính thức được quyết định trên cơ sở kết quả đánh giá Golden Set.

### 3.4. Cơ sở dữ liệu

| Hạng mục | Mô tả |
|---|---|
| Hệ quản trị | SQLite async (`sqlite+aiosqlite`) cho môi trường phát triển; PostgreSQL (`postgresql+asyncpg`) cho môi trường production. Chuyển đổi bằng biến `DATABASE_URL` |
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

**Điều kiện chuyển sang tầng 2.** Ngoài lỗi và timeout của LLM, `validate_output` còn đẩy sang tầng dự phòng khi bản dịch rỗng, dài bất thường so với bản gốc, hoặc **không đúng ngôn ngữ đích** (ADR-13). Trường hợp cuối bắt được câu từ chối của model — vốn quá ngắn để lọt quy tắc độ dài. Đầu ra của tầng 2 cũng chịu đúng kiểm tra ngôn ngữ đó trước khi được chấp nhận, vì nó không quay lại `validate_output`.

**Timeout ở mức toàn bộ lượt chạy không thuộc Agent.** Hệ thống chỉ có timeout theo từng lần gọi (`LLM_TIMEOUT_SECONDS`, `FALLBACK_TRANSLATOR_TIMEOUT_SECONDS`). Hạn thời gian cho cả lượt dịch thuộc về bên gọi — Chat Service bọc `graph.ainvoke` trong `asyncio.wait_for` — vì chỉ bên gọi mới biết người dùng còn chờ được bao lâu. Xem ADR-14.

### 5.2. Guardrail đầu vào và đầu ra

Ba lớp kiểm tra, cài đặt trong `src/agents/guardrails.py` (ADR-12, ADR-13). Tổng chi phí trên đường thành công khoảng 2ms, tức 0,2% ngân sách của NFR-01.

| Lớp | Kiểm tra | Khi vi phạm |
|---|---|---|
| Đầu vào | `original_text` tối đa 2000 ký tự | Ghi `error`, trả nguyên bản. Không cắt bớt — nửa bản dịch tệ hơn không dịch |
| Đầu vào | `target_language` phải đúng dạng ISO 639-1 hai chữ cái thường | Ghi `error`, trả nguyên bản. Giá trị này đi thẳng vào system prompt và đến từ trường hồ sơ người dùng tự sửa được |
| Prompt | Mỗi dòng ngữ cảnh bị gộp xuống dòng, escape dấu ngoặc nhọn, cắt còn 500 ký tự | Áp dụng im lặng tại `build_context_block` |
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
| ADR-12 | Xử lý nội dung không tin cậy trong prompt | Cô lập bằng thẻ phân định `<conversation_history>` và `<message>`, kèm làm sạch từng dòng ngữ cảnh (gộp xuống dòng và ký tự điều khiển thành khoảng trắng, **escape dấu ngoặc nhọn thành `&amp;lt;`/`&amp;gt;`**, giới hạn 500 ký tự mỗi dòng) và giới hạn 2000 ký tự cho tin nhắn. **Không** cố phát hiện ý đồ tấn công | `build_context_block` trước đây nối các dòng ngữ cảnh bằng ký tự xuống dòng, nên một tin nhắn chứa xuống dòng có thể giả mạo tiêu đề phần thứ hai và chiếm quyền điều khiển bản dịch. Nguy hiểm hơn dạng tự tấn công thông thường ở chỗ ngữ cảnh do **người khác** trong hội thoại viết ra, tức A có thể chiếm quyền bản dịch của B. Gộp xuống dòng một mình là chưa đủ — thẻ giả mạo vẫn nằm inline và vẫn đọc được như cấu trúc, nên phải escape dấu ngoặc nhọn; việc escape không tốn gì vì dòng ngữ cảnh chỉ được model *đọc*, không bao giờ xuất hiện trong bản dịch trả cho người nhận. Riêng phần thân tin nhắn không escape (sẽ làm hỏng bản dịch đầu ra) — rủi ro ở đây thấp hơn hẳn vì đó là tự tấn công: người gửi chỉ thao túng được bản dịch tin nhắn của chính mình, và phần này nằm cuối prompt nên không có chỉ dẫn tin cậy nào phía sau để ghi đè. Việc làm sạch loại bỏ chính khả năng giả mạo cấu trúc, nên nó là biện pháp giảm thiểu thực sự; còn một bộ phát hiện ý đồ sẽ thêm độ trễ và dương tính giả vào một pipeline mà trường hợp xấu nhất vốn đã là trả nguyên bản an toàn. `target_language` cũng được kiểm tra hình dạng ISO 639-1 trước khi nội suy vào system prompt, do giá trị này đến từ trường hồ sơ người dùng tự sửa được |
| ADR-13 | Kiểm tra tính hợp lệ của bản dịch đầu ra | Bản dịch bị từ chối khi `langdetect` nhận ra nó **vẫn đúng ngôn ngữ nguồn** trong khi đích khác nguồn. **Không** kiểm theo kiểu "có đúng ngôn ngữ đích không", **không** gọi LLM lần hai, **không** dùng danh sách cụm từ từ chối. Áp dụng cho cả `validate_output` lẫn `fallback_translate` | Bắt được ba dạng hỏng mà quy tắc tỷ lệ độ dài bỏ sót khi phản hồi ngắn: model từ chối (`"I can't help with that."` chỉ 24 ký tự, dưới ngưỡng 200 nên trước đây được giao cho người nhận với `is_valid = true`), trả lại nguyên văn chưa dịch, và trả lời tin nhắn thay vì dịch. **Phương án đầu tiên — so bản dịch với `target_language` — đã bị bác bỏ sau khi đo thực tế.** `langdetect` sai một cách tự tin trên đúng loại văn bản sản phẩm này nhắm tới: chuỗi `"Hotfix merged, CI green now"` bị nhận là tiếng Hà Lan ở mức 0.86, `"Docker Kubernetes Jenkins CI/CD pipeline"` bị nhận là tiếng Đức ở mức 0.9999. Cách đó loại bỏ chính những bản dịch đúng của tin nhắn kỹ thuật rồi trả về nguyên bản chưa dịch — ngược hẳn mục đích. Nâng ngưỡng độ dài không cứu được (ca tiếng Đức dài 40 ký tự) và đòi thêm biên tin cậy cũng không. Cách hiện tại chỉ yêu cầu bộ nhận diện **đồng ý với một giá trị đã biết** là ngôn ngữ nguồn do `detect_language` xác định; một lần nhận nhầm sang ngôn ngữ thứ ba bất kỳ không còn chứng minh điều gì và không gây hậu quả gì. Chấp nhận bỏ sót hơn là báo nhầm: bỏ sót một câu từ chối chỉ hỏng một tin nhắn, còn báo nhầm làm giảm chất lượng mọi tin nhắn kỹ thuật trong hội thoại. Chỉ chạy khi bản dịch dài từ 20 ký tự; khi thư viện lỗi hoặc không nhận diện được thì bản dịch được chấp nhận, tránh việc một lỗi phụ thuộc đẩy toàn bộ lưu lượng sang provider dự phòng |
| ADR-14 | Ranh giới an toàn AI trong phạm vi MVP | Guardrail giới hạn ở ba lớp: chặn kích thước đầu vào, cô lập văn bản không tin cậy trong prompt, và kiểm tra tính hợp lệ của đầu ra. **Không** có bộ phân loại kiểm duyệt nội dung, phát hiện độc hại hay PII; **không** giới hạn tần suất theo người dùng; **không** ngân sách token; **không** timeout ở mức agent | Hệ thống *dịch* nội dung người dùng chứ không *sinh* nội dung mới, nên bề mặt rủi ro hẹp hơn một trợ lý hội thoại: mô hình không được yêu cầu đưa ra quan điểm hay lời khuyên. Mọi đường lỗi đều đã suy giảm về việc trả nguyên bản (NFR-02), tức trường hợp xấu nhất là người nhận đọc tin chưa dịch chứ không phải nhận nội dung sai lệch. Ba hạng mục bị loại đều thuộc tầng API (`src/api/routes.py`, do nhánh khác sở hữu) hoặc thuộc Post-MVP theo phạm vi F-01..F-06. Timeout ở mức agent thuộc về bên gọi (`asyncio.wait_for` quanh `graph.ainvoke`), mà Chat Service chưa tồn tại. Sẽ xem xét lại khi hệ thống phục vụ người dùng ngoài nhóm |
| ADR-15 | Công bố luồng dữ liệu ra dịch vụ bên thứ ba | Ghi đầy đủ ba kênh chuyển dữ liệu tại §6.4, mỗi kênh kèm cơ chế tắt bằng cấu hình | Trước thay đổi này, `deep-translator` chỉ được mô tả như kỹ thuật bảo đảm sẵn sàng tại ADR-07 và §5.1; không tài liệu nào nêu rằng nó gửi toàn văn tin nhắn tới một endpoint không có hợp đồng xử lý dữ liệu. Langfuse cũng gửi toàn bộ prompt nhưng không xuất hiện ở mục bảo mật. Một luồng dữ liệu không được ghi nhận thì không thể được đánh giá rủi ro, nên việc công bố là điều kiện cần trước khi hệ thống nhận dữ liệu thật |
| ADR-16 | Nơi lưu số liệu đo của Agent | **Bảng mới `translation_attempts`**, tách khỏi `translation_results`; không dùng Prometheus/Grafana | Bốn đường ra của luồng dịch — timeout, exception, passthrough và bản dịch rỗng — **không sinh dòng nào** trong `translation_results`. Mọi tỷ lệ tính trên bảng đó vì thế đều chia cho một mẫu số đã loại sẵn phần lớn các ca hỏng: "tỷ lệ fallback" không đo được vì chính cái bị fallback lại không được ghi. Thêm cột vào `translation_results` không giải quyết được điều này *và* còn đòi `make reset-db` (ADR-06), trong khi bảng mới thì `create_all` tạo được mà không đụng dữ liệu cũ. Hai bảng cũng khác nhau về bản chất: `translation_results` là trạng thái ứng dụng, có ràng buộc duy nhất, cột nằm trong hợp đồng và được client đọc; `translation_attempts` là nhật ký chỉ ghi thêm, không ràng buộc duy nhất (chạy lại là một lượt thử mới), và cột được tự do đổi theo nhu cầu đo. Không chọn Prometheus/Grafana vì dự án chưa có scraper — một endpoint không ai đọc chỉ là hình thức, còn hai service trong compose là chi phí vận hành thật cho một dự án 6 tuần. Khoá `attempt_id` được sinh trước khi chạy graph và dùng làm cả PK lẫn thuộc tính trace, nên tra được hai chiều giữa Langfuse và cơ sở dữ liệu |
| ADR-17 | Phương pháp đánh giá chất lượng dịch | LLM-as-judge, **chấm một lần mỗi mẫu**, có cho judge xem ngữ cảnh hội thoại; không chấm điểm thành phần, không chạy lặp để đo dao động | Không có bộ tham chiếu do người chấm, và việc thuê người chấm 53 mẫu × mỗi lần đổi provider nằm ngoài khả năng của nhóm. Judge **phải** được xem `context_messages`: tiêu chí chấm vốn có mục "đại từ và chủ ngữ được khôi phục đúng theo ngữ cảnh", mà trước đây judge chưa bao giờ được cho xem ngữ cảnh nào — với một sản phẩm dịch theo ngữ cảnh thì đó là lỗ hổng đo lường lớn nhất. Ba hạn chế đã biết, ghi ra để người đọc báo cáo không diễn giải quá mức: (1) judge và model dịch đều chạy ở `temperature=0.3` và mỗi mẫu chỉ chấm một lần, nên hai lần chạy cùng mã nguồn vẫn lệch nhau — vì vậy `--compare` chỉ báo "thay đổi" khi vượt ngưỡng đã công bố (0.05 với điểm trung bình, 5 điểm phần trăm với tỷ lệ đạt), còn lại ghi "trong khoảng nhiễu", và **không** tính p-value giả vờ có ý nghĩa với n=53; (2) chấm điểm thành phần và chạy lặp sẽ tốn gấp 3-5 lần hạn mức mỗi lần chạy (~318 request), vượt xa gói miễn phí — xem xét lại khi có hạn mức trả phí; (3) khi provider chấm trùng provider dịch thì model tự chấm chính nó, báo cáo in cảnh báo nhưng không chặn. Mẫu passthrough (nguồn trùng đích) bị loại khỏi mọi chỉ số chất lượng vì không model nào được gọi mà judge vẫn cho ~1.0 |
| ADR-18 | Nơi chạy sản phẩm và nơi lưu tệp đính kèm | Backend (Docker) và PostgreSQL trên **Railway**, frontend trên **Vercel**; tệp đính kèm nằm trên **volume gắn vào container**, không dùng object storage | `ConnectionManager` giữ danh sách socket trong bộ nhớ tiến trình (`src/api/websocket.py`), nên hệ thống chỉ chạy đúng **một tiến trình, một bản sao** — không `--workers`, không autoscale — cho tới khi có backplane kiểu Redis (ADR-08 đã bác trong MVP). Điều đó loại các nền tảng ngủ khi không có lưu lượng: gói miễn phí của Render ngủ sau 15 phút và cắt mọi WebSocket đang mở, đồng thời không cho gắn đĩa. Railway chạy liên tục, tiêm `$PORT`, và cho gắn volume. Vì chỉ có một bản sao nên volume là đủ cho tệp đính kèm và **rẻ hơn hẳn** việc viết lại tầng lưu trữ cho S3/R2 — đổi lại, ngày nào cần nhân bản thì phải làm cả hai việc cùng lúc. Supabase dùng được không đổi mã (chỉ là một `DATABASE_URL` khác), nhưng cổng pooler 6543 cần tắt prepared statement của asyncpg, xem `docs/DEPLOY.md`. Không thêm job deploy vào GitHub Actions: cả Railway lẫn Vercel đều tự triển khai theo nhánh |
| ADR-19 | Nơi lưu bản góp ý bản dịch của người dùng | **Bảng mới `translation_edits`**, chỉ ghi thêm và **riêng tư theo người viết**; `translation_results.translated_text` không bao giờ bị ghi đè; ở chat 1-1 người gửi cũng được góp ý | Mục đích của tính năng là so người với máy, nên cả hai văn bản phải cùng tồn tại — ghi đè bản máy sẽ xoá đúng cái đang cần đo, và sau vài tuần sẽ không còn cách nào biết bản dịch nào từng bị sửa. Chọn bảng riêng chứ không thêm cột `edited_text` vào `translation_results` vì người dùng được góp ý nhiều lần: một cột chỉ giữ được bản cuối, trong khi chuỗi các lần sửa mới cho thấy người ta sửa lại chỗ nào — dữ liệu duy nhất đáng giá cho tính năng quản trị về sau. Cũng không tái dùng `feedbacks.correction`, vốn chỉ giữ được một dòng mỗi người nên lần góp ý thứ hai sẽ xoá mất lần thứ nhất. **Góp ý là riêng tư**, đúng như `feedbacks` xưa nay: người đọc không biết ngôn ngữ gốc thì bản họ gõ ra là cảm nhận về câu chữ, không phải một bản dịch đã được kiểm chứng — phát nó cho cả phòng sẽ biến phỏng đoán của một người thành nội dung chính thức của người khác. Vì thế tính năng này **không sinh sự kiện WebSocket nào**; việc cả phòng thấy nội dung mới là chuyện của F-06 sửa tin nhắn gốc (§3.6), một luồng đã có sẵn và rất dễ bị lẫn với luồng này. Quyền góp ý của người gửi giới hạn ở hội thoại `direct` vì chỉ ở đó tin nhắn có đúng một bản dịch và người gửi nhìn thấy trọn vẹn cả hai bản; đổi lại, người gửi phải nhận được sự kiện dịch của chính tin mình gửi trong `direct` — xem sửa đổi §4.4 quy tắc 3 |
| ADR-20 | Ngôn ngữ giao diện tách khỏi ngôn ngữ đọc tin nhắn | Thêm cột **`users.interface_language`**, lưu ở server theo tài khoản, độc lập với `preferred_language` | Hai lựa chọn này trả lời hai câu hỏi khác nhau — "tôi muốn đọc tin nhắn bằng gì" và "tôi muốn menu bằng gì" — và người học ngoại ngữ, đúng nhóm người dùng của sản phẩm này, thường trả lời khác nhau cho hai câu. Dùng chung một cột sẽ buộc người muốn luyện đọc tiếng Nhật phải nuốt luôn cả giao diện tiếng Nhật. Quan trọng hơn, hai trường khác nhau về hiệu lực: đổi ngôn ngữ đọc **chỉ áp dụng cho tin nhắn mới** (bản dịch cũ đã nằm trong `translation_results`, dịch lại là tốn hạn mức LLM cho thứ người dùng đã đọc rồi), còn đổi ngôn ngữ giao diện phải thấy **ngay lập tức** và không tốn gì cả. Gộp vào một cột thì một hành động sẽ mang hai ngữ nghĩa hiệu lực trái nhau. Lưu ở server chứ không phải `localStorage` để lựa chọn theo người dùng qua mọi thiết bị, và để lần render đầu tiên không loé lên tiếng Việt rồi mới đổi |


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

