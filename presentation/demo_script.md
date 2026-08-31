# Kịch bản Demo (2 phút) — Xưng hô & Glossary trong LinguaFlow

Toàn bộ input/output dùng để "chốt" (câu demo chính) lấy nguyên văn từ `eval/golden_set.jsonl`, đã được xác nhận bởi các test đang **pass**. Phần ngữ cảnh dựng trước (bên dưới) là tự viết, vì golden set không đủ dài để hệ thống tự nhận ra vai vế — xem lý do ngay sau đây.

Bạn **không cần và không thể** chỉnh DB trực tiếp — toàn bộ chuẩn bị dưới đây làm được **chỉ bằng cách gõ tin nhắn thật trong app**, không đụng tới cơ sở dữ liệu.

**Xác minh lại trước khi lên demo (bắt buộc, chạy 1 lần trong ngày):**
```bash
pytest tests/test_eval/test_golden_set.py tests/test_services/test_bucket_fanout.py tests/test_agents/test_customize.py tests/test_services/test_glossary.py tests/test_services/test_profile_inference.py -v
```
Nếu có test đỏ, dừng và sửa trước khi demo — đừng demo case đang fail.

---

## Vì sao phải dựng hội thoại trước — và vì sao dựng bằng cách gõ chuyện thật, không phải copy 2 dòng ngữ cảnh

Có **hai cơ chế "ngữ cảnh" khác nhau** trong hệ thống:

**1. Ngữ cảnh dịch tức thời** (`build_context`, đọc 3-5 tin gần nhất) — dùng cho Case 1. Có ngay khi tin nhắn được lưu, gõ trực tiếp lúc dựng hội thoại là đủ.

**2. Hồ sơ vị thế người nói / đối tượng hội thoại** (`honorific_profile` từng thành viên, `domain`/`audience` hội thoại — dùng cho Case 2 và Case 3) — đây là kết quả của một **lượt LLM chạy nền, tự động, kích hoạt ngay khi hội thoại đủ 5 tin nhắn** (`MIN_MESSAGES_BEFORE_FIRST_RUN = 5`, `src/services/profile_inference.py`). Việc này chạy như một tác vụ nền ngay trong lúc gửi tin nhắn thứ 5 — **không cần đợi lâu, chỉ vài giây** để LLM trả lời và ghi kết quả — và **không cần đụng DB**. `customize` chỉ đọc kết quả này, không tự suy luận tại chỗ.

**Điểm quan trọng nhất — vì sao không thể chỉ copy 2 dòng ngữ cảnh từ golden set:** mô hình suy luận vị thế **đọc chính lời của người đọc**, không chỉ lời người gửi. Nếu người đọc chỉ ngồi im không nói gì, mô hình không có gì để dựa vào và trả về mặc định `peer` (trung tính) — đúng câu trong chính prompt suy luận: *"nếu không có gì để dựa vào cho một người nói, trả lời `peer`."* Vì vậy 2 dòng ngữ cảnh của golden set (chỉ có người gửi nói) **không đủ** để hệ thống tự gán đúng vai — cần dựng một đoạn hội thoại mà **cả hai người đọc đều chủ động thể hiện vị thế của mình** qua lời nói.

Mô hình xác định vị thế dựa trên **hành vi trong câu nói**, không phải xưng hô đơn thuần:
- `senior` — người khác nhường lời, tự mình giao việc hoặc duyệt việc
- `junior` — báo cáo tiến độ, xin duyệt, nhận chỉ thị
- `client` — là khách hàng hoặc bên ngoài tổ chức
- `peer` — không có gì khác biệt rõ ràng (mặc định an toàn khi mô hình không chắc)

Và với `audience`: `client` khi có **bên ngoài tổ chức** xuất hiện trong phòng, `internal` khi mọi người cùng một tổ chức.

| Case | Cần gì | Cách dựng |
|---|---|---|
| 1 — Đại từ 1-1 | 2 dòng lịch sử ngay trước câu demo | Gõ trực tiếp, không cần chờ |
| 2 — Xưng hô nhóm | Cả 2 người đọc phải **tự nói** ra vị thế của mình (≥5 tin trong hội thoại) | Gửi đoạn hội thoại dựng sẵn bên dưới, đợi vài giây |
| 3 — Glossary theo audience | Hội thoại phải **tự lộ rõ** có/không có người ngoài tổ chức (≥5 tin) | Gửi 2 đoạn hội thoại dựng sẵn bên dưới, đợi vài giây |

