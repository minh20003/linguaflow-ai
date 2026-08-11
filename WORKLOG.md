# Worklog — Team P-217
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
| Toàn nhóm | Xây dựng 6 sơ đồ thiết kế Gate 2 (System Design, Sequence, Use Case, Agent Flow, Data Flow, ER) | Hoàn thành | `docs/T217/Gate 2/ArchitectureDesign.drawio` và 4 tệp PNG | — |
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
| Fhttps://github.com/AI20K-Build-Phase-Cohort-3/P-217/pull/3/conflict?name=WORKLOG.md&ancestor_oid=675408c254bfea5b87ac3b9fcd1c628353c3dfdf&base_oid=5a27567defcbffe9c4e62c71354a9147fe66fdc4&head_oid=0d126680b39218468921ac2b21e56323829d0147allback khi máy chưa có `.venv` | `C:\Program Files\Python313\python.exe` |
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

<!-- Bổ sung theo mẫu trên cho mỗi ngày làm việc -->
