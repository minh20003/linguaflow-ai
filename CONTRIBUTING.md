# QUY ĐỊNH LÀM VIỆC NHÓM

**Dự án:** LinguaFlow (P-217) · **Nhóm thực hiện:** 4U
**Phiên bản:** 1.0 · **Ngày cập nhật:** 10/08/2026 · **Trạng thái:** Đang áp dụng

---

## Phạm vi và hiệu lực

Tài liệu này chuẩn hoá quy định làm việc của nhóm và là **nguồn tham chiếu duy nhất** về quy trình làm việc, tiêu chuẩn chất lượng và quản lý mã nguồn trong suốt dự án.


## Mục lục

1. [Thành viên và phân vai](#1-thành-viên-và-phân-vai)
2. [Thời gian làm việc và báo cáo hàng ngày](#2-thời-gian-làm-việc-và-báo-cáo-hàng-ngày)
3. [Kênh liên lạc](#3-kênh-liên-lạc)
4. [Quản lý mã nguồn](#4-quản-lý-mã-nguồn)
5. [Quy trình giao việc](#5-quy-trình-giao-việc)
6. [Tiêu chuẩn chất lượng](#6-tiêu-chuẩn-chất-lượng)
   - 6.1. [Ngôn ngữ trong mã nguồn](#61-ngôn-ngữ-trong-mã-nguồn)
   - 6.2. [Quy ước đặt tên](#62-quy-ước-đặt-tên)
   - 6.3. [Chú thích và docstring](#63-chú-thích-và-docstring)
   - 6.4. [Kiểm tra trước khi commit](#64-kiểm-tra-trước-khi-commit)
7. [Ra quyết định và xử lý bất đồng](#7-ra-quyết-định-và-xử-lý-bất-đồng)
8. [Báo cáo và quy trình leo thang](#8-báo-cáo-và-quy-trình-leo-thang)
9. [Nguyên tắc làm việc](#9-nguyên-tắc-làm-việc)

---

## 1. Thành viên và phân vai

| Họ tên | Vai trò chính | Vai trò phụ | Cam kết |
|---|---|---|---|
| Nguyễn Thị Trà My | Team Lead / AI | Backend | 40 giờ/tuần |
| Nguyễn Văn Hưởng | AI | Knowledge Base | 40 giờ/tuần |
| Nguyễn Ngọc Thuận | Frontend | Tester | 40 giờ/tuần |
| Đinh Quang Minh | Backend | Knowledge Base | 40 giờ/tuần |

**Mentor phụ trách:** Đoàn Viết Thắng
**Kho mã nguồn:** https://github.com/AI20K-Build-Phase-Cohort-3/P-217.git

## 2. Thời gian làm việc và báo cáo hàng ngày

| Hạng mục | Quy định |
|---|---|
| Thời gian làm việc | Thứ Hai đến Thứ Bảy, tối thiểu 40 giờ/tuần |
| Khung giờ bắt buộc trực tuyến | 09:00-11:30 và 14:00-17:00 |
| Daily standup | 09:00 hàng ngày, gửi trên Discord. Nội dung: công việc đã hoàn thành, công việc trong ngày, vướng mắc |
| Mentor Meeting | Tối Thứ Tư (toàn khoá, 90 phút) và Thứ Bảy (riêng nhóm, 45 phút). Bắt buộc tham dự |
| Nghỉ phép | Thông báo Team Lead trước tối thiểu 24 giờ. Tối đa 2 ngày trong 6 tuần, không nghỉ liên tiếp gần thời điểm bàn giao. Trường hợp vắng mặt vẫn phải gửi standup |

## 3. Kênh liên lạc

| Kênh | Phạm vi sử dụng | Thời gian phản hồi |
|---|---|---|
| Discord `#team-217` | Trao đổi hàng ngày, hỏi đáp nhanh | Tối đa 2 giờ trong giờ làm việc |
| Discord `#team-217-Thảo luận` | Daily standup dạng văn bản | Gửi trước 09:30 |
| GitHub Issues / Pull Request | Thảo luận kỹ thuật, báo lỗi, đề xuất tính năng | Tối đa 1 ngày làm việc |
| Google Meet | Nội dung cần trao đổi trực tiếp | Hẹn trước; ghi lại kết luận lên Discord sau cuộc họp |
| Email | Liên hệ mentor và đối tác, nội dung chính thức | Tối đa 24 giờ |

Khi cần phản hồi từ một thành viên cụ thể, sử dụng chức năng tag trực tiếp và mô tả rõ vấn đề.

## 4. Quản lý mã nguồn

### 4.1. Nhánh

| Hạng mục | Quy định |
|---|---|
| Nhánh chính | `main` — chỉ merge mã nguồn đã qua review và kiểm thử. Không push trực tiếp |
| Nhánh tính năng | `feature/<tên-tính-năng>` |
| Nhánh sửa lỗi | `bugfix/<tên-lỗi>` |
| Nhánh sửa khẩn cấp | `hotfix/<tên-lỗi>` |

### 4.2. Commit message

Áp dụng chuẩn [Conventional Commits](https://www.conventionalcommits.org/), nội dung viết bằng tiếng Anh:

```
feat: add websocket routing for group chat
fix: correct source_language update after detection
refactor: extract llm provider factory
docs: update api contract for translation_id
test: add unit tests for translate node
chore: bump langchain-groq version
```

### 4.3. Pull Request và review

| Hạng mục | Quy định |
|---|---|
| Phạm vi áp dụng | Bắt buộc với mọi thay đổi mã nguồn |
| Nội dung mô tả | Thay đổi gì, lý do, phương pháp kiểm thử. Liên kết issue nếu có |
| Kích thước | Dưới 400 dòng thay đổi. Vượt ngưỡng phải tách nhỏ |
| Người review | Tối thiểu 1 thành viên khác |
| Thời gian review | Tối đa 4 giờ làm việc |
| Sau khi merge | Xoá nhánh đã merge |

### 4.4. Tệp không đưa vào kho mã nguồn

Không commit: `node_modules`, `.env`, API key, tệp build, tệp tạm. Các mục này phải được khai báo trong `.gitignore`.

## 5. Quy trình giao việc

1. Team Lead là người phân công công việc. Trường hợp Team Lead không sẵn sàng, thành viên được uỷ quyền thực hiện thay.
2. Mỗi đầu việc phải có một người chịu trách nhiệm chính, thời hạn cụ thể và kết quả mong đợi được mô tả rõ ràng.
3. Người nhận việc xác nhận trong vòng 2 giờ. Trường hợp chưa rõ yêu cầu, cần trao đổi lại ngay thay vì tự suy đoán.
4. Khi dự kiến không kịp thời hạn, thông báo Team Lead trước tối thiểu 4 giờ.
5. Cập nhật trạng thái công việc qua GitHub Issues và daily standup.

## 6. Tiêu chuẩn chất lượng

| Hạng mục | Tiêu chuẩn |
|---|---|
| Mã nguồn | Tên biến và tên hàm mang ngữ nghĩa rõ ràng; chú thích tại các đoạn xử lý phức tạp; không để lại mã không sử dụng |
| Kiểm thử | Mỗi tính năng chính có tối thiểu một test cho luồng thành công và một test cho luồng lỗi |
| Tài liệu | `README.md`, `ARCHITECTURE.md`, `docs/CONTRACT.md` cập nhật đồng thời với thay đổi thiết kế |
| Hiệu năng | API phản hồi dưới 1 giây; dịch thuật dưới 1 giây (NFR-01); trang chính tải dưới 3 giây. Trường hợp không đạt phải ghi nhận nguyên nhân và kế hoạch tối ưu |
| Bảo mật | Không hard-code API key và mật khẩu; sử dụng `.env`; kiểm tra hợp lệ toàn bộ dữ liệu đầu vào từ người dùng |
| Giao diện | Không có lỗi hiển thị ảnh hưởng khả năng sử dụng (vỡ bố cục, chồng lấn văn bản, thành phần không tương tác được) |

Bốn mục dưới đây cụ thể hoá dòng "Mã nguồn" trong bảng trên.

> Quy định này cụ thể hoá và thay thế mục *Naming Conventions* trong `docs/guide/code-style/python.md` (nội dung template dùng chung cho toàn khoá).

### 6.1. Ngôn ngữ trong mã nguồn

| Viết bằng tiếng Anh | Viết bằng tiếng Việt |
|---|---|
| Tên biến, hàm, lớp, module, **tên hàm test** | Tài liệu Markdown (`README.md`, `ARCHITECTURE.md`, `docs/**`) |
| Chú thích `#` và docstring | Báo cáo sinh ra tại `eval/results/report.md` |
| Thông điệp ghi log | Chuỗi hiển thị cho người dùng cuối |
| Nội dung prompt gửi cho LLM | |
| Tiêu đề commit, tên nhánh, tiêu đề Pull Request | |

Riêng các trường trong `eval/golden_set.jsonl` viết theo ngôn ngữ của tình huống đang kiểm thử.

Prompt viết bằng tiếng Anh không phải vì lý do hình thức: system prompt viết bằng một ngôn ngữ sẽ làm tăng khả năng model trả lời bằng chính ngôn ngữ đó thay vì ngôn ngữ đích được yêu cầu.

### 6.2. Quy ước đặt tên

**Python (`src/`, `tests/`, `eval/`)**

| Loại | Quy ước | Ví dụ |
|---|---|---|
| Hàm, biến, phương thức | `snake_case` | `translate_message`, `preferred_language` |
| Lớp, Pydantic model, Enum | `PascalCase` | `TranslationAgent`, `AgentState` |
| Hằng số | `SCREAMING_SNAKE_CASE` | `MAX_RETRY_COUNT`, `DEFAULT_TIMEOUT_MS` |
| Hàm hỗ trợ nội bộ module | Một dấu gạch dưới ở đầu | `_build_prompt` |
| Biến boolean | Tiền tố `is_` / `has_` / `should_` | `is_fallback`, `has_context` |
| Biến exception | Luôn đặt là `exc` | `except Exception as exc` |
| Module, tệp | `snake_case.py`, khớp lớp hoặc hàm chính bên trong | `context_provider.py` |
| Hàm nhà máy | `build_x` trả về **một giá trị**; `make_x` trả về **một callable** | `build_translation_graph`, `make_build_context` |

Không viết tắt. `docs/CONTRACT.md` §1 đã cấm các dạng như `lang`, `src_lang`; quy tắc này áp dụng cho toàn bộ mã nguồn.

**TypeScript / React (frontend)**

| Loại | Quy ước | Ví dụ |
|---|---|---|
| Biến, hàm, hook | `camelCase` | `sendMessage`, `useTranslation` |
| Component, type, interface | `PascalCase` | `ChatWindow`, `TranslationAgentState` |
| Hook | Luôn có tiền tố `use` | `useWebSocket` |
| Hằng số | `SCREAMING_SNAKE_CASE`; object cấu hình dùng `camelCase` | `MAX_MESSAGE_LENGTH`, `defaultConfig` |
| Interface props | `<TênComponent>Props` | `ChatWindowProps` |
| Tệp component | `PascalCase.tsx`, khớp tên component | `ChatWindow.tsx` |
| Tệp không phải component | `kebab-case.ts` | `use-websocket.ts` |

**Cơ sở dữ liệu (Supabase PostgreSQL)**

| Loại | Quy ước | Ví dụ |
|---|---|---|
| Bảng | Số nhiều, `snake_case` | `messages`, `translation_results` |
| Cột | `snake_case` | `preferred_language`, `is_fallback` |
| Khoá ngoại | `<bảng_số_ít>_id` | `user_id`, `message_id` |
| Cột boolean | Tiền tố `is_` / `has_` | `is_deleted` |
| Cột thời gian | Hậu tố `_at` | `created_at` |

**API và WebSocket** — phải khớp `docs/CONTRACT.md` chính xác

| Loại | Quy ước | Ví dụ |
|---|---|---|
| Đường dẫn REST | `kebab-case`, danh từ số nhiều | `/api/v1/chat-sessions` |
| Tên sự kiện WebSocket | `snake_case`, động từ đứng trước | `send_message`, `translation_result` |
| Trường trong payload JSON | `snake_case`, ánh xạ 1:1 với tên cột CSDL khi trường đó tương ứng trực tiếp một cột | `is_fallback` |

Cần tên trường / endpoint / sự kiện mới → bổ sung vào `docs/CONTRACT.md` và được nhóm duyệt trước, không tự đặt tên trong mã nguồn.

#### 6.2.1. Đặt tên hàm test

Theo mẫu `test_<đối tượng>_<điều kiện>_<kết quả mong đợi>`. Tên test phải đọc được như một câu mô tả hành vi mà không cần mở phần thân hàm.

```python
def test_route_skips_llm_when_languages_match(): ...
def test_returns_none_on_timeout(): ...
def test_secondary_provider_translates_when_llm_fails(): ...
```

Tránh những tên chỉ nêu điều kiện mà không nêu kết quả (`test_timeout`), hoặc chỉ là một danh từ (`test_translation`). Tên test không được trùng nhau kể cả khi nằm ở hai tệp khác nhau.

#### 6.2.2. Tên bị đóng băng

Ba nhóm tên sau **đứng trên** mọi quy ước ở §6.2 và không được đổi để "cho đúng chuẩn":

1. Tên do `docs/CONTRACT.md` ràng buộc: trường của `AgentState`, trường JSON, tên bảng và tên cột. Muốn đổi phải sửa `CONTRACT.md` trước và báo nhóm.
2. Chuỗi tên node LangGraph trong `src/agents/graph.py` — chúng xuất hiện trong sơ đồ tại `docs/architecture_diagram.md` §2 và trong `ARCHITECTURE.md` §5.1.
3. Biến `agent` trong `src/agents/graph.py`, do `src/api/routes.py` đang import theo tên này.

### 6.3. Chú thích và docstring

- Chú thích trả lời câu hỏi **tại sao**, không thuật lại **cái gì**. Nếu một đoạn mã cần chú thích để hiểu nó đang làm gì, hãy đặt lại tên hoặc tách hàm thay vì thêm chú thích.
- Không chú thích những dòng đã hiển nhiên (`# tăng biến đếm`).
- Không để lại mã bị comment.
- Mọi module trong `src/` có docstring ở đầu tệp.
- Mọi hàm và lớp public có docstring nêu mục đích và các tác dụng phụ không hiển nhiên.
- Dùng khối `Args:` / `Returns:` / `Raises:` theo chuẩn Google **khi** hàm có từ hai tham số trở lên, hoặc khi giá trị trả về không suy ra được từ tên hàm và annotation. Các trường hợp còn lại viết docstring dạng văn xuôi.

**Ngoại lệ có chủ đích:** hàm node LangGraph nhận đúng một tham số `state: AgentState` và trả về dict cập nhật một phần. Quy ước này đã được mô tả một lần tại docstring của `src/agents/nodes/translation.py`, nên các node dùng docstring văn xuôi, không lặp lại khối `Args:` ở từng hàm. Hàm lồng bên trong (closure) cũng vậy khi docstring của hàm bao ngoài đã giải thích đủ.

Giữ hàm nhỏ, mỗi hàm một trách nhiệm. Nếu một hàm cần chú thích nội bộ để giải thích các bước, hãy tách nó thành các hàm nhỏ hơn.

### 6.4. Kiểm tra trước khi commit

```bash
docker compose up -d postgres    # bo kiem thu chay tren PostgreSQL that
ruff check src/ tests/ eval/
pytest tests/ -q
```

Cả hai lệnh sau phải pass. Không tắt rule để lệnh pass.

**Bộ kiểm thử cần một PostgreSQL có `pgvector`** kể từ ADR-22 — không còn chạy
trên SQLite được nữa, vì schema có cột `vector`. `docker compose up -d postgres`
dựng đúng phiên bản mà CI dùng. `tests/conftest.py` tự suy ra cơ sở dữ liệu kiểm
thử bằng cách thêm hậu tố `_test` vào `DATABASE_URL`, tự tạo nó và extension
`vector` ở lần chạy đầu, rồi cấp cho mỗi test một schema riêng.

Chỉ cần Docker Engine, **không cần Docker Desktop**: trên Windows, bản CLI cài
trong WSL2 là đủ và Windows nối được qua `localhost:5432`. Máy ảo WSL tự tắt sau
khoảng 60 giây không hoạt động và kéo PostgreSQL tắt theo — nếu một lần chạy test
đang giữa chừng thì báo `ConnectionRefusedError`. Giữ một tiến trình sống trong
WSL, hoặc nâng `vmIdleTimeout` trong `.wslconfig`.

Toàn bộ 408 test mất khoảng 7 phút rưỡi trên máy phát triển, chậm hơn hẳn thời
SQLite vì mỗi test dựng và xoá một schema. Đây là cái giá đã biết của ADR-22.

**Lưu ý về giới hạn của công cụ:** không có linter nào trong dự án phát hiện được định danh hoặc chú thích viết bằng tiếng Việt. Rule `N` của `ruff` chỉ kiểm tra kiểu chữ (`snake_case`, `PascalCase`), còn `PLC2401` chỉ bắt được ký tự non-ASCII — trong khi tiếng Việt không dấu là ASCII thuần. Việc bảo đảm §6.1 và §6.2 hoàn toàn thuộc trách nhiệm người review.

## 7. Ra quyết định và xử lý bất đồng

### 7.1. Quy trình

1. Các bên trình bày quan điểm kèm căn cứ.
2. Lắng nghe và ghi nhận quan điểm đối lập.
3. Xác định điểm thống nhất.
4. Trường hợp không đạt được đồng thuận, Team Lead ra quyết định cuối cùng.

### 7.2. Thẩm quyền quyết định

| Loại vấn đề | Người quyết định |
|---|---|
| Kỹ thuật | Thành viên có chuyên môn phù hợp nhất với vấn đề |
| Tiến độ và phạm vi | Team Lead |
| Ảnh hưởng toàn nhóm | Biểu quyết toàn nhóm; Team Lead quyết định khi kết quả cân bằng |

Sau khi quyết định được ban hành, toàn nhóm thực hiện thống nhất. Bất đồng kéo dài quá 2 ngày không giải quyết được phải báo cáo mentor.

## 8. Báo cáo và quy trình leo thang

| Tình huống | Hành động |
|---|---|
| Vướng mắc kỹ thuật | Đăng lên Discord `#team-217`. Mentor phản hồi trong 24 giờ |
| Vướng mắc với đối tác | Báo cáo mentor ngay, không tự xử lý |
| Báo cáo tuần | Tổng hợp trước Mentor Meeting Thứ Tư theo mẫu sheet *Báo Cáo Tuần*. Nội dung bắt buộc: tiến độ, chỉ số, vướng mắc, kế hoạch tuần sau, tối thiểu một ảnh chụp minh chứng |
| Thành viên không hoàn thành trách nhiệm | Cảnh báo lần thứ nhất; tiếp diễn thì tổ chức họp với mentor |

## 9. Nguyên tắc làm việc

| Nguyên tắc | Nội dung |
|---|---|
| Trách nhiệm cá nhân | Mỗi thành viên chịu trách nhiệm hoàn thành phần việc được giao |
| Báo cáo trung thực | Báo cáo đúng thực trạng, kể cả khi kết quả chưa đạt yêu cầu. Việc che giấu vấn đề gây hậu quả lớn hơn bản thân vấn đề |
| Ưu tiên sản phẩm vận hành được | Sản phẩm hoạt động được với người dùng thật có mức ưu tiên cao hơn mã nguồn hoàn thiện nhưng chưa kịp bàn giao |
| Khắc phục nhanh | Sai sót được ghi nhận và khắc phục sớm; không quy trách nhiệm cá nhân |
| Tôn trọng thời gian | Tham dự đúng giờ các cuộc họp đã thống nhất |
