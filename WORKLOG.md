# Worklog — Team P-217

**Dự án:** LinguaFlow — AI Agent dịch tin nhắn đa ngôn ngữ real-time trong hội thoại
**Mã dự án:** P-217 · **Nhóm thực hiện:** 4U

Tài liệu ghi nhận công việc theo ngày: người thực hiện, nội dung công việc, trạng thái và kết quả bàn giao.

**Quy ước trạng thái:** `Hoàn thành` · `Đang thực hiện` · `Chưa bắt đầu` · `Tạm dừng`
**Ghi chú:** cột *Thời lượng* do từng thành viên tự ghi nhận. Ký hiệu `—` là chưa cập nhật.

---

## 25/07/2026

| Thành viên | Công việc | Trạng thái | Kết quả bàn giao | Thời lượng |
|---|---|---|---|---|
| Ban tổ chức | Khởi tạo kho mã nguồn `P-217` từ template AI20K | Hoàn thành | commit `d34da30` | — |

**Tổng kết:** Kho mã nguồn dự án được cấp phát. Nhóm bắt đầu Tuần 1.

---

## 26/07/2026

| Thành viên | Công việc | Trạng thái | Kết quả bàn giao | Thời lượng |
|---|---|---|---|---|
| Trà My | Khởi tạo dự án từ template, thiết lập cấu trúc thư mục | Hoàn thành | commit `1457a44` | — |

**Tổng kết:** Cấu trúc dự án chuẩn (`src/`, `tests/`, `docs/`, `scripts/`) sẵn sàng cho toàn nhóm.

---

## 28/07/2026

| Thành viên | Công việc | Trạng thái | Kết quả bàn giao | Thời lượng |
|---|---|---|---|---|
| Thuận | Kiểm thử hệ thống AI Usage Logging | Hoàn thành | commit `62223be` | — |

**Tổng kết:** Xác nhận AI logging hooks ghi nhận được dữ liệu, đáp ứng yêu cầu Deliverable số 4.

---

## 30/07/2026

| Thành viên | Công việc | Trạng thái | Kết quả bàn giao | Thời lượng |
|---|---|---|---|---|
| Minh | Bổ sung logging hooks cho Codex CLI | Hoàn thành | commit `c14a62b` | — |
| Minh | Khắc phục lỗi AI logging hooks không hoạt động trên Windows (`scripts/_pyrun.sh`) | Hoàn thành | commit `c4495a3` | — |

**Tổng kết:** Hooks hoạt động trên Windows, gỡ bỏ trở ngại cho các thành viên sử dụng hệ điều hành này.

---

## 02/08/2026

| Thành viên | Công việc | Trạng thái | Kết quả bàn giao | Thời lượng |
|---|---|---|---|---|
| Hưởng | Chuẩn hoá định dạng `JOURNAL.md`, thiết lập quyền thực thi cho `scripts/_pyrun.sh` | Hoàn thành | commit `1d30549` | — |

**Tổng kết:** Kết thúc Tuần 1. Hạ tầng kho mã nguồn và hệ thống logging hoàn tất, chuyển sang giai đoạn thiết kế.

---

## 03/08/2026 - 08/08/2026

> Ghi nhận tổng hợp. Phân bổ chi tiết theo từng ngày chưa được cập nhật đầy đủ tại thời điểm lập báo cáo.

| Thành viên | Công việc | Trạng thái | Kết quả bàn giao | Thời lượng |
|---|---|---|---|---|
| Toàn nhóm | Xây dựng 6 sơ đồ thiết kế Gate 2 (System Design, Sequence, Use Case, Agent Flow, Data Flow, ER) | Hoàn thành | Bộ 6 sơ đồ thiết kế và hình ảnh minh họa | — |
| Minh | Review System Design, đề xuất phương án lựa chọn LLM | Hoàn thành | Ý kiến ghi trong sheet *Design* (TO DO LIST) | — |
| Hưởng | Review Sequence Diagram, đề xuất thống nhất ngữ cảnh 3-5 tin và tách Main Database khỏi Context Memory | Hoàn thành | Ý kiến ghi trong sheet *Design* | — |
| Thuận | Review Use Case Diagram, đề xuất loại bỏ use case kỹ thuật và tách riêng hai actor | Hoàn thành | Ý kiến ghi trong sheet *Design* | — |
| Thuận | Review ER Diagram | Hoàn thành | Ý kiến ghi trong sheet *Design* | — |
| Trà My | Review Data Flow; phân rã F-01 đến F-06 thành 14 đầu việc | Hoàn thành | Sheet *Code* (TO DO LIST) | — |

