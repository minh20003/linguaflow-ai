# NHẬT KÝ PHÁT TRIỂN THEO TUẦN

**Dự án:** LinguaFlow — AI Agent dịch tin nhắn đa ngôn ngữ real-time trong hội thoại
**Mã dự án:** P-217 · **Nhóm thực hiện:** 4U
**Team Lead:** Nguyễn Thị Trà My · **Mentor phụ trách:** Đoàn Viết Thắng

Tài liệu ghi nhận theo tuần: mục tiêu, kết quả đạt được, vướng mắc và biện pháp xử lý, bài học rút ra, kế hoạch tiếp theo.

---

## Tuần 1: 25/07/2026 - 02/08/2026 — Khởi động và lập Project Charter

### 1.1. Mục tiêu

- [x] Xác định đề tài, hoàn thành Brief, PRD và Market Research (Gate 1)
- [x] Lập Project Charter và Quy định làm việc nội bộ
- [x] Khởi tạo kho mã nguồn và cấu hình AI Usage Logging
- [x] Tổ chức buổi làm việc đầu tiên với đối tác (mốc M2)

### 1.2. Kết quả đạt được

| Hạng mục | Nội dung |
|---|---|
| Tài liệu Gate 1 | Brief (phân tích 4 sản phẩm cạnh tranh theo 12 tiêu chí, xác định 6 khoảng trống thị trường), PRD (xác định phạm vi MVP F-01 đến F-06), Market Research |
| Tài liệu quản trị | Project Charter (mục tiêu, phạm vi, rủi ro, tiêu chí thành công), Quy định làm việc nội bộ, phân vai 4 thành viên |
| Hạ tầng kỹ thuật | Khởi tạo dự án từ template AI20K (26/07, Trà My); cấu hình AI logging hooks cho Claude Code, Cursor, Codex, Gemini (28/07 Thuận; 30/07 Minh) |
| Mốc dự án | M1 (Project Charter) và M2 (làm việc với đối tác) hoàn thành |

### 1.3. Vướng mắc và biện pháp xử lý

| Vướng mắc | Biện pháp | Kết quả |
|---|---|---|
| AI logging hooks không hoạt động trên hệ điều hành Windows | Hiệu chỉnh `scripts/_pyrun.sh` và thiết lập quyền thực thi | Hooks hoạt động trên cả Windows và macOS/Linux (30/07, 02/08) |
| Phạm vi đề tài ban đầu bao gồm cả tiếng vùng miền, từ lóng và xử lý giọng nói, vượt khả năng triển khai trong 6 tuần | Phân chia thành hai giai đoạn trong Brief: MVP xử lý văn bản kèm ngữ cảnh, các nội dung còn lại chuyển sang Post-MVP | PRD xác định được 6 tính năng F-01 đến F-06 |

### 1.4. Bài học rút ra

1. Phương pháp nghiên cứu thị trường bằng bảng so sánh theo tiêu chí định lượng cho kết quả rõ ràng hơn mô tả định tính, đồng thời tạo cơ sở để bảo vệ giá trị khác biệt của sản phẩm ở giai đoạn thiết kế.
2. Cấu hình môi trường phát triển (hooks, script shell) cần được kiểm thử trên toàn bộ hệ điều hành mà nhóm sử dụng ngay từ đầu. Nhóm sử dụng đồng thời Windows và Unix nên lỗi tương thích ảnh hưởng đến tiến độ chung.

### 1.5. Kế hoạch tuần tiếp theo

- [x] Hoàn thành bộ sơ đồ thiết kế hệ thống (Gate 2)
- [x] Phân rã tính năng MVP thành đầu việc và phân công cụ thể
- [x] Bắt đầu hiện thực hoá các thành phần không phụ thuộc thiết kế cuối cùng

---

## Tuần 2: 03/08/2026 - 09/08/2026 — Thiết kế hệ thống và khởi động lập trình

### 2.1. Mục tiêu

- [x] Hoàn thành 6 sơ đồ thiết kế (Gate 2) và tổ chức review chéo
- [x] Phân rã F-01 đến F-06 thành đầu việc, phân công người phụ trách
- [x] Hoàn thành tính năng backend đầu tiên (F-01.2)
- [x] Cấu hình CI/CD

### 2.2. Kết quả đạt được

