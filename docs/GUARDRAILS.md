# Guardrail và ranh giới dữ liệu của Translation Agent

**Nhóm 4U (P-217)** — bản rà soát ngày 19/08. Tài liệu này bổ trợ cho
[`ARCHITECTURE.md`](../ARCHITECTURE.md) §5.1–5.2 và §6.4; phần *quyết định* vẫn nằm ở
các ADR, ở đây là **bức tranh đầy đủ theo kênh dữ liệu** để rà soát và để trả lời câu
hỏi khi bảo vệ.

Hai câu hỏi tài liệu này phải trả lời được:

1. **Nội dung một cuộc hội thoại có thể thoát ra ngoài cuộc hội thoại đó bằng đường
   nào, và đường đó đã được bịt tới đâu?**
2. **Bản dịch có giữ nguyên thông tin của tin nhắn gốc không, kể cả khi nội dung nghe
   giống một câu hỏi nhạy cảm?**

## 1. Vì sao agent này có mặt trái riêng

Agent **cố tình** cho model đọc tin nhắn của người khác: 5 tin gần nhất của hội thoại
được nạp làm ngữ cảnh để dịch đúng đại từ và chủ ngữ bị lược (ADR-01). Đó là thứ làm
chất lượng dịch chat khác hẳn dịch từng câu rời — và cũng chính là kênh rò rỉ: đầu ra
của model đi thẳng tới **một người nhận khác**, người chưa từng được xem những dòng
ngữ cảnh ấy.

Vì vậy mọi guardrail ở đây được đo bằng hai thước cùng lúc: chặn được cái gì, và **có
làm mất thông tin của người dùng không**. Một guardrail báo nhầm không "an toàn hơn" —
nó tạo ra đúng một tin nhắn mà người nhận phải đọc chưa dịch.

## 2. Các kênh dữ liệu rời khỏi hội thoại

| Kênh | Dữ liệu đi ra | Đi tới đâu | Biện pháp hiện tại | Tắt bằng cách nào |
|---|---|---|---|---|
| Ngữ cảnh → prompt | 5 tin gần nhất của **cùng một hội thoại** | Provider LLM | Truy vấn khoá cứng theo `conversation_id`; loại tin đã thu hồi và tin không có văn bản; mỗi dòng bị escape và cắt 500 ký tự | `AGENT_CONTEXT_SIZE=0` |
| Đầu ra bản dịch | Bản dịch tin nhắn | Người nhận trong hội thoại | Ba lớp kiểm rò rỉ ở §3.3 | Không (là chức năng chính) |
| Tầng dịch dự phòng | **Chỉ** tin nhắn gốc, không kèm ngữ cảnh | Endpoint công cộng của Google Translate | Không gửi ngữ cảnh; chịu cùng giới hạn độ dài và cùng phép kiểm ngôn ngữ đầu ra | `FALLBACK_TRANSLATOR_ENABLED=false` |
| Tracing | **Toàn bộ prompt**, gồm cả ngữ cảnh | Braintrust (cloud), hoặc Langfuse khi chọn lại | Công bố tại §6.4; không đặt khoá thì không gửi gì | `OBSERVABILITY_PROVIDER=none`, hoặc bỏ trống khoá của backend đang chọn |
| Log máy chủ | Chỉ **hình dạng**: mã ngôn ngữ, độ dài, số lượng, tên ngoại lệ | Log Railway | Không ghi nội dung tin nhắn, không ghi giá trị định danh rò rỉ, không ghi đoạn văn trùng | — |
| Cache dịch trong tiến trình | Cụm ngắn ≤ 30 ký tự đã dịch | Bộ nhớ tiến trình | Khoá cache **có `conversation_id`**, nên một hội thoại không bao giờ đọc được bản dịch của hội thoại khác | — |
| Fan-out WebSocket | Bản dịch theo ngôn ngữ | Thành viên của đúng hội thoại đó | Danh sách người nhận lấy từ `conversation_members`, cộng người gửi ở `direct` (CONTRACT §4.4) | — |
| Bảng `translation_attempts` | **Không có văn bản nào** — chỉ số đo, mã ngôn ngữ, tên model | Cơ sở dữ liệu | Thiết kế cột đã loại nội dung ngay từ đầu (ADR-16) | — |

