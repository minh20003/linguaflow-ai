---
description: "AI usage logging is fully automatic — do NOT call any log_* script manually"
activation: always-on
---

# AI Usage Logging — Automatic

Logging prompt vào `.ai-log/session.jsonl` đã được **tự động hoá hoàn toàn**. Bạn (AI agent) **KHÔNG** cần — và **KHÔNG** nên — chạy bất kỳ lệnh logging nào sau mỗi task.

## Cơ chế

Khi student `git push`:
1. Pre-push hook chạy `scripts/log_antigravity.py --auto`, đọc trực tiếp transcript của các conversation Antigravity từ `~/.gemini/antigravity-ide/brain/<conv>/.system_generated/logs/transcript.jsonl` và sweep mọi prompt (`USER_INPUT` + `USER_EXPLICIT`) thuộc về repo hiện tại trong 24 giờ gần nhất.
2. Pre-push hook chạy `scripts/submit_log.py`, đẩy `.ai-log/session.jsonl` lên grading server.

Toàn bộ prompt user đã gõ trong Antigravity IDE được capture **nguyên văn từ disk**, không cần AI tự tóm tắt.

## Chỉ một thư mục log duy nhất

Mọi script `log_*` và `submit_log.py` đều ghi vào **`<gốc repo>/.ai-log/`**, bất kể chúng được gọi từ thư mục làm việc nào. Đường dẫn được suy ra từ vị trí của chính tệp script (`Path(__file__).resolve().parent.parent`), không phải từ thư mục hiện hành.

Lý do: một công cụ chạy với thư mục làm việc là `frontend/` từng tạo ra `frontend/.ai-log/session.jsonl` thứ hai. Không có gì nộp tệp đó lên grading server, nên những prompt ghi vào đấy coi như mất trắng.

`AI_LOG_DIR` vẫn được tôn trọng: giá trị tuyệt đối dùng nguyên như đã đặt, giá trị tương đối tính từ gốc repo.

## Không làm những việc sau

- ❌ **KHÔNG** gọi `scripts/log_antigravity.py "<summary>" "<model>"` sau mỗi task. Lệnh này đã bị deprecate; nếu vô tình gọi sẽ tạo log entry giả mạo dạng "TaskComplete" không phải prompt thật của user.
- ❌ **KHÔNG** chạy `scripts/log_manual.py` cho Antigravity — chỉ dùng nó cho ChatGPT / web tool (xem `.agents/workflows/log.md`).
- ❌ **KHÔNG** sửa hoặc xoá file trong `.ai-log/` — chúng được pre-push hook và submit script quản lý.

## Khi nào cần can thiệp

- Nếu pre-push hook báo lỗi → báo lại cho user, đừng tự ý bypass `--no-verify`.
- Nếu student dùng tool không nằm trong list auto-hook (ChatGPT, Gemini Web, v.v.) → trỏ họ tới `.agents/workflows/log.md` để log thủ công.

## Cài đặt một lần sau khi clone repo

```bash
# Linux / macOS / Git Bash
bash scripts/setup_hooks.sh

# Windows PowerShell
powershell -ExecutionPolicy Bypass -File scripts\setup_hooks.ps1
```