| Hạng mục | Nội dung |
|---|---|
| Sơ đồ thiết kế Gate 2 | System Design, Sequence Diagram, Use Case Diagram, Agent Flow, Data Flow, ER Diagram. Toàn bộ đã qua review chéo giữa 4 thành viên |
| F-01.2 — Backend Auth API | Hoàn thành 09/08 (Minh): SQLAlchemy async với SQLite, xác thực bcrypt và JWT, 3 endpoint (`POST /auth/login`, `GET /auth/me`, `PUT /auth/me/language`), script khởi tạo dữ liệu người dùng, 16 test case |
| CI/CD | GitHub Actions vận hành (04/08, Trà My) |
| Phân công công việc | Phân rã F-01 đến F-06 thành 14 đầu việc, mỗi đầu việc có người phụ trách xác định |

### 2.3. Vướng mắc và biện pháp xử lý

| Vướng mắc | Biện pháp | Kết quả |
|---|---|---|
| Use Case Diagram chứa các use case mang tính kỹ thuật (UC-06.1, UC-06.2), không phù hợp góc nhìn người dùng | Review chéo: loại bỏ các use case kỹ thuật, tách riêng actor Người gửi và Người nhận, hiệu chỉnh quan hệ `<<include>>` | Sơ đồ phản ánh đúng góc nhìn nghiệp vụ |
| Agent Flow mô tả bao trùm cả Client, Backend và tầng bảo mật, thực chất là sơ đồ End-to-End Flow | Ghi nhận trong biên bản review, xác định lại phạm vi sơ đồ | Xử lý dứt điểm ở Tuần 3 |
| Kích thước ngữ cảnh không thống nhất giữa các tài liệu (3-5 tin so với 10 tin) | Ghi nhận trong review Sequence Diagram, thống nhất áp dụng 3-5 tin | Áp dụng đầy đủ ở Tuần 3 |

### 2.4. Bài học rút ra

1. Review chéo sơ đồ thiết kế mang lại hiệu quả thực tế: phần lớn sai sót được phát hiện bởi thành viên khác chứ không phải người trực tiếp xây dựng sơ đồ.
2. Việc ghi nhận ý kiến review là chưa đủ. Ý kiến phải được áp dụng trở lại vào tệp gốc. Một số ý kiến trong tuần này được ghi nhận nhưng tệp `.drawio` chưa cập nhật tương ứng, dẫn tới sai lệch phát hiện ở Tuần 3.
3. Xây dựng test đồng thời với tính năng (16 test cho phân hệ xác thực) tạo cơ sở tin cậy khi merge, giảm nhu cầu kiểm tra thủ công.

### 2.5. Kế hoạch tuần tiếp theo

- [x] Rà soát toàn bộ thiết kế trước khi hiện thực hoá luồng dịch
- [ ] Hoàn thiện luồng dịch end-to-end (WebSocket và LangGraph Agent)
- [ ] Demo 1 với đối tác (mốc M4)

---

## Tuần 3: 10/08/2026 - 16/08/2026 — Chuẩn hoá thiết kế và Demo 1

> Tuần đang thực hiện. Số liệu cập nhật đến ngày 10/08/2026.

### 3.1. Mục tiêu

- [x] Rà soát chéo toàn bộ thiết kế, xử lý các điểm không nhất quán giữa các tài liệu
- [x] Chuẩn hoá tài liệu kỹ thuật thành nguồn tham chiếu duy nhất phục vụ phát triển song song
- [ ] Hoàn thiện luồng dịch end-to-end (F-02 và F-03)
- [ ] Demo 1 với đối tác (mốc M4)

### 3.2. Kết quả đạt được (đến 10/08)

| Hạng mục | Nội dung |
|---|---|
| Tài liệu kỹ thuật | `ARCHITECTURE.md` (kiến trúc thành phần và 10 quyết định kiến trúc ADR-01 đến ADR-10); `docs/architecture_diagram.md` (6 sơ đồ Mermaid, quản lý phiên bản qua Git); `docs/CONTRACT.md` (đặc tả API, WebSocket, cơ sở dữ liệu); `CONTRIBUTING.md` (quy định làm việc nhóm) |
| Xử lý lỗi thiết kế | Phát hiện và khắc phục 4 lỗi thiết kế cản trở việc hiện thực hoá (chi tiết mục 3.3) |
| Đồng bộ tài liệu với mã nguồn | Hiệu chỉnh đặc tả giao diện cho khớp với mã nguồn phân hệ xác thực đã hoàn thành |
| Lớp LLM đa provider | `src/services/llm.py` hỗ trợ lựa chọn provider qua biến `LLM_PROVIDER` (Groq mặc định, DeepSeek, Gemini, OpenAI). Đã kiểm chứng cả 4 provider khởi tạo đúng |