**Tổng kết:** Bộ sơ đồ Gate 2 hoàn thành và được review chéo đầy đủ. Các ý kiến review được ghi nhận nhưng chưa áp dụng hoàn toàn vào tệp gốc; nội dung này được xử lý ở Tuần 3.

---

## 04/08/2026

| Thành viên | Công việc | Trạng thái | Kết quả bàn giao | Thời lượng |
|---|---|---|---|---|
| Trà My | Cấu hình và kiểm thử CI/CD (GitHub Actions) | Hoàn thành | commit `cb7a155` | — |

**Tổng kết:** Pipeline CI vận hành, Pull Request được kiểm tra tự động.

---

## 2026-07-29

| Member | Task | Status | Output | Time |
|--------|------|--------|--------|------|
| minh20003 | Khởi tạo dự án từ starter template, tạo `.venv` + cài `requirements.txt` | ✅ Done | Cấu trúc `src/`, `tests/`, `data/` sẵn sàng | 0.5h |
| minh20003 | Cài AI logging hooks (`bash scripts/setup_hooks.sh`) | ✅ Done | Hook không ghi được log nào → chuyển sang debug | 0.25h |
| minh20003 | Debug & fix AI logging hooks trên Windows | ✅ Done | Commit `c14a62b` — 4 file, +63/−19 | 1h |
| minh20003 | Verify end-to-end pipeline logging | ✅ Done | 46 event đã log, submit server trả `202` | 0.25h |

**Tổng kết ngày:** Dựng xong môi trường dự án và thông toàn bộ đường ống AI logging. Phần lớn thời gian dồn vào 2 lỗi tương thích Windows khiến hook im lặng hoàn toàn — đã xác định nguyên nhân gốc và fix, log giờ ghi và nộp lên server bình thường.

### Chi tiết kỹ thuật — fix AI logging hooks

Hook cài theo đúng hướng dẫn nhưng `.ai-log/session.jsonl` không có dòng nào. Hai nguyên nhân độc lập:

**1. `scripts/_pyrun.sh` — `python3` trên PATH là Microsoft Store stub**

```
$ command -v python3
/c/Users/Admin/AppData/Local/Microsoft/WindowsApps/python3
$ python3 -c "print(1)"
Python was not found; run without arguments to install from the Microsoft Store...
$ echo $?
49
```

Script gốc chọn interpreter bằng `command -v python3` — stub này *có* trên PATH nên luôn được chọn, rồi chết ngay khi chạy. Hook exit khác 0, không ghi gì, và vì hook được thiết kế "không bao giờ chặn AI tool" nên lỗi bị nuốt im lặng.

*Fix:* probe từng candidate bằng `-c pass` trước khi dùng để loại stub, và ưu tiên `.venv` của repo lên đầu (do `submit_log.py` cần `python-dotenv` để đọc `AI_LOG_SERVER` từ `.env`).

**2. `scripts/setup_hooks.ps1` — BOM phá shebang của pre-push hook**

`Set-Content -Encoding UTF8` trên PowerShell 5.1 chèn BOM vào đầu file:

```
Set-Content -Encoding UTF8   → EF BB BF 23 21 2F   (BOM đứng trước "#!")
File.WriteAllText(UTF8:false) → 23 21 2F 75 73 72   (đúng)
```

BOM nằm trước `#!` khiến git không nhận ra shebang → pre-push hook không chạy → log không được nộp khi push.

*Fix:* ghi bằng `File.WriteAllText` với `UTF8Encoding($false)` và ép LF.

**Kiểm chứng sau khi fix**

