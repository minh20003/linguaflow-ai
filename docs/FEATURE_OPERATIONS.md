# Hướng dẫn vận hành các chức năng hiện có

Tài liệu này mô tả **hành vi đang được hiện thực trong mã nguồn**. Nó bổ sung cho
[`CONTRACT.md`](CONTRACT.md), nơi quy định chính xác request/response và schema.
Không coi phần mô tả ở đây là cam kết cho tính năng chưa được triển khai; đặc biệt,
**Google Meet thật chưa được tạo**.

## 1. Gọi thoại và video trực tiếp

### Phạm vi và nhà cung cấp

Hệ thống chỉ hỗ trợ cuộc gọi `voice` và `video` giữa đúng hai thành viên của hội
thoại `direct`. Nhà cung cấp hiện tại là **Daily**. Backend tạo phòng Daily riêng tư,
rồi phát token tham gia ngắn hạn cho từng người; API key Daily không được gửi cho
frontend, lưu trong message hay phát qua WebSocket.

| Biến cấu hình | Ý nghĩa | Mặc định |
|---|---|---|
| `RTC_PROVIDER` | `daily` hoặc `disabled` | `daily` |
| `DAILY_API_KEY` | API key phía server của Daily | rỗng |
| `DAILY_API_BASE` | Daily REST API base URL | `https://api.daily.co/v1` |
| `CALL_RING_TIMEOUT_SECONDS` | Hết thời gian đổ chuông thành `missed` | `45` |
| `CALL_TOKEN_TTL_SECONDS` | Hạn token/phòng tạm | `3600` |

TURN/STUN, kết nối ICE và quyền media do Daily SDK/browser xử lý. LinguaFlow không
có cấu hình TURN/STUN riêng; nếu mạng doanh nghiệp chặn WebRTC, phải chẩn đoán trong
Daily và trên chính sách mạng, không thêm secret TURN vào frontend.

### Vòng đời và trạng thái

1. Người gọi tạo `POST /conversations/{conversation_id}/calls` với `call_type`.
   Backend kiểm tra thành viên, block list và bảo đảm cả hai không đang ở cuộc gọi
   `ringing` hoặc `accepted`; sau đó tạo phòng và phiên `ringing`.
2. Người nhận nhận WebSocket `call_incoming`, rồi chọn `POST /calls/{id}/accept`
   hoặc `/reject`.
3. `accept` chuyển phiên sang `accepted`, cấp token cho người nhận và phát
   `call_accepted`. Người gọi lấy token riêng qua `GET /calls/{id}/join`.
4. Một trong hai phía gọi `POST /calls/{id}/end`; phía còn lại nhận `call_ended`.
   Phòng Daily được đóng theo best effort. Cuộc gọi bị quá hạn đổ chuông thành
   `missed`; lỗi cấp token/phòng thành `failed`.

WebSocket chỉ mang trạng thái công khai (`call_incoming`, `call_accepted`,
`call_rejected`, `call_ended`, `call_failed`) — không bao giờ mang token hoặc API key.
Mọi thao tác không thuộc người tham gia, sai trạng thái, hội thoại nhóm, blocked hoặc
đang bận đều phải hiển thị lỗi từ API thay vì tự chuyển UI sang “đã kết thúc”.

### Quyền trình duyệt và kiểm thử

Frontend chỉ yêu cầu microphone khi gọi thoại và microphone + camera khi gọi video.
Từ chối quyền là lỗi cục bộ của thiết bị, không phải lý do gọi API `end` ngay; UI cần
cho phép thử lại sau khi người dùng mở quyền trong browser/OS. Kiểm thử tối thiểu:

- Hai tài khoản mở cùng hội thoại direct: gọi, chấp nhận, hai token khác nhau, kết thúc.
- Từ chối; hết `CALL_RING_TIMEOUT_SECONDS`; người nhận hoặc người gọi đang bận.
- `RTC_PROVIDER=disabled` và `DAILY_API_KEY` rỗng trả lỗi provider an toàn, không lộ secret.
- Tắt mic/camera, từ chối permission và refresh trang trong lúc gọi: UI không được báo sai
  là đã có media; backend vẫn có thể đóng phiên bằng endpoint hợp lệ.

## 2. Liên kết và đồng bộ Google Calendar

### Điều kiện bật tính năng