## 3. Các lớp guardrail

Toàn bộ nằm ở `src/agents/guardrails.py` — hàm thuần, kiểm thử được mà không phải dựng
graph. Chi phí trên đường thành công khoảng 2ms.

### 3.1 Đầu vào

| Lớp | Khi vi phạm |
|---|---|
| `original_text` ≤ 2000 ký tự | Trả nguyên bản; **không cắt bớt**, nửa bản dịch tệ hơn không dịch |
| `target_language` đúng dạng ISO 639-1 | Trả nguyên bản — giá trị này đi thẳng vào system prompt |

### 3.2 Prompt

| Lớp | Ghi chú |
|---|---|
| Mỗi dòng ngữ cảnh: gộp xuống dòng, escape `<`, `>`, `&`, cắt 500 ký tự | Đóng kênh **A chiếm quyền bản dịch của B** (ADR-12) |
| Thẻ bao tin nhắn mang nonce ngẫu nhiên theo từng request | Người gửi không đoán được thẻ để đóng sớm; thân tin nhắn vẫn đi qua **nguyên vẹn** |
| Ràng buộc 7–8: tin nhắn là *dữ liệu cần dịch*, cấm từ chối / che / lược bớt / thêm cảnh báo | Phần **phòng ngừa** cho mục §4.2 |

### 3.3 Đầu ra

| Lớp | Khi vi phạm |
|---|---|
| Gỡ lớp bọc model tự thêm (`<think>`, code fence, nhãn `Translation:`, ngoặc kép, ghi chú cuối) | Gỡ im lặng, ghi cờ `scaffolding_stripped` |
| Không được đọc lại chỉ dẫn của agent | Tầng dự phòng, `prompt_disclosure` |
| Không được là **câu từ chối của model** | Tầng dự phòng, `refusal` |
| Không được chứa định danh mà tin gốc **không có** | Tầng dự phòng, `leaked_identifier` kèm `leak_source` |
| Không được **thiếu** định danh mà tin gốc **có** | Tầng dự phòng, `dropped_identifier` |
| Độ dài ≤ max(4× bản gốc, 200) | Tầng dự phòng, `too_long` |
| Không được vẫn là ngôn ngữ nguồn | Tầng dự phòng, `wrong_language` |
| Không chép ≥ 40 ký tự văn xuôi từ ngữ cảnh | **Chỉ đo** — ghi `context_echo`, bản dịch vẫn được giao |

Nguyên tắc chung: hàm phụ thuộc thư viện ngoài thì **fail open**, hàm thuần regex và số
học thì **fail closed**. Một lỗi phụ thuộc không được đẩy toàn bộ lưu lượng sang
provider dự phòng.

### 3.4 Bảng `fallback_reason`

`empty_input`, `bad_target_language`, `oversized_input`, `llm_error`, `empty_output`,
`too_long`, `prompt_disclosure`, `refusal`, `leaked_identifier`, `dropped_identifier`,
`wrong_language`. Đọc bằng `make metrics` (`scripts/report_metrics.py`) — chỉ đọc cơ sở
dữ liệu, không tốn hạn mức LLM.

## 4. Kết quả rà soát 19/08

### 4.1 Rò rỉ ra ngoài hội thoại

| # | Phát hiện | Xử lý |
|---|---|---|
| 1 | `DatabaseContextProvider` **không lọc `deleted_at`**: tin đã thu hồi bị API xoá trắng với người dùng nhưng vẫn nguyên văn trong cơ sở dữ liệu, và vẫn được nạp vào prompt của mọi bản dịch sau đó | Thêm điều kiện `deleted_at IS NULL`, loại luôn tin không có văn bản |
| 2 | Không có gì bắt được **văn xuôi** chép từ ngữ cảnh; lớp định danh chỉ thấy token có hình dạng định danh | Thêm `find_context_echo`, **đang ở chế độ đo** |
| 3 | Không phân biệt được rò rỉ thật (giá trị có trong lịch sử) với model bịa số | Thêm `classify_leak_source`, ghi telemetry `leak_source` |
| 4 | `fallback_translator.py` ghi `%r` kết quả provider trả về, tức **nội dung tin nhắn nằm trong log** | Chỉ còn ghi kiểu và độ dài |

