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

Định nghĩa chi tiết từng tính năng: xem PRD (`docs/T217/Gate 1/2. PRD.docx`, lưu ngoài kho mã nguồn — xem mục 10).

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
| State | `source_language`, `target_language`, `original_text`, `context_messages`, `translated_text`, `translation_id`, `is_valid`, `is_fallback`, `model`, `latency_ms`, `error`. Định nghĩa bắt buộc tại [`docs/CONTRACT.md`](docs/CONTRACT.md) §2 |
| Chuỗi node | `detect_language` → `check_same_language` (rẽ nhánh) → `build_context` → `translate` (gọi LLM, streaming) → `validate_output` → `deliver`, song song với `persist_async` (ghi CSDL bất đồng bộ) |
| Cơ chế fallback | Khi `validate_output` thất bại hoặc LLM timeout, hệ thống trả về `original_text` và không chặn luồng chat |
| Mô hình ngôn ngữ | Lựa chọn qua biến môi trường `LLM_PROVIDER`. Mặc định Groq (`llama-3.3-70b-versatile`); hỗ trợ `deepseek`, `gemini`, `openai`. Xem ADR-10 |

Việc lựa chọn provider chính thức được quyết định trên cơ sở kết quả đánh giá Golden Set.

### 3.4. Cơ sở dữ liệu

| Hạng mục | Mô tả |
|---|---|
| Hệ quản trị | SQLite async (`sqlite+aiosqlite`) cho môi trường phát triển; PostgreSQL (`postgresql+asyncpg`) cho môi trường production. Chuyển đổi bằng biến `DATABASE_URL` |
| ORM | SQLAlchemy 2.0 async (`src/database/`) |
| Vai trò | Vừa lưu trữ lịch sử hội thoại dài hạn, vừa là nguồn cung cấp ngữ cảnh cho Agent (xem ADR-01) |
| Bảng dữ liệu | `users`, `conversations`, `conversation_members`, `messages`, `translation_results`, `feedbacks` |
| Vector Store | Không sử dụng trong phạm vi MVP (xem ADR-01) |