Calendar OAuth chỉ khả dụng khi có đủ `GOOGLE_OAUTH_CLIENT_ID`,
`GOOGLE_OAUTH_CLIENT_SECRET`, `GOOGLE_OAUTH_REDIRECT_URI` và
`TOKEN_ENCRYPTION_KEY`. Redirect URI phải khớp tuyệt đối cấu hình OAuth Web Client
trên Google Cloud Console. Mã hóa token dùng Fernet; thiếu khóa mã hóa làm endpoint
liên kết trả `503`, thay vì lưu refresh token dạng rõ.

Scope Google duy nhất là `https://www.googleapis.com/auth/calendar.events`: đủ đọc
và ghi event, không xin quyền quản trị calendar. Ở tầng ứng dụng, người dùng còn phải
cấp `calendar_read` để liên kết/đồng bộ và `calendar_write` để event nội bộ đã duyệt
được đẩy lên Google.

### Luồng OAuth và token

1. Client gọi `GET /me/calendar/google/authorize` sau khi có `calendar_read`.
   API trả URL consent cùng `state` đã ký, hạn 10 phút.
2. Sau consent, client đưa `code` và `state` vào
   `POST /me/calendar/google/callback`. Server xác thực chữ ký **và** tài khoản sở
   hữu state, rồi đổi code lấy access token + refresh token.
3. Google phải trả refresh token. URL consent luôn dùng `access_type=offline` và
   `prompt=consent`; thiếu refresh token bị coi là lỗi, vì liên kết chỉ sống một giờ
   là trạng thái sai.
4. Access token được làm mới trước hạn hai phút. `DELETE /me/calendar/google/link`
   xóa token đã mã hóa nhưng không xóa event thật trên Google; thao tác này idempotent.

### Đồng bộ, lỗi và khôi phục

Đẩy event nội bộ là background best effort. Chiều kéo từ Google là polling, mặc định
mỗi 300 giây qua `CALENDAR_SYNC_INTERVAL_SECONDS` (60–3600). `POST /me/calendar/sync`
chạy ngay một chu kỳ để UI không phải chờ. Google event kéo về có `source=google`,
`sync_state=remote_only`, chỉ đọc trong LinguaFlow.

`google_etag` chống vòng lặp: thay đổi do LinguaFlow vừa đẩy lên quay lại từ Google với
etag giống nhau sẽ không bị đánh dấu để đẩy lần nữa. `sync_token` cho phép kéo incremental;
khi Google trả `410 Gone`, server bỏ cursor cũ và chạy full sync. `last_sync_error` được
giữ trong calendar link và trả ở kết quả sync — phải hiển thị/ghi log nó, không im lặng
retry vô hạn.

Runbook: kiểm tra status liên kết, gọi sync thủ công, đọc `last_sync_error`, kiểm tra
redirect URI/secret/khóa Fernet, sau đó unlink và liên kết lại nếu refresh token đã bị
Google thu hồi. Không tự xóa event local để “sửa” lỗi token.

## 3. Ngôn ngữ hiển thị và bản dịch tin nhắn

`preferred_language` là ngôn ngữ người dùng muốn đọc **nội dung tin nhắn đã dịch**;
`interface_language` là ngôn ngữ của **nhãn, nút, trạng thái và trợ giúp hệ thống**.
Hai giá trị độc lập. Nội dung do người dùng gửi không được dịch chỉ vì đổi ngôn ngữ UI;
nó đi theo cơ chế dịch tin nhắn của người nhận.

Frontend dùng `frontend/src/features/chat/i18n.ts` làm điểm tập trung cho nhãn hệ thống.
Mọi thành phần nhận `interfaceLanguage` từ `AppShell`; không được tự suy ra từ browser,
`preferredLanguage` hay nhúng chuỗi UI cố định. Quy tắc khi thêm UI mới:

1. Thêm khóa tiếng Anh chuẩn vào dictionary; bổ sung bản dịch cho các ngôn ngữ hỗ trợ.
2. Dùng helper `tx(language, key)`/helper chuyên biệt thay vì string literal trong JSX.
3. Fallback là tiếng Anh nếu một bản dịch chưa tồn tại; không fallback sang nội dung tin nhắn.
4. Định dạng ngày/giờ/số dùng locale `interfaceLanguage`, nhưng timestamp API vẫn UTC/ISO.
5. Tên hệ thống như trợ lý cũng lấy từ dictionary; tên người dùng/nhóm và text tin nhắn giữ nguyên.

Checklist hồi quy: đổi interface language trong Settings, refresh trang, kiểm tra Chat,
Calendar, Task Inbox, popup đính kèm/mention/scan lịch, modal, empty/error/toast state
và trang auth. Một chuỗi tiếng Việt/Anh hard-code trong UI là lỗi coverage; ngoại lệ chỉ
là content người dùng hoặc tên dữ liệu bên ngoài.