---

## Chuẩn bị trước (làm ở hậu trường, không tính vào 2 phút — chỉ cần app, không cần DB)

### Bước 1 — Hội thoại A (1-1, cho Case 1)

User A (English) ↔ User B (Vietnamese). Gửi đúng thứ tự:
1. User A: `Could you send us the updated project plan?`
2. User B: `Vâng, em gửi anh trong hôm nay ạ`
3. *(để dành — đây là câu demo, xem Case 1 ở Timeline)*

Case này dùng ngữ cảnh tức thời, không cần chờ — xong ngay.

### Bước 2 — Hội thoại B (nhóm, cho Case 2 — xưng hô theo vị thế)

3 thành viên: U01 gửi tiếng Anh (vai trò kiểu PM), U02 và U03 đọc tiếng Việt — **để dành U02 là reader-senior, U03 là reader-junior**. Gửi đúng thứ tự, đợi hết cả đoạn rồi mới sang bước 3:

1. U01 (EN): `Can everyone confirm they've seen the updated spec doc?`
2. U02 (VI): `Anh xem rồi, em cứ triển khai theo bản đó nhé`
3. U03 (VI): `Dạ vâng anh, em sẽ cập nhật lại phần API doc trong hôm nay ạ`
4. U01 (EN): `Great, let me know if you hit any blockers`
5. U02 (VI): `Em làm xong thì gửi anh check lại trước khi merge nhé`
6. U03 (VI): `Dạ, có gì em báo lại anh chị ngay ạ`

Đây là 6 tin — đủ ngưỡng 5 tin để kích hoạt suy luận, và U02/U03 đều **tự nói** ra vị thế của mình: U02 duyệt việc, giao việc, yêu cầu gửi mình check trước khi merge (dấu hiệu `senior`); U03 xin nhận việc, báo cáo tiến độ, xưng "dạ...em...ạ" (dấu hiệu `junior`). Đợi khoảng **10-15 giây** sau tin thứ 6 rồi mới gửi câu demo.

*(để dành câu demo Case 2 — xem Timeline)*

### Bước 3 — Hội thoại C (nhóm nội bộ, cho Case 3 — nửa "internal")

2 thành viên, cùng một team, không nhắc tới ai bên ngoài:

1. U01 (EN): `I pushed the fix to staging this morning`
2. U02 (VI): `Ok để mình xem lại`
3. U01 (EN): `Also updated the API docs, let me know if the endpoint naming makes sense`
4. U02 (VI): `Ừ ổn đó, để mình merge luôn`
5. U01 (EN): `Thanks, ping me if staging breaks again`

5 tin, giọng điệu "cùng một đội" tự nhiên — không ai nhắc tới khách hàng hay bên ngoài, hệ thống sẽ tự đọc ra `audience: internal`.

*(để dành câu demo Case 3-internal)*

### Bước 4 — Hội thoại D (nhóm khách hàng, cho Case 3 — nửa "client")

2 thành viên, một bên là đội dự án, một bên là khách hàng — **chú ý các cụm "bên tôi"/"phía chúng tôi"**, đây là tín hiệu rõ nhất báo hiệu có bên ngoài tổ chức:

1. U01 (EN): `We have prepared the demo for your team`
2. U02 (VI): `Cảm ơn, bên tôi sẽ xem trong hôm nay`
3. U01 (EN): `Sure, let us know if you'd like any changes before the deadline`
4. U02 (VI): `Dạ được, phía chúng tôi sẽ phản hồi sớm nhất có thể`
5. U01 (EN): `Great, looking forward to your feedback`

5 tin — hệ thống sẽ tự đọc ra `audience: client` nhờ "bên tôi"/"phía chúng tôi" lặp lại hai lần, một dấu hiệu khó nhầm.

*(để dành câu demo Case 3-client)*

### Bước 5 — Xác minh trước khi lên sân khấu (làm được mà không cần DB)