| Hạng mục | Kết quả |
|---|---|
| `_pyrun.sh` resolve interpreter | `.venv\Scripts\python.exe` |
| Hook ghi log tiếng Việt | Không lỗi mã hoá |
| pre-push hook | `23 21 2F` — không BOM |
| `submit_log.py` | `Submitted 13 entries → 202` |
| Fallback khi máy chưa có `.venv` | `C:\Program Files\Python313\python.exe` |
| Overhead thêm mỗi lần gọi hook | ~0.2s |

**Ghi chú cho team**

- Nhớ `pip install -r requirements.txt` trong `.venv`. Thiếu `python-dotenv` thì log vẫn ghi nhưng **không nộp được** (báo `AI_LOG_SERVER not set`).
- Hai fix trên chỉ ảnh hưởng Windows. `scripts/setup_hooks.sh` (Linux/macOS) không đụng tới.
- Cần báo BTC: lỗi Store stub sẽ làm câm log của mọi đội dùng Windows chưa cài Python thủ công, không riêng P-217.

---

## 2026-07-30

| Member | Task | Status | Output | Time |
|--------|------|--------|--------|------|
| minh20003 | Commit & push cấu hình logging lên `develop` | ✅ Done | `c14a62b Add Codex logging hooks` | 0.25h |
| minh20003 | Tạo branch `docs`, cập nhật WORKLOG | ✅ Done | Branch `docs` | 0.25h |

**Tổng kết ngày:**

---

## 10/08/2026

| Thành viên | Công việc | Trạng thái | Kết quả bàn giao | Thời lượng |
|---|---|---|---|---|
| Trà My | Rà soát chéo toàn bộ thiết kế, đối chiếu tài liệu Gate 1 và Gate 2 với mã nguồn hiện có | Hoàn thành | Xác định 4 lỗi thiết kế và các điểm mâu thuẫn giữa đặc tả với mã nguồn xác thực | — |
| Trà My | Xây dựng `ARCHITECTURE.md`: kiến trúc thành phần và 10 quyết định kiến trúc (ADR-01 đến ADR-10) | Hoàn thành | `ARCHITECTURE.md` | — |
| Trà My | Chuyển 6 sơ đồ sang định dạng Mermaid, hiệu chỉnh các điểm không nhất quán | Hoàn thành | `docs/architecture_diagram.md` | — |
| Trà My | Xây dựng `docs/CONTRACT.md`: đặc tả giao diện API, WebSocket, cơ sở dữ liệu | Hoàn thành | `docs/CONTRACT.md` | — |
| Trà My | Chuẩn hoá quy định làm việc nhóm từ tệp Excel quản trị | Hoàn thành | `CONTRIBUTING.md` | — |
| Trà My | Hiện thực hoá lớp LLM đa provider (Groq, DeepSeek, Gemini, OpenAI) | Hoàn thành | `src/services/llm.py`, `src/config.py`, `requirements.txt`, `.env.example` | — |
| Hưởng | F-05.2 — API tiếp nhận và lưu trữ phản hồi | Đang thực hiện | — | — |
| Thuận | F-01.1, F-02.1, F-04.1 — Giao diện đăng nhập, khung chat, chuyển đổi hiển thị song ngữ | Đang thực hiện | Phát triển trên các nhánh `feature/*` riêng | — |
| Minh | F-02.2 — WebSocket routing và phân phối tin nhắn | Chưa bắt đầu | — | — |

**Tổng kết:** Bắt đầu Tuần 3 (tuần Demo 1). Hoàn thành chuẩn hoá bộ tài liệu kỹ thuật làm nguồn tham chiếu duy nhất cho phát triển song song; khắc phục 4 lỗi thiết kế ảnh hưởng tới F-05 và tính năng chat nhóm; kiểm chứng 4 LLM provider khởi tạo đúng. Trọng tâm còn lại của tuần: hoàn thiện luồng dịch end-to-end (F-02 và F-03) phục vụ Demo 1.

---

