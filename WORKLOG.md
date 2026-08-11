# NHẬT KÝ CÔNG VIỆC THEO NGÀY

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

## 09/08/2026

| Thành viên | Công việc | Trạng thái | Kết quả bàn giao | Thời lượng |
|---|---|---|---|---|
| Minh | F-01.2 — Backend Auth API và lưu cấu hình người dùng | Hoàn thành | Nhánh `feature/f-01-2-auth-user-config`, commit `509eef3` | — |

**Chi tiết F-01.2** (tham chiếu `Minh_report.md` trên nhánh tương ứng):

| Thành phần | Nội dung |
|---|---|
| `src/database/` | SQLAlchemy async với SQLite (aiosqlite), model `User` |
| `src/core/security.py` | Băm mật khẩu bcrypt, tạo và xác thực JWT |
| `src/core/deps.py` | Dependency `get_current_user` |
| `src/schemas/auth.py` | `LoginRequest`, `TokenResponse`, `UserResponse`, `UpdateLanguageRequest`; danh sách 13 mã ngôn ngữ ISO 639-1 |
| Endpoint | `POST /auth/login`, `GET /auth/me`, `PUT /auth/me/language` |
| `scripts/seed_dev_users.py` | Khởi tạo dữ liệu người dùng thử nghiệm (member và admin) |
| `tests/test_api/test_auth.py` | 16 test case |

**Tổng kết:** Tính năng backend đầu tiên hoàn thành, đang chờ review trước khi merge. Kết thúc Tuần 2.

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

<!-- Bổ sung theo mẫu trên cho mỗi ngày làm việc -->
