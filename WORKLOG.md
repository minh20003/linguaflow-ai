# Worklog — Team P-217

> Ghi lại tất cả công việc đã làm theo ngày. Ai làm gì, kết quả gì.

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

## [YYYY-MM-DD]

| Member | Task | Status | Output | Time |
|--------|------|--------|--------|------|
| | | | | |

**Tổng kết ngày:**

---

<!-- Format: copy block trên cho mỗi ngày làm việc -->