### 3.3. Vướng mắc và biện pháp xử lý

| Vướng mắc | Biện pháp | Kết quả |
|---|---|---|
| Tài liệu thiết kế được xây dựng độc lập với mã nguồn phân hệ xác thực đang chờ review, dẫn tới đặc tả mâu thuẫn với mã nguồn (sai cấu trúc response đăng nhập, sai đường dẫn endpoint, sai tên bảng và khoá chính) | Đọc mã nguồn trên nhánh `feature/f-01-2-auth-user-config`, hiệu chỉnh tài liệu theo mã nguồn hiện có | Đặc tả khớp hoàn toàn với mã nguồn đã kiểm thử; không phải viết lại mã nguồn |
| Sơ đồ Gate 2 (`.drawio`) chứa hai điểm không nhất quán: kích thước ngữ cảnh ghi 10 tin trong khi PRD quy định 3-5 tin; có bước áp dụng Glossary thuộc Post-MVP | Chuyển toàn bộ sơ đồ sang định dạng Mermaid trong kho mã nguồn, hiệu chỉnh theo PRD, xác định tệp `.drawio` không còn là nguồn tham chiếu | Sơ đồ và tài liệu thống nhất, có khả năng so sánh phiên bản qua Git |
| Ý kiến review Use Case Diagram từ Tuần 2 chưa được áp dụng vào tệp gốc | Xây dựng lại Use Case Diagram bằng Mermaid theo đúng ý kiến đã thống nhất | Hai actor Người gửi và Người nhận được tách riêng đúng yêu cầu |
| Bốn lỗi thiết kế cản trở hiện thực hoá: (1) `translation_id` không được truyền tới client khiến F-05 không khả thi; (2) `source_language` được ghi và phát trước khi detect mà chưa có quy tắc giá trị tạm; (3) `preferred_language` mang hai ngữ nghĩa chồng lấn; (4) chat nhóm chưa xác định hành vi với N thành viên và M ngôn ngữ | Bổ sung `translation_id` vào payload sự kiện; quy định quy tắc giá trị tạm và ghi đè sau detect; xác định `preferred_language` là ngôn ngữ đọc; quy định dịch một lần cho mỗi ngôn ngữ đích | Cả 4 lỗi được xử lý và ghi nhận trong `docs/CONTRACT.md` |

### 3.4. Bài học rút ra

1. Tài liệu thiết kế phải được xây dựng trên cơ sở khảo sát mã nguồn hiện có. Việc xây dựng thiết kế song song với hoạt động lập trình mà không đối chiếu dẫn tới hai nguồn tham chiếu mâu thuẫn, chi phí đồng bộ lại cao hơn chi phí khảo sát ban đầu.
2. Sơ đồ thiết kế nên được lưu trong kho mã nguồn dưới dạng văn bản (Mermaid) thay vì tệp nhị phân. Tệp `.drawio` không hỗ trợ so sánh phiên bản và review qua Pull Request, dẫn tới ý kiến review dễ bị bỏ sót và các điểm không nhất quán tồn tại không được phát hiện.
3. Đặc tả giao diện dùng chung (tên trường, endpoint, sự kiện) phải được thống nhất trước khi các thành viên phát triển song song, nhằm tránh phát sinh nhiều quy ước đặt tên khác nhau.
4. Lựa chọn kiến trúc một nguồn dữ liệu duy nhất (truy vấn ngữ cảnh trực tiếp từ bảng `messages`) thay vì bổ sung Vector Store riêng giúp giảm số thành phần phải vận hành trong phạm vi 6 tuần.

### 3.5. Kế hoạch tuần tiếp theo

- [ ] Hoàn thiện F-02 (WebSocket routing) và F-03 (LangGraph Agent dịch theo ngữ cảnh)
- [ ] Xử lý ý kiến phản hồi sau Demo 1 (mốc M5)
- [ ] Triển khai F-05: thiết kế schema và API tiếp nhận phản hồi

---

## Tuần 4: 17/08/2026 - 23/08/2026 — Hoàn thiện nền tảng hội thoại, xác thực và agent

### 4.1. Mục tiêu

- [x] Hoàn thiện giao diện chat đa ngôn ngữ, đăng nhập và các thao tác hội thoại cốt lõi
- [x] Hoàn thiện lớp dịch theo người đọc, glossary và đánh giá agent
- [x] Bổ sung quản trị nhóm, tệp đính kèm, Google authentication và ổn định tích hợp nhánh

### 4.2. Kết quả đạt được