> Các ngày từ 11/08/2026 trở đi được lập từ lịch sử commit của kho mã nguồn, nên mọi dòng đều đối chiếu được. Cột **Thời lượng** để trống: dự án không ghi nhận số giờ ở đâu, và điền số ước lượng sẽ khiến tài liệu trông đầy đủ hơn mức nó thật sự có.

## 12/08/2026

| Thành viên | Công việc | Trạng thái | Kết quả bàn giao | Thời lượng |
|---|---|---|---|---|
| Minh | Xóa plan md.; Thêm kiểm thử tích hợp kết nối lại WebSocket F-02.3 và tài liệu hợp đồng kết nối lại | Hoàn thành | 2 commit — Khác, Phát triển | — |
| Thuận | Tổ chức các tính năng và tài liệu thiết kế.; Lưu trữ người dùng và quản lý phiên làm việc. | Hoàn thành | 2 commit — Phát triển, Tái cấu trúc | — |
| Trà My | Thêm demo song song cho hai ngôn ngữ đọc.; Giữ khách truy cập đã đăng nhập ở lại trang chat.; Kết nối xử lý đăng ký và phiên làm việc với backend.; Thêm các endpoint đăng ký, tìm kiếm người dùng và ngôn ngữ.; và 4 thay đổi khác | Hoàn thành | 8 commit — Khắc phục, Phát triển | — |

---

## 13/08/2026

| Thành viên | Công việc | Trạng thái | Kết quả bàn giao | Thời lượng |
|---|---|---|---|---|
| Trà My | Khôi phục nhánh main về trạng thái khởi tạo dự án; Ghi nhận telemetry contract và phương pháp đánh giá; Lưu trữ lịch sử đánh giá và so sánh hai lần chạy; Đo lường đúng các chỉ số mà quá trình đánh giá yêu cầu; và 5 thay đổi khác | Hoàn thành | 9 commit — Khắc phục, Phát triển, Tài liệu, revert | — |

---

## 15/08/2026

| Thành viên | Công việc | Trạng thái | Kết quả bàn giao | Thời lượng |
|---|---|---|---|---|
| Trà My | Lưu trữ mọi bản ghi nhật ký AI trong thư mục .ai-log của kho lưu trữ; Ghi lại cấu trúc triển khai và các phần mở rộng của API; Cấu hình ứng dụng để có thể triển khai bên ngoài máy này — Postgres, Alembic, $PORT; Không lưu bản dịch của văn bản đã được người gửi thay đổi (F-03); và 3 thay đổi khác | Hoàn thành | 7 commit — Khắc phục, Phát triển, Tài liệu | — |

---

## 16/08/2026

| Thành viên | Công việc | Trạng thái | Kết quả bàn giao | Thời lượng |
|---|---|---|---|---|
| Minh | Thêm tài liệu kiến trúc và bằng chứng benchmark đánh giá; Giới hạn và cung cấp số liệu thống kê dịch thuật; Thêm bộ nhớ đệm dịch thuật thận trọng; Hoàn tất khôi phục kết nối lại websocket; và 1 thay đổi khác | Hoàn thành | 5 commit — Khắc phục, Phát triển, Tài liệu | — |
| Thuận | Đồng bộ frontend nhánh develop để khớp chính xác với feature/chat-integration-ui (xóa các tệp thừa); Ghi đè frontend bằng phiên bản của feature/chat-integration-ui; Xóa các tệp không được cập nhật trong ngày (dọn dẹp các tệp cũ từ 5 ngày trước); Tích hợp giao diện chat với backend | Hoàn thành | 4 commit — Hạ tầng, Phát triển | — |
| Trà My | Ghi lại hai tính năng và các quyết định đằng sau chúng; Hộp chỉnh sửa F-05, ngôn ngữ giao diện và các sửa lỗi thực tế; Các chỉnh sửa dịch thuật riêng tư và ngôn ngữ giao diện riêng biệt | Hoàn thành | 3 commit — Phát triển, Tài liệu | — |

---

## 17/08/2026