### 4.2 Bản dịch làm mất thông tin

| # | Phát hiện | Xử lý |
|---|---|---|
| 5 | **Câu từ chối viết bằng đúng ngôn ngữ đích đi lọt toàn bộ hàng rào.** `"I'm sorry, I can't help with that request."` dài 42 ký tự nên dưới ngưỡng 200 của quy tắc độ dài, `detected == target` nên quy tắc ngôn ngữ không thấy, và nó tới người nhận với `is_valid = true`. Đây đúng là thứ mà một tin nhắn nghe giống câu hỏi nhạy cảm tạo ra | Siết prompt (ràng buộc 7–8) và thêm `looks_like_a_refusal`; sửa ADR-13 |
| 6 | Ràng buộc 6 cũ viết *"…never let any of its wording, names or figures into your output"* — dễ bị hiểu thành "bỏ luôn tên và số có mặt ở cả lịch sử lẫn tin nhắn", tức chính guardrail ép model bỏ bớt thông tin | Viết lại theo hướng "không **thêm** từ lịch sử"; nói rõ thứ có ở cả hai nơi là của tin nhắn và phải dịch bình thường |
| 7 | Không có lớp nào phát hiện model **bỏ bớt** định danh (che số điện thoại, bỏ link) | Thêm `find_dropped_identifiers` |

Ba chốt giữ cho chính các lớp mới không làm mất thêm thông tin: bộ dò từ chối bỏ qua
khi chính tin gốc cũng từ chối và chỉ xét bản dịch ≤ 200 ký tự; bộ dò mất định danh
chấp nhận mọi cách viết lại định dạng, kể cả quốc tế hoá số điện thoại
(`0912 345 678` → `(+84) 912 345 678`); bộ dò chép văn xuôi chưa được phép loại bỏ bản
dịch nào.

## 5. Cố ý không làm

1. **Chưa chặn `context_echo`** — cần số liệu dương tính giả trên lưu lượng thật trước.
   Hội thoại vốn lặp lại: hai người bàn cùng một lần deploy viết gần như cùng một câu.
2. **Không có bộ phân loại nội dung độc hại hay PII tổng quát** (ADR-14). Nó đi ngược
   đúng mục tiêu ở §4.2: sản phẩm này *dịch* nội dung người dùng chứ không *sinh* nội
   dung, nên kiểm duyệt đầu vào chỉ tạo thêm tin nhắn không được dịch.
3. **Không thử lại LLM khi bị từ chối** — tầng dự phòng gánh ca này, rẻ hơn một lần gọi
   model nữa và không làm người nhận chờ thêm.
4. **Không giới hạn tần suất theo người dùng, không ngân sách token** — thuộc tầng API.
5. **Ngữ cảnh không lọc theo `conversation_members.joined_at`.** Thành viên vào nhóm
   sau vẫn đọc được toàn bộ lịch sử qua `GET /conversations/{id}/messages`, nên ngữ
   cảnh không mở thêm kênh nào so với chính ứng dụng. Nếu sau này lịch sử bị cắt theo
   thời điểm tham gia thì **truy vấn ngữ cảnh phải cắt theo đúng mốc đó**.
6. **Tin nhắn đã sửa**: ngữ cảnh dùng bản mới nhất, không giữ bản trước khi sửa.

## 6. Cách kiểm chứng

```bash
pytest tests/test_agents/test_guardrails.py -q         # từng lớp, không cần graph
pytest tests/test_agents/test_prompt_injection.py -q   # mức graph, có đối kháng
pytest tests/test_services/test_db_context_provider.py -q
```