## 4. Consent của trợ lý và ranh giới dữ liệu

Mọi scope mặc định `false`; membership hội thoại không thay thế consent. API
`GET`/`PUT /auth/me/agent-consents` luôn trả đủ vocabulary, còn cập nhật là partial.

| Scope | Đọc/ghi được phép | Khi thu hồi |
|---|---|---|
| `read_conversations` | Đọc nội dung để `@assistant`, tóm tắt, trích đề xuất | Lần gọi tiếp theo bị chặn; dữ liệu lịch sử không tự xóa |
| `proactive_scan` | Quét tin mới để phát hiện cam kết | Cần đồng thời `read_conversations`; dừng quét về sau |
| `store_memory` | Ghi memory và chunk truy hồi từ tin công khai | Dừng ghi mới; row đã có không tự xóa |
| `calendar_read` | Liên kết và kéo Google Calendar | Liên kết/sync endpoint bị chặn |
| `calendar_write` | Đẩy event đã duyệt lên Google | Event vẫn tồn tại nội bộ, không được đẩy ra ngoài |

Thu hồi chỉ chuyển `is_granted=false` và ghi `revoked_at`, không xóa audit row. Consent
có `policy_version`; khi policy tăng phiên bản, UI phải yêu cầu chấp thuận lại thay vì coi
đồng ý cũ bao phủ scope mới. `ai_smart_assistance` là công tắc hiển thị, không phải consent.

Ca kiểm thử bắt buộc: từng scope một; `proactive_scan` không có `read_conversations`;
thu hồi giữa hai lần gọi; account khác thử dùng resource/consent id; thay đổi policy version;
và xác nhận API trả `403 CONSENT_REQUIRED` chỉ nêu scope thiếu, không trả nội dung chat.

## 5. Assistant retrieval và memory

### Index và truy hồi

`assistant_chunks` chỉ index message `public`; private message không được đưa vào chunk
dùng chung. Khóa logic là `(conversation_id, strategy, embedding_model)`. Rebuild thay thế
trọn vẹn trong một transaction, nên lỗi giữa chừng giữ index cũ thay vì index nửa chừng.

Indexer chạy incremental sau mỗi 20 tin mới để tránh embedding trên message path. Incremental
có thể tạo “seam” tại ranh giới cửa sổ; full rebuild định kỳ qua
`scripts/backfill_assistant_chunks.py` xử lý điều đó. Có thể dùng nhiều strategy song song;
không trộn vector khác embedding model, vì thứ hạng giữa các không gian vector vô nghĩa.

Retrieval luôn giới hạn một `conversation_id`, lấy tối đa cấu hình
`ASSISTANT_RETRIEVAL_TOP_K` (mặc định 8 candidates) rồi `ASSISTANT_RERANK_TOP_N` (mặc định 4).
Lỗi embedding, rerank, query rỗng hoặc index chưa có không làm request trợ lý lỗi: đường đọc
trả ít/không chunk và agent quay về recent-message window. Đây là graceful degradation, không
phải tín hiệu rằng có thể bỏ qua consent.

### Memory dài hạn và giám sát

`assistant_user_memory` tách khỏi chunks: lưu preference/fact/relationship/recurring, được
gắn nguồn khi có thể và thay thế bằng `superseded_by` thay vì ghi đè. Chỉ `store_memory`
cho phép ghi. Theo dõi `assistant_attempts.memory_recalled` và `memory_lines`: nếu
`memory_recalled=0` liên tục, cần kiểm tra index/backfill, provider embedding và consent,
không kết luận người dùng “không có dữ liệu”.

Khi đổi embedding provider/model: tạo/rebuild index cho model mới, xác nhận truy vấn lọc
đúng `embedding_model`, theo dõi chi phí/latency và chỉ xóa model cũ sau khi không còn đường
đọc nào dùng nó.

## 6. Nhắc hẹn và thông báo

APScheduler chỉ là đồng hồ; PostgreSQL `reminders` mới là hàng đợi nguồn sự thật.
`scan_due_reminders` claim bằng conditional update, ghi `delivered_at` trước khi gửi để hai
lượt quét không phát trùng. Lịch quét theo `REMINDER_SCAN_INTERVAL_SECONDS` (mặc định 60;
10–3600) và có thể tắt bằng `REMINDER_SCHEDULER_ENABLED=false` cho test/worker ngoài.