| Thành viên | Công việc | Trạng thái | Kết quả bàn giao | Thời lượng |
|---|---|---|---|---|
| Minh | Hoàn thành bản địa hóa UI đa ngôn ngữ; Chuẩn hóa lockfile đã khôi phục; Hoàn tác "feat(frontend): overwrite frontend with feature/chat-integration-ui version"; Hoàn tác "chore(frontend): sync develop frontend to exactly match feature/chat-integration-ui (remove extra files)" | Hoàn thành | 4 commit — Hạ tầng, Khác, Phát triển | — |
| Thuận | Xóa pnpm store khỏi repository; Tinh chỉnh tính năng dịch chat và kiểm soát tài khoản; Cấu hình proxy API chat và URL websocket; Thay thế mã nguồn nhánh bằng develop | Hoàn thành | 4 commit — Hạ tầng, Khác, Khắc phục | — |

---

## 18/08/2026

| Thành viên | Công việc | Trạng thái | Kết quả bàn giao | Thời lượng |
|---|---|---|---|---|
| Thuận | Bản địa hóa giao diện chat và hỗ trợ tin nhắn chuyển tiếp; Tăng cường bảo mật quy trình khởi chạy container production; Cập nhật ví dụ cấu hình môi trường cơ sở dữ liệu; Thay thế frontend develop bằng tích hợp chat; và 2 thay đổi khác | Hoàn thành | 6 commit — Hạ tầng, Khắc phục, Phát triển | — |

---

## 19/08/2026

| Thành viên | Công việc | Trạng thái | Kết quả bàn giao | Thời lượng |
|---|---|---|---|---|
| Minh | Thêm tính năng đăng ký bằng OTP qua email; Khôi phục frontend P0 sau khi bị ghi đè bởi tích hợp chat | Hoàn thành | 2 commit — Khắc phục, Phát triển | — |
| Thuận | Chuẩn hóa định danh hồ sơ và nội dung tiếng Anh; Tinh chỉnh nút đăng nhập Google tương thích giao diện; Thêm tính năng đăng nhập bằng Google đã xác thực; Sử dụng đầu ra Next mặc định trên Vercel | Hoàn thành | 4 commit — Khắc phục, Phát triển | — |
| Trà My | Sửa đổi ADR-13 và ghi lại kiểm toán guardrail.; Ngăn rò rỉ ngữ cảnh và phản hồi từ chối tiếp cận người nhận.; Đảm bảo ruff chạy thành công sau khi hợp nhất email-OTP | Hoàn thành | 3 commit — Chuẩn hoá mã, Phát triển, Tài liệu | — |

---

## 20/08/2026

| Thành viên | Công việc | Trạng thái | Kết quả bàn giao | Thời lượng |
|---|---|---|---|---|
| Trà My | Cung cấp bộ thuật ngữ khởi đầu để tính năng hoạt động ngay từ ngày đầu; Xem xét hàng đợi các thuật ngữ được đề xuất; Đề xuất các thuật ngữ từ các bản sửa lỗi được nhiều người đồng ý; Truy xuất ngữ cảnh cũ hơn theo ngữ nghĩa, không chỉ theo thời gian.; và 9 thay đổi khác | Hoàn thành | 13 commit — Hạ tầng, Khắc phục, Phát triển, Tài liệu | — |

---

## 21/08/2026

| Thành viên | Công việc | Trạng thái | Kết quả bàn giao | Thời lượng |
|---|---|---|---|---|
| Minh | Hỗ trợ đăng ký OTP qua email trên UI, sửa Google button client ID env, và ánh xạ lại cổng Postgres thành 5433; Đồng bộ các route xác thực Google, schema và migration head để tích hợp develop_v2; Hoàn thành lõi conversation intelligence; Liên kết migration của Batch G sau ef06ca79ef49; và 1 thay đổi khác | Hoàn thành | 5 commit — Hạ tầng, Khắc phục, Phát triển | — |
| Thuận | Làm rõ cách diễn đạt về ngôn ngữ ưu tiên; Thêm quản trị nhóm và xử lý phiên auth bền bỉ; Thêm quản trị nhóm và xử lý phiên auth bền bỉ; Giữ lại cơ chế dự phòng Google env và cổng cơ sở dữ liệu local; và 7 thay đổi khác | Hoàn thành | 11 commit — Khác, Khắc phục, Phát triển | — |
| Trà My | Đánh giá liệu đối tượng người nghe và vị thế có thực sự làm thay đổi bản dịch | Hoàn thành | 1 commit — Kiểm thử | — |