| Hạng mục | Nội dung |
|---|---|
| Chat và giao diện | Hoàn thiện bản địa hoá UI, chuyển tiếp tin nhắn, proxy API/WebSocket, cấu trúc component chat/auth dùng chung và các điều khiển tài khoản. |
| Dịch và agent | Bổ sung dịch theo ngôn ngữ/vị thế người đọc, glossary có review queue, truy hồi ngữ cảnh, guardrail riêng tư, đánh giá retrieval/generation và tracing. |
| Xác thực và nhóm | Hoàn thiện email OTP, Google authentication, Google Sign-In UI, quản trị nhóm, session handling và các migration liên quan. |
| Calendar và tệp đính kèm | Tích hợp Supabase Storage có kiểm tra quyền; bổ sung lịch cá nhân, đề xuất được duyệt, reminder queue, REST calendar và luồng Google Calendar. |
| Chất lượng và triển khai | Cải thiện khởi động production, cấu hình môi trường, test reconnect WebSocket, CI runner và tài liệu triển khai. |

### 4.3. Vướng mắc và biện pháp xử lý

| Vướng mắc | Biện pháp | Kết quả |
|---|---|---|
| Nhiều feature branch cùng thay đổi frontend/chat và xác thực | Tách component theo feature, đồng bộ nhánh tích hợp và dùng migration/API contract làm mốc chung | Các luồng chat, auth và group có thể được merge mà không thay đổi ngầm hợp đồng dữ liệu |
| Dịch theo ngữ cảnh dễ lộ thông tin hoặc áp nhầm bản dịch giữa người đọc | Gắn dữ liệu dịch với người đọc/vị thế, bổ sung guardrail, consent và kiểm thử đánh giá | Bản dịch hiển thị theo đúng phạm vi nhận; các trường hợp từ chối được ghi nhận rõ |
| Storage ngoài database có nguy cơ làm lỏng quyền truy cập | Đặt kiểm tra xác thực và membership ở endpoint thay vì dựa vào URL file | File đính kèm giữ quyền truy cập theo hội thoại |

### 4.4. Bài học rút ra

1. Khi phát triển song song nhiều tính năng, migration, API contract và type frontend phải được xem như một đơn vị tích hợp.
2. Tính năng AI cần được kiểm thử cả đúng ngữ cảnh và đúng quyền truy cập; độ chính xác đơn thuần không đủ.
3. Cấu hình triển khai phải được kiểm chứng cùng với luồng người dùng, nhất là các provider xác thực và storage bên ngoài.

### 4.5. Kế hoạch tuần tiếp theo

- [x] Hoàn thiện admin realtime, telemetry và glossary workflow
- [x] Mở rộng assistant, calendar/task inbox, voice và Google Calendar sync
- [x] Tăng độ tin cậy CI/CD và chuẩn bị demo

---

## Tuần 5: 24/08/2026 - 30/08/2026 — Tích hợp sản phẩm, vận hành và demo readiness

### 5.1. Mục tiêu

- [x] Hoàn thiện các khoảng trống backend/frontend và dữ liệu quản trị
- [x] Tích hợp calendar, task inbox, assistant consent/privacy và voice message
- [x] Củng cố CI/CD, phát hành production và kiểm thử assistant

### 5.2. Kết quả đạt được

| Hạng mục | Nội dung |
|---|---|
| Admin và telemetry | Hoàn thiện feedback, glossary persistence, live translation, số liệu quản trị, chi phí theo model và dashboard admin. |
| Assistant | Bổ sung consent theo scope, đề xuất có human gate, private assistant reply, retrieval/chunking/tools/evaluation, xử lý proposal thiếu thông tin và hành vi theo thời gian. |
| Calendar và nhắc hẹn | Hoàn thiện REST calendar/reminder, đồng bộ hai chiều Google Calendar, bảo vệ token lưu trữ, personal calendar, task inbox và hành vi duyệt đề xuất. |
| Voice và chat | Bổ sung Gemini STT, retry transcription, message voice, attachment access và các sửa lỗi UI/chat liên quan proposal. |
| DevOps và kiểm thử | Hoàn thiện production workflow, self-hosted runner, test isolation, release transport, production readiness và kiểm thử assistant/retrieval. |

### 5.3. Vướng mắc và biện pháp xử lý