Khi đến hạn, server phát WebSocket `reminder_due` nếu socket đang mở **và** tạo notice bền
trong hội thoại trợ lý. Vì vậy offline không mất hoàn toàn lịch sử thông báo, nhưng realtime
toast không được đảm bảo delivery. Lỗi gửi socket/message chỉ log warning; row vẫn được claim
để tránh bắn lặp mỗi phút. Một reminder có thể dismiss qua API; cancel event vô hiệu các
reminder chưa gửi. `reminder_minutes_before` vắng mặt là 15, `null` là không nhắc, còn mốc
nhắc đã ở quá khứ thì không tạo reminder.

Vận hành: kiểm tra `reminder_scheduler_running` tại `/health/system`, `delivered_at`/
`dismissed_at`, timezone của event và log lỗi. Sau restart, scan kế tiếp claim mọi row còn
đến hạn; không cần APScheduler job store. Kiểm thử event quá khứ, `null`, dismiss, cancel,
offline socket, restart giả lập và hai scan chồng nhau.

## 7. Tương tác tin nhắn và quyền riêng tư

| Chức năng | Hành vi | Biên giới quyền riêng tư |
|---|---|---|
| Search | Tìm original text hoặc bản dịch mà **người gọi** có quyền đọc; cursor theo `before_created_at` + `before_id` | Không trả message đã gỡ hoặc bản dịch/honorific của thành viên khác |
| Saved messages | Bookmark cá nhân qua `PUT`/`DELETE .../saved` | `is_saved` thuộc người gọi, không broadcast |
| Reactions | Một emoji duy nhất mỗi người trên một message; server tổng hợp và phát `message_reactions_updated` | Chỉ thành viên hội thoại được tương tác |
| Forward | Forward tạo message mới cho hội thoại đích, được dịch lại cho người nhận mới | Không copy quyền xem/private visibility của message nguồn sang người không được phép |
| Attachment/voice | Download yêu cầu xác thực và membership; voice transcript chỉ tham gia search/context khi completed | File/audio không public URL; retry transcription chỉ cho voice failed hợp lệ |

Kiểm thử E2E phải bao gồm hai người có preferred language khác nhau, tin private trong nhóm,
message bị gỡ, reaction đồng thời, save chỉ hiện với chủ sở hữu, forward sang nhóm khác và
download attachment bằng account không phải thành viên (404/không lộ tồn tại).

## 8. Admin và observability

`GET /health/system` là admin-only và không trả text chat, token hay dữ liệu định danh nhạy
cảm. Nó trả uptime, online users/total sockets, background tasks, translation cache,
DB pool, circuit breaker, memory RSS, scheduler và rate-limit status.

| Dấu hiệu | Cách diễn giải | Hành động đầu tiên |
|---|---|---|
| Breaker `open` | Provider ngoài có lỗi liên tiếp; request đi fallback | Xem log/provider quota; không restart liên tục để ép request qua breaker |
| Cache hit rate tụt mạnh | Thay đổi traffic, glossary/model hoặc cache restart | So sánh release và cache size; không coi đó là lỗi một mình |
| `checked_out` DB pool cao kéo dài | Có request/transaction chậm hoặc leak | Kiểm tra DB latency, route đang chạy và pool status |
| Scheduler không running | Không có delivery reminder định kỳ | Kiểm tra config/dependency/process state trước khi bật lại |
| Background tasks tăng mãi | Worker không kết thúc hoặc provider chậm | Kiểm tra task/log timeout, không chỉ tăng giới hạn |
| `last_sync_error` có giá trị | Đồng bộ Google chưa lành mạnh | Chạy sync thủ công, kiểm tra OAuth/token, sau đó relink nếu cần |

Ngưỡng cảnh báo cụ thể phụ thuộc hạ tầng và baseline production; đặt baseline trước rồi cảnh
báo theo xu hướng. Không suy luận “hệ thống khỏe” chỉ từ `/health`: endpoint đó không thay thế
synthetic checks cho login, WebSocket, LLM, Daily hoặc Google Calendar.

## Liên kết liên quan

- [`CONTRACT.md`](CONTRACT.md): API, event WebSocket, schema và các mã lỗi chuẩn.
- [`RUNTIME_RELIABILITY.md`](RUNTIME_RELIABILITY.md): rate limit, nén, cache, health và circuit breaker.
- [`DEPLOY.md`](DEPLOY.md): biến môi trường, triển khai và troubleshooting nền tảng.
- [`NewFeature.md`](NewFeature.md): thiết kế trợ lý, đề xuất, calendar và giới hạn Google Meet.