---

## 22/08/2026

| Thành viên | Công việc | Trạng thái | Kết quả bàn giao | Thời lượng |
|---|---|---|---|---|
| Trà My | Liên kết bản triển khai thực tế; Liệt kê các biến SMTP mà production guard thực sự yêu cầu; Ghim thanh điều hướng và thêm lối quay lại màn hình quản trị cho mục Settings; Chỉnh sửa và khôi phục một thuật ngữ, đồng thời mô tả chức năng của tùy chọn "keep as is"; và 18 thay đổi khác | Hoàn thành | 22 commit — Khắc phục, Kiểm thử, Phát triển, Tài liệu | — |

---

## 24/08/2026

| Thành viên | Công việc | Trạng thái | Kết quả bàn giao | Thời lượng |
|---|---|---|---|---|
| Minh | Sử dụng URL API công khai đã cấu hình; Thêm view phản hồi dịch thuật và các endpoint admin; Đồng bộ package-lock và sửa các import sau khi merge develop_v2; Thêm luồng đặt lại mật khẩu và các cấu hình triển khai VPS; và 3 thay đổi khác | Hoàn thành | 7 commit — Hạ tầng, Khắc phục, Phát triển | — |
| Thuận | Lưu trữ các thay đổi glossary qua backend; Tích hợp trợ lý admin dashboard và lịch | Hoàn thành | 2 commit — Khắc phục, Phát triển | — |
| Trà My | Khôi phục các tệp frontend/ của develop_v2 bị mất do cơ chế phát hiện đổi tên; Trỏ các tham chiếu đường dẫn còn lại đến frontend-v1/; Đổi tên frontend/ thành frontend-v1/ trước khi hợp nhất develop_v2; Sửa lỗi chính xác của số liệu thống kê, thêm chi phí theo từng mô hình và hiển thị từ ngữ của chính người gửi; và 1 thay đổi khác | Hoàn thành | 5 commit — Hạ tầng, Khắc phục, Phát triển, Tài liệu | — |

---

## 25/08/2026

| Thành viên | Công việc | Trạng thái | Kết quả bàn giao | Thời lượng |
|---|---|---|---|---|
| Trà My | Thêm bài nộp Day 23 Product Metrics Lab cho Nguyen Thi Tra My (MSSV: 2A202601026) | Hoàn thành | 1 commit — Phát triển | — |

---

## 26/08/2026

| Thành viên | Công việc | Trạng thái | Kết quả bàn giao | Thời lượng |
|---|---|---|---|---|
| Minh | Khắc phục lỗi phân giải đường dẫn tệp .env và chuẩn hóa ký tự phân cách định giá mô hình.; Khắc phục lỗi xác thực CI và kéo dài timeout.; Tăng timeout kiểm thử CI; Tránh xung đột cổng PostgreSQL trong CI; và 1 thay đổi khác | Hoàn thành | 5 commit — Khắc phục | — |
| Thuận | Tinh chỉnh tính năng dịch trò chuyện và telemetry của admin.; Tích hợp dịch thuật trực tiếp và dữ liệu quản lý | Hoàn thành | 2 commit — Phát triển | — |
| Trà My | Thay đổi runner thành self-hosted và ubuntu-latest | Hoàn thành | 1 commit — Khác | — |

---

## 27/08/2026

| Thành viên | Công việc | Trạng thái | Kết quả bàn giao | Thời lượng |
|---|---|---|---|---|
| Minh | Khôi phục trạng thái các lượt thử lại voice transcription.; Đánh số phiên bản công cụ release VPS.; Thêm tin nhắn thoại được phiên âm bằng Gemini | Hoàn thành | 3 commit — CI/CD, Khắc phục, Phát triển | — |
| Trà My | Cho phép người dùng kết nối Google Calendar.; Đẩy thay đổi lên Google ngay khi được thực hiện.; Vẽ sơ đồ luồng của assistant, các bảng mới và đường dẫn đến Google; Ghi lại liên kết Google Calendar và các sự kiện thời gian thực của assistant; và 18 thay đổi khác | Hoàn thành | 22 commit — Kiểm thử, Phát triển, Tài liệu | — |