Tại thời điểm cập nhật tài liệu, chỉ bảng `users` đã được hiện thực hoá. Schema chi tiết: xem [ER Diagram](docs/architecture_diagram.md#4-er-diagram).

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
| NFR-02 | Khả năng chịu lỗi | Lỗi hoặc timeout của LLM không làm mất tin nhắn | Luồng gửi tin gốc độc lập với luồng dịch (bước 2 và bước 5-7 không phụ thuộc nhau) |
| NFR-03 | Khả năng giám sát | Ghi nhận độ trễ và mô hình sử dụng cho mọi bản dịch | Lưu `latency_ms` và `model` trong `translation_results`; tích hợp Langfuse từ Sprint 1 |

## 6. Bảo mật và chính sách lưu trữ dữ liệu

> **Đính chính thuật ngữ:** Tài liệu giai đoạn trước sử dụng thuật ngữ "E2E" (End-to-End Encryption) cho tính năng F-06. Thuật ngữ này không chính xác về mặt kỹ thuật: Agent bắt buộc phải đọc nội dung dạng plaintext để gọi LLM, do đó hệ thống không thể đáp ứng định nghĩa mã hoá đầu-cuối. Tài liệu này thay bằng mô tả đúng bản chất là chính sách lưu trữ và kiểm soát truy cập.

### 6.1. Phạm vi lưu trữ

- Toàn bộ nội dung hội thoại (bản gốc và bản dịch) được lưu dài hạn trong `messages` và `translation_results`. Đây là hành vi tiêu chuẩn của ứng dụng chat nhằm phục vụ nhu cầu tra cứu lịch sử của người dùng.
- Ngữ cảnh cung cấp cho LLM không phải là kho lưu trữ độc lập mà là kết quả truy vấn 3-5 bản ghi gần nhất từ bảng `messages`. Do không tồn tại bản sao độc lập, hệ thống không cần cơ chế xoá ngữ cảnh khi kết thúc phiên.

### 6.2. Kiểm soát truy cập

- Mã hoá at-rest được áp dụng ở môi trường production (Supabase bật mặc định). Môi trường phát triển sử dụng SQLite không có mã hoá, do đó không được đưa dữ liệu thật vào môi trường này.
- API key và secret được cấu hình qua tệp `.env`, không hard-code trong mã nguồn.
- Kiểm tra quyền truy cập theo `conversation_id` và `user_id` được thực hiện tại tầng Chat Service.

### 6.3. Xoá dữ liệu theo yêu cầu

Tính năng xoá hội thoại theo yêu cầu người dùng (right-to-be-forgotten) không thuộc phạm vi MVP. Schema hiện tại với khoá ngoại xác định rõ ràng cho phép hiện thực hoá tính năng này theo `conversation_id` khi cần.

## 7. Quyết định kiến trúc (ADR)

| Mã | Nội dung quyết định | Lựa chọn | Căn cứ |
|---|---|---|---|
| ADR-01 | Nguồn ngữ cảnh cho LLM | Truy vấn trực tiếp bảng `messages`; không sử dụng Vector Store trong MVP | Yêu cầu "3-5 tin gần nhất" là truy vấn tuần tự theo thời gian, không cần tìm kiếm theo độ tương đồng ngữ nghĩa. Vector Store chỉ cần thiết cho Glossary ở giai đoạn Post-MVP. Việc duy trì một nguồn dữ liệu duy nhất loại bỏ rủi ro sai lệch giữa hai hệ thống và giảm số thành phần phải vận hành |
| ADR-02 | Giao thức real-time | WebSocket | Yêu cầu truyền hai chiều liên tục. SSE chỉ hỗ trợ chiều server đến client, không phù hợp với luồng chat |
| ADR-03 | Tối ưu fan-out theo nhóm ngôn ngữ | Không thực hiện trong Sprint 1 | Đây là cải tiến hiệu năng, không phải yêu cầu chức năng. Việc tối ưu được thực hiện sau khi có số liệu đo thực tế, tránh thiết kế vượt nhu cầu khi luồng end-to-end chưa hoàn chỉnh |
| ADR-04 | Framework Backend | FastAPI | Hỗ trợ async nguyên bản, phù hợp với tác vụ I/O-bound (chờ phản hồi LLM); tự động sinh tài liệu API |
| ADR-05 | Điều phối Agent | LangGraph | Luồng xử lý yêu cầu rẽ nhánh điều kiện và đường fallback. Chain tuyến tính không đáp ứng được |
| ADR-06 | Cơ sở dữ liệu | SQLite async (dev) và PostgreSQL (prod), ORM SQLAlchemy 2.0 async | Môi trường phát triển không yêu cầu cài đặt PostgreSQL cục bộ, chỉ thay đổi `DATABASE_URL` khi triển khai. PostgreSQL hỗ trợ kiểu JSON và có thể bật `pgvector` cho Glossary mà không phải thay đổi hệ quản trị |
| ADR-07 | Provider dịch dự phòng | Không tích hợp NLLB hoặc Google Translate trong MVP | Cơ chế fallback trả về bản gốc khi LLM lỗi đã đáp ứng NFR-02. Việc bổ sung provider thứ hai làm tăng số tích hợp và số API key phải quản lý khi chưa có số liệu chứng minh nhu cầu. Sẽ xem xét lại nếu kết quả benchmark Golden Set không đạt yêu cầu |
| ADR-08 | Lớp cache (Redis) | Không sử dụng trong MVP | Truy vấn 3-5 bản ghi gần nhất đáp ứng yêu cầu hiệu năng ở quy mô MVP. Việc bổ sung Redis làm tăng số thành phần phải vận hành khi chưa có số liệu chứng minh nhu cầu. Sẽ xem xét lại nếu đo được độ trễ truy vấn CSDL là điểm nghẽn |
| ADR-09 | Ngôn ngữ Backend | Python/FastAPI thống nhất toàn hệ thống | LangGraph và các SDK của LLM đều là Python. Sử dụng thống nhất một ngôn ngữ với Agent giúp giảm số runtime phải vận hành, phù hợp với quy mô nhóm hiện tại. Quyết định này thay thế phương án "FastAPI hoặc Node" trong tài liệu giai đoạn trước |
| ADR-10 | Provider LLM | Factory đa provider điều khiển qua `LLM_PROVIDER`; mặc định Groq | Giới hạn tần suất của các gói miễn phí khác biệt đáng kể (Groq khoảng 30 request/phút, Gemini khoảng 10 request/phút, Mistral 1 request/giây). Cơ chế factory cho phép chuyển provider khi bị giới hạn tần suất mà không phải sửa mã nguồn. Groq được chọn làm mặc định do tốc độ inference cao nhất, phù hợp yêu cầu real-time. DeepSeek tuân thủ chuẩn OpenAI-compatible nên tái sử dụng `langchain-openai` thông qua tham số `base_url`, không cần bổ sung SDK |

## 8. Triển khai

| Thành phần | Nền tảng |
|---|---|
| Backend và Agent | Docker container, triển khai trên Render hoặc Railway (gói miễn phí) |
| Frontend | Vercel |
| Cơ sở dữ liệu | Supabase (PostgreSQL managed) |
| CI/CD | GitHub Actions |

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

### 10.2. Tài liệu quản trị dự án (lưu ngoài kho mã nguồn)

Thư mục `docs/T217/` không được đưa vào kho mã nguồn (khai báo trong `.gitignore`). Các tài liệu dưới đây được lưu trữ và chia sẻ qua kênh nội bộ của nhóm.

| Tài liệu | Đường dẫn | Nội dung |
|---|---|---|
| PRD | `docs/T217/Gate 1/2. PRD.docx` | Đặc tả yêu cầu sản phẩm, xác định phạm vi F-01 đến F-06 |
| Brief | `docs/T217/Gate 1/1. Brief.docx` | Bối cảnh bài toán, phân tích cạnh tranh, khoảng trống thị trường |
| Project Charter | `docs/T217/1. T217 - Project Chart + Report.xlsx` | Mục tiêu, phạm vi, mốc dự án, rủi ro, tiêu chí thành công |
| Quản lý dự án | `docs/T217/2. T217 - Team Project Management.xlsx` | Backlog, User Story, đặc tả tính năng, theo dõi lỗi |
| Sơ đồ Gate 2 | `docs/T217/Gate 2/ArchitectureDesign.drawio` | Bản thiết kế giai đoạn Gate 2 (đã thay thế bằng `docs/architecture_diagram.md`) |