Gọi `GET /api/v1/conversations` bằng tài khoản bất kỳ đang ở trong hội thoại B — response trả về `members[].honorific_profile` cho từng người. Kiểm tra đúng: U02 = `senior`, U03 = `junior`. Nếu vẫn thấy `peer` cho một trong hai, đợi thêm hoặc gửi thêm 1-2 tin cùng giọng điệu rồi kiểm tra lại — mô hình có thể cần thêm bằng chứng.

Với hội thoại C/D không có endpoint lộ `audience` cho người dùng thường — cách xác minh thực tế là **thử trước** câu demo Case 3 ở cả hai hội thoại một lần trước giờ diễn, xem đúng chữ có đổi (UI/deadline giữ nguyên ở C, đổi thành giao diện/hạn chót ở D) hay chưa. Nếu đúng, đừng gửi lại — để dành cho lúc lên demo.

### Bước 6 — Việc khác

- Gõ sẵn 4 câu demo (Case 1, 2, 3-internal, 3-client) vào một file text để copy-paste khi lên sân khấu — không gõ tay trực tiếp, tránh lỗi chính tả làm hỏng bản dịch.
- Mở sẵn các cửa sổ: hội thoại A/B/C/D, mỗi cái hiện cả phía gửi và phía đọc, để khán giả nhìn thấy cả hai bên cùng lúc.
- Dựng toàn bộ hội thoại này **trước giờ diễn ít nhất vài chục phút** (không phải ngay sát giờ) — vừa để có thời gian xác minh ở Bước 5, vừa vì `honorific_profile` **ghi một lần, không ghi đè** (ADR-23): một khi đã đúng, nó không tự đổi nữa dù bạn gửi thêm tin.

---

## Timeline (2:00) — chỉ phần diễn trực tiếp, hội thoại đã dựng và xác minh sẵn từ trước

### 00:00–00:12 — Mở đầu
> "Hai lỗi dịch máy hay mắc nhất: xưng hô sai vai, và thuật ngữ công ty bị dịch bừa. LinguaFlow xử lý cả hai — dựa trên chính bối cảnh cuộc trò chuyện, không phải bảng từ điển cứng."

### 00:12–00:45 — Case 1 · Xưng hô trong 1-1 (đại từ theo đúng người, không dịch máy móc)

Mở hội thoại A (đã có sẵn 2 dòng lịch sử ở Bước 1).

| | |
|---|---|
| Gửi tiếp (User B) | `Anh xem qua rồi cho em xin ý kiến trước thứ Sáu nhé ạ` |
| User A thấy | `Please review it and send me your feedback before Friday` |

> "Anh/em ở đây không dịch máy móc thành brother/sister. Hệ thống biết ai đang nói với ai trong cuộc hội thoại này, nên anh thành *you*, em thành *me*."

Nguồn câu demo: `eval/golden_set.jsonl` — id `gs-001`, category `context_pronoun`.

### 00:45–01:25 — Case 2 · Xưng hô trong nhóm (một tin, hai bản dịch)

Mở hội thoại B (đã dựng và xác minh senior/junior ở Bước 2 + 5).

| | |
|---|---|
| U01 gửi tiếp | `Could you take a look when you have time?` |
| U02 (senior) thấy | `Khi nào anh rảnh xem giúp em với ạ` |
| U03 (junior) thấy | `Lúc nào rảnh em xem giúp anh nhé` |

> "Cùng một tin nhắn, gửi đúng một lần — nhưng hai người trong nhóm nhìn thấy hai bản dịch khác nhau, đúng vai của từng người. Không ai phải tự đổi cách xưng hô trong đầu."

Nguồn câu demo: `eval/golden_set.jsonl` — id `gs-056` / `gs-057`, category `honorific_recipient`. Cơ chế một tin nhắn tách thành nhiều bản dịch theo `(ngôn ngữ, vị thế)` được kiểm chứng tại `tests/test_services/test_bucket_fanout.py::test_two_standings_in_one_language_each_get_their_own_translation`.