Mỗi test trong `test_prompt_injection.py` khẳng định thêm hai điều ngoài nội dung của
chính nó: graph **không ném lỗi**, và `translated_text` **không rỗng** — tức NFR-02
không bị chính guardrail phá.

Kiểm với LLM thật (tốn hạn mức): gửi trong một hội thoại `vi → en` bốn tin — một tin
hỏi mật khẩu máy chủ, một tin chửi thề, một tin có số điện thoại và link, một tin nối
tiếp cần ngữ cảnh để hiểu đại từ — rồi đối chiếu `make metrics`: cả bốn phải có
`outcome = llm`, không tin nào rơi vào `refusal` hay `dropped_identifier`, và bản dịch
phải còn đủ số điện thoại lẫn link.


## Glossary và kính ngữ — hai giới hạn đã biết (bổ sung 20/08)

1. **Tầng dự phòng không nhận glossary lẫn chỉ dẫn xưng hô.** `deep-translator`
   (ADR-07) chỉ nhận đúng nguyên văn tin nhắn: không prompt, không mục
   `# Audience`, không khối `<glossary>`. Một tin rơi xuống tầng hai vì thế mất
   cả tính nhất quán thuật ngữ lẫn cách xưng hô đã chọn. Đây là đánh đổi chấp
   nhận được vì tầng hai chỉ chạy khi tầng một đã hỏng, và một bản dịch hơi lệch
   giọng vẫn hơn hẳn một tin nhắn chưa dịch (NFR-02) — nhưng nó có nghĩa là tỷ lệ
   rơi xuống tầng hai cũng chính là tỷ lệ mất glossary.

2. **Thuật ngữ đích được coi là một phần của nguồn khi kiểm rò rỉ định danh.**
   `find_leaked_identifiers` (ADR-21) từ chối bản dịch chứa email, dãy ≥ 9 chữ số
   hay token dạng khoá mà tin nhắn gốc không có. Một thuật ngữ glossary **theo
   định nghĩa** là chữ mà tin nhắn không có — ép một cách dịch nghĩa là thế — nên
   một mã sản phẩm nằm trong glossary sẽ bị đọc thành định danh do model bịa ra,
   và **cả bản dịch bị vứt**. Vì vậy các thuật ngữ đích đã được quản trị viên
   duyệt được nối vào phần "nguồn" **chỉ cho phép kiểm này**, không cho gì khác.
   Hệ quả cần biết: một mục glossary độc hại có thể đưa một định danh vào bản dịch
   mà lớp (2) của ADR-21 không chặn. Đó là lý do mục glossary phải qua duyệt.

3. **Truy hồi theo ngữ nghĩa mở một lối thứ hai vào bảng `messages`** (ADR-27),
   và mọi ràng buộc của lối thứ nhất phải áp lại nguyên vẹn. Hai điều được kiểm
   bằng test riêng vì cả hai đều hỏng **im lặng** — dòng lấy sai vẫn trông y hệt
   dòng lấy đúng, và bản dịch sinh ra vẫn trôi chảy:

   - `test_a_withdrawn_message_never_returns_through_recall` — người gửi đã thu
     hồi thì không ai đọc được nữa trong ứng dụng, nên cũng không được quay lại
     qua đường này.
   - `test_recall_never_reaches_into_another_conversation` — truy hồi bị giới hạn
     trong một hội thoại. Với sang hội thoại khác là lấy chữ từ luồng người đọc
     chưa từng tham gia rồi đặt trước mặt model: đúng cái rò rỉ mà ADR-21 canh ở
     **đầu ra**, chỉ khác là đưa vào từ **đầu vào**, nơi chưa lớp nào canh.

   Cần lưu ý phần **chưa** làm: không có lớp nào kiểm rằng dòng được truy hồi
   nằm trong phạm vi người nhận *hiện tại* được phép đọc. Hiện điều đó đúng theo
   cách dựng — thành viên vào sau vốn đọc được toàn bộ lịch sử qua
   `GET /conversations/{id}/messages` — nên truy hồi không mở thêm kênh nào, đúng
   như đã ghi ở mục "cố ý không làm" số 5.