---

## 28/08/2026

| Thành viên | Công việc | Trạng thái | Kết quả bàn giao | Thời lượng |
|---|---|---|---|---|
| Minh | Tăng cường bảo mật truyền tải portable release; Cho phép thành viên tải xuống các tệp đính kèm đang chờ.; Sửa thứ tự import auth schema.; Tự động hóa quy trình phát hành production của develop_v2. | Hoàn thành | 4 commit — CI/CD, Chuẩn hoá mã, Khắc phục | — |
| Thuận | Tinh chỉnh quyền riêng tư của calendar, task inbox và assistant. | Hoàn thành | 1 commit — Phát triển | — |
| Trà My | Cập nhật .env.example khớp với các cấu hình thực tế mã nguồn đọc; Cấu hình run.sh khởi động frontend và backend thực tế của dự án; Đo lường riêng biệt quá trình truy xuất và tạo của assistant.; Bao phủ chunking, retrieval, tool registry và gate.; và 2 thay đổi khác | Hoàn thành | 6 commit — Hạ tầng, Khắc phục, Kiểm thử, Phát triển | — |

---

## 29/08/2026

| Thành viên | Công việc | Trạng thái | Kết quả bàn giao | Thời lượng |
|---|---|---|---|---|
| Minh | Tăng cường độ ổn định cho STT runtime và cơ chế khôi phục thử lại.; Trỏ README tới VPS production | Hoàn thành | 2 commit — Khắc phục, Tài liệu | — |
| Thuận | Tinh chỉnh giao diện hộp thư nhiệm vụ và cài đặt trợ lý.; Làm mới giao diện lịch, quản trị và xác thực. | Hoàn thành | 2 commit — Khắc phục, Phát triển | — |
| Trà My | Đọc thời gian từ tin nhắn và nhận diện cả các cuộc hẹn.; Ngăn giới hạn token của trình dịch làm tắt tính năng phát hiện đề xuất.; Cho phép hoàn thành và phê duyệt đề xuất chưa hoàn tất; Quyết định đề xuất tại nơi đề xuất được đưa ra và dọn dẹp sau đó; và 7 thay đổi khác | Hoàn thành | 11 commit — Hạ tầng, Khắc phục, Phát triển | — |

---

## 30/08/2026

| Thành viên | Công việc | Trạng thái | Kết quả bàn giao | Thời lượng |
|---|---|---|---|---|
| Minh | Khôi phục các bài kiểm tra trợ lý độc lập và cổng kiểm duyệt production. | Hoàn thành | 1 commit — Khắc phục | — |

---

## 31/08/2026

| Thành viên | Công việc | Trạng thái | Kết quả bàn giao | Thời lượng |
|---|---|---|---|---|
| Thuận | Thêm hướng dẫn vận hành runtime và tính năng. | Hoàn thành | 1 commit — Tài liệu | — |
| Trà My | Thêm kịch bản demo, slide thuyết trình và kịch bản xây dựng slide.; Cung cấp cho trợ lý nguồn thời gian đáng tin cậy và cho phép thẻ của trợ lý phản hồi lại. | Hoàn thành | 2 commit — Phát triển, Tài liệu | — |

---

## 01/09/2026

| Thành viên | Công việc | Trạng thái | Kết quả bàn giao | Thời lượng |
|---|---|---|---|---|
| Trà My | Trình bày lại phân tích khả thi trong report register.; Tối ưu hóa độ đọc hiểu của kịch bản khả thi, sau đó áp dụng các số liệu thực tế.; Lập luận về sai lệch biên dịch bằng các cơ chế và định danh nhóm phát triển.; Lập luận lý do sản phẩm tồn tại và chỉ ra điểm giới hạn của lập luận đó.; và 11 thay đổi khác | Hoàn thành | 15 commit — Khắc phục, Phát triển, Tài liệu | — |