*(Nếu còn thời gian / có câu hỏi sâu hơn: nhấn thêm rằng hệ thống còn tránh "mượn nhầm vai" — nếu lịch sử nhóm có một cặp anh/em là quan hệ giữa hai người khác, hệ thống không gán nhầm quan hệ đó cho người đang đọc. Case này nằm ở `gs-061`/`gs-062`, không đưa vào 2 phút chính để tránh dài dòng.)*

### 01:25–01:55 — Case 3 · Glossary theo đối tượng đọc

Mở song song hội thoại C (internal) và hội thoại D (client), mỗi cái đã dựng và thử trước ở Bước 3-5.

| | |
|---|---|
| Gửi vào **cả hai** hội thoại | `Please review the UI on staging before the deadline` |
| Hội thoại C (**nội bộ**) thấy | `Xem lại UI trên staging trước deadline nhé` |
| Hội thoại D (**khách hàng**) thấy | `Mong quý khách xem lại giao diện trên staging trước hạn chót` |

> "Cùng một từ, hai bản dịch — không phải vì hệ thống đoán ngẫu nhiên, mà vì nó biết đang nói chuyện với ai. UI và deadline giữ nguyên khi nói với dev — vì đó là cách team thật sự nói. Đổi thành giao diện, hạn chót khi có khách hàng."

Nguồn câu demo: `eval/golden_set.jsonl` — id `gs-054` (internal) / `gs-055` (client), category `glossary_audience`. Cơ chế tra cứu theo audience được kiểm chứng tại `tests/test_services/test_glossary.py::test_the_same_term_resolves_by_who_is_reading`, dữ liệu glossary thật tại `seed/glossary_en_vi.jsonl`.

### 01:55–02:00 — Chốt
> "Đây không phải demo dàn dựng riêng cho hôm nay — cơ chế xử lý cả ba case đều nằm trong bộ test chúng tôi chạy trước mỗi lần release."

---

## Ghi chú thành thật (để không hứa quá khi bị hỏi ngược)

- **1-1 không phải một cơ chế riêng cho xưng hô.** Nó là trường hợp nhóm có đúng một người đọc. Nếu bị hỏi "vậy 1-1 và nhóm khác nhau ở đâu", trả lời thẳng: *"Cùng một cơ chế — nhóm chỉ là nơi bạn nhìn thấy nó tạo ra nhiều bản dịch cùng lúc."*
- **Hồ sơ vị thế/đối tượng hiện chưa có màn hình sửa tay.** Case 2 và Case 3 chạy đúng vì đoạn hội thoại dựng sẵn đủ rõ để mô hình suy luận tự tin — không phải vì có ai chỉnh tay. Nếu mô hình đoán sai (ra `peer` thay vì `senior`/`junior`, hoặc đọc nhầm audience), hiện **không có cách sửa tay** — chỉ có thể gửi thêm bằng chứng rõ hơn và chờ lần suy luận kế tiếp (mỗi 20 tin), hoặc tạo hội thoại mới. Đây là hạng mục đã biết, ghi trong ADR-24.
- **Vị thế ghi một lần, không ghi đè** — nếu ở Bước 5 phát hiện suy luận sai, đừng cố "sửa" bằng cách gửi thêm tin trong cùng hội thoại đó; khả năng cao phải làm lại hội thoại mới, vì lần suy luận tiếp theo chỉ chạy sau 20 tin nữa.
- **Case 3 hiện chỉ có trong bối cảnh nhóm** ở golden set (`gs-054`/`gs-055` đều `chat_type: group`). Không có sẵn một cặp glossary được test riêng cho 1-1 so với nhóm.
- Toàn bộ cơ chế đứng sau 3 case đã được xác nhận **pass** trong lần chạy `pytest tests/ -k "glossary or audience or customize or terminology or honorific or bucket_fanout"` (92 passed) — không phải suy đoán. Riêng đoạn hội thoại dựng sẵn ở trên là tự viết theo đúng tiêu chí trong `INFER_CONVERSATION_PROFILE_PROMPT` (`src/agents/prompts.py`), chưa chạy thử bằng LLM thật trong lúc soạn tài liệu này — **bắt buộc rehearsal ít nhất 1 lần, xác minh bằng Bước 5, trước khi dùng cho demo thật.**