| Vướng mắc | Biện pháp | Kết quả |
|---|---|---|
| Tích hợp assistant, calendar và UI trên nhiều nhánh dễ tạo xung đột hành vi | Giữ proposal là đối tượng có trạng thái rõ ràng, cập nhật contract và bổ sung kiểm thử theo từng điểm duyệt | Đề xuất, lịch và Task Inbox cùng dùng được nhưng không bỏ qua bước xác nhận của người dùng |
| Provider AI/STT và local reranker có thể làm dịch vụ chậm hoặc dừng | Sửa retry, timeout, startup và fallback; cô lập kiểm thử agent | Luồng assistant/voice bền hơn khi provider hoặc local model lỗi |
| Chuỗi phát hành có nhiều môi trường và runner | Chuẩn hoá CI/CD, rehearsal channel, kiểm tra runner và tài liệu deployment | Có đường phát hành `develop_v2` rõ ràng hơn và kiểm chứng được trước production |

### 5.4. Bài học rút ra

1. Tính năng assistant cần có điểm duyệt nghiệp vụ rõ ràng; không nên để model thực thi lịch hay công việc trực tiếp.
2. Reliability cho AI không chỉ là retry: cần kiểm soát timeout, fallback, trạng thái xử lý và khả năng khởi động lại.
3. CI/CD hiệu quả khi test được cô lập và môi trường phát hành có bước rehearsal, thay vì chỉ dựa vào một lần deploy thành công.

### 5.5. Kế hoạch tuần tiếp theo

- [x] Hoàn thiện tài liệu vận hành, demo script và presentation
- [x] Rà soát biểu đạt thời gian, proposal và phạm vi dữ liệu assistant
- [ ] Đưa các cải tiến reliability runtime qua review/commit riêng

---

## Tuần 6: 31/08/2026 - 06/09/2026 — Hoàn thiện tài liệu và rà soát reliability

> Cập nhật đến ngày 01/09/2026.

### 6.1. Mục tiêu

- [x] Hoàn thiện tài liệu kỹ thuật, vận hành và bộ tài liệu demo
- [x] Cải thiện assistant về ngôn ngữ thời gian, quyền riêng tư và phạm vi truy hồi
- [x] Kiểm tra các cơ chế reliability runtime bằng kiểm thử tự động

### 6.2. Kết quả đạt được

| Hạng mục | Nội dung |
|---|---|
| Tài liệu | Bổ sung tài liệu vận hành runtime/feature operations, cập nhật contract/reconnect/README; bổ sung demo script, slide deck và script xây dựng presentation. |
| Assistant | Cải thiện hiểu biểu đạt thời gian tự nhiên, gợi ý proposal theo múi giờ người nói, giữ mention/private chat trong đúng phạm vi và cho assistant private đọc ngữ cảnh tài khoản theo quyền. |
| Reliability | Hoàn thiện kiểm thử cho rate limit, GZip, cursor pagination, translation cache, system health và circuit breaker; kết quả kiểm thử runtime hiện tại đạt 54/54. |
| Môi trường | Kiểm tra Alembic revision local, bổ sung migration còn thiếu và xác nhận backend health endpoint hoạt động. |

### 6.3. Vướng mắc và biện pháp xử lý

| Vướng mắc | Biện pháp | Kết quả |
|---|---|---|
| API history có nguy cơ trả kiểu dữ liệu cũ khi dùng cursor pagination | Điều chỉnh nhánh trả response và kiểm thử phân trang theo cursor | Cursor pagination trả đúng envelope, không lặp hoặc bỏ sót message |
| Database local có thể thiếu migration dù source đã cập nhật | Đối chiếu Alembic head, chạy migration và kiểm tra schema trước khi test luồng đăng nhập | Môi trường local khớp schema hiện hành |
| Dịch vụ ngoài lỗi liên tiếp gây latency lớn | Bổ sung circuit breaker, cache và metric health để fail-fast/có thể quan sát | Cơ chế runtime có kiểm thử trạng thái lỗi và phục hồi |

### 6.4. Bài học rút ra

1. Tài liệu vận hành cần mô tả giới hạn thực thi thực tế, đặc biệt với state in-memory và triển khai single-process.
2. Đối với phân trang, kiểm thử nhiều message cùng timestamp là cần thiết để phát hiện lỗi cursor composite.
3. Việc kiểm tra schema phải là một bước trong quy trình chạy local, không chỉ là công việc khi deploy.

### 6.5. Kế hoạch tuần tiếp theo

- [ ] Commit và review độc lập các thay đổi runtime đang ở working tree
- [ ] Kiểm tra E2E login, chat, calendar, OAuth và reminder trên môi trường deploy
- [ ] Theo dõi health metrics sau phát hành để hiệu chỉnh ngưỡng vận hành
