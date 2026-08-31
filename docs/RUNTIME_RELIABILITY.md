# Vận hành độ tin cậy runtime

Tài liệu này là chuẩn vận hành cho độ tin cậy runtime của LinguaFlow. Nó tập trung vào
hành vi khi hệ thống đang chạy, các giới hạn hiện tại, tín hiệu quan sát được và cách
chẩn đoán. Đặc tả API vẫn thuộc về [`CONTRACT.md`](CONTRACT.md); cấu hình và thao tác triển khai
thuộc về [`DEPLOY.md`](DEPLOY.md).

## 1. Rate limiting

Rate limit dùng SlowAPI với in-memory store (`src/core/rate_limit.py`). Đây là thiết kế single-process; không chia sẻ bộ đếm giữa nhiều instance.

| Phạm vi | Khoá | Giới hạn | Mục đích |
|---|---|---:|---|
| Đăng nhập/đăng ký | IP | 5 yêu cầu/phút | Chống brute-force |
| REST đã xác thực | `user_id` JWT | 60 yêu cầu/phút | Bảo vệ API chung |
| Luồng phụ thuộc LLM | `user_id` JWT | 20 yêu cầu/phút | Bảo vệ hạn mức provider |

Khi vượt ngưỡng, HTTP trả `429 Too Many Requests` cùng `Retry-After`; client không tự retry dồn dập mà đợi hết thời gian này. WebSocket kiểm tra bộ đếm trước khi chạy tác vụ tốn LLM, nên một người dùng không thể làm cạn quota provider của cả hệ thống.

Bộ đếm mất khi process restart và không chia sẻ giữa worker. Điều đó phù hợp môi trường single-process hiện tại, nhưng **không** phải cơ chế chống lạm dụng phân tán. Khi scale ngang, phải thay store bằng Redis và xác nhận key theo `user_id` vẫn được áp dụng sau JWT authentication; không chuyển rate limit đã xác thực sang IP vì nhiều người dùng hợp lệ có thể chung mạng.

## 2. Nén phản hồi

`GZipMiddleware` được bật tại `src/main.py` với `minimum_size=500`. Middleware chỉ nén khi client gửi `Accept-Encoding: gzip` và body đủ lớn; phản hồi nhỏ không bị nén để tránh chi phí CPU lớn hơn lợi ích băng thông.

Các response được hưởng lợi rõ nhất là lịch sử chat, danh sách hội thoại, trang kết quả tìm kiếm và thống kê admin. Nén không thay thế pagination: một response JSON rất lớn vẫn phải được phân trang. Có thể xác nhận bằng `Content-Encoding: gzip`; không suy luận từ `Content-Length` vì framework/client có thể tự giải nén trước khi hiển thị.

## 3. Phân trang lịch sử chat

Endpoint lịch sử hỗ trợ cursor composite `(created_at, id)` qua query `before`, trả `next_cursor` trong page envelope. Cursor là opaque và phải được client chuyển nguyên trạng; không tự giải mã hay chỉnh sửa ở frontend.

Khi `before` xuất hiện (hoặc `paginated=true`), response có dạng `{items, has_more, next_cursor}`. `next_cursor` trỏ tới trang cũ hơn và được sinh từ tin nhắn cũ nhất của trang hiện tại. Cursor có cả `created_at` và `id`, do đó vẫn ổn định khi nhiều tin nhắn cùng timestamp.

Offset cũ vẫn giữ cho tương thích ngược. Client mới phải ưu tiên cursor để tránh chi phí `OFFSET` tăng dần trên hội thoại dài. Không được trộn offset và cursor trong cùng một request. Cursor sai định dạng, không hợp lệ hoặc vượt quyền hội thoại phải được server từ chối; client cần dừng phân trang khi `has_more=false` hoặc `next_cursor=null`.

## 4. Translation cache L2

Cache dịch in-memory có TTL 30 phút, tối đa 500 phần tử và chỉ lưu câu ngắn (tối đa 60 ký tự). Key chứa dữ liệu cần thiết để không trả bản dịch sai ngôn ngữ đích. Một hit chỉ tái sử dụng kết quả đã có; không bỏ qua persistence, quyền truy cập hoặc pipeline hiển thị của message.

Cache bị bỏ qua khi dữ liệu không phù hợp hoặc khi TTL hết hạn; đây là chủ ý để glossary/model mới không bị che bởi kết quả cũ. Cache không bền qua restart và không chia sẻ giữa instance, vì vậy không được dùng hit rate làm chỉ số trực tiếp cho chất lượng dịch hoặc chi phí toàn cụm.

Metric `hit`, `miss`, `size` được xuất qua system health. Không coi cache hit rate thấp đơn lẻ là lỗi: cần đối chiếu tỷ lệ câu đủ điều kiện cache và thay đổi glossary/model.

## 5. System health

`GET /api/v1/health/system` chỉ dành cho admin. Endpoint tổng hợp trạng thái runtime, không trả nội dung hội thoại, token hoặc dữ liệu định danh của người dùng.

| Metric | Ý nghĩa vận hành |
|---|---|
| WebSocket connections | Số socket/user đang kết nối trong process hiện tại |
| Background tasks | Tác vụ dịch nền đang được giữ tham chiếu |
| Translation cache | Kích thước, hit, miss và hit rate của cache process-local |
| DB pool | Trạng thái pool để phát hiện cạn kết nối hoặc overflow |
| Uptime / memory | Phân biệt restart, rò rỉ hoặc áp lực bộ nhớ |
| Reminder scheduler | Trạng thái scheduler của nhắc hẹn |
| Circuit breakers | Trạng thái provider ngoài và số lần trip |

Checklist khi có cảnh báo:

1. Kiểm tra `uptime_seconds` để phân biệt restart với lỗi tích luỹ.
2. Kiểm tra DB pool trước khi tăng worker hoặc timeout.
3. Kiểm tra background task/circuit breaker trước khi kết luận LLM chậm.
4. Không ghi log response health chứa token, nội dung tin nhắn hay dữ liệu theo người dùng.

## 6. Circuit breaker và graceful degradation

Circuit breaker tại `src/core/circuit_breaker.py` bảo vệ LLM, embedding, embedding fallback và fallback translator. Cấu hình mặc định: đóng bình thường, mở sau 5 lỗi liên tiếp, thử lại half-open sau 60 giây.

| Trạng thái | Hành vi |
|---|---|
| Closed | Gọi provider bình thường; lỗi liên tiếp được đếm |
| Open | Không gọi provider, đi thẳng fallback để tránh timeout dây chuyền |
| Half-open | Chỉ một probe được phép gọi lại sau cooldown |

Một probe half-open thành công đóng circuit và xoá chuỗi lỗi; thất bại mở lại cooldown. Circuit breaker không thay thế fallback: fallback phải vẫn có giới hạn lỗi riêng và không được tạo vòng gọi quay lại provider đang mở. Khi circuit mở kéo dài, kiểm tra credentials, quota và trạng thái provider trước; xoá cache không khắc phục lỗi provider.

## 7. Mục tiêu dịch vụ và tín hiệu cảnh báo

LinguaFlow chưa có SLO/SLA đã ký với khách hàng trong mã nguồn. Vì vậy các số ở đây là
**baseline vận hành cần đo trước**, không phải ngưỡng đã được hệ thống tự động áp đặt.
Mỗi môi trường production phải ghi nhận baseline sau một giai đoạn traffic ổn định, rồi
đặt cảnh báo theo xu hướng và dung lượng thực tế của hạ tầng.

| Bề mặt | SLI cần theo dõi | Dấu hiệu suy giảm | Nguồn hiện có |
|---|---|---|---|
| REST | Tỷ lệ 2xx/4xx/5xx, p50/p95/p99 latency | 5xx tăng, latency tăng liên tục | Access log/proxy + tracing |
| WebSocket | Auth thành công, socket online, disconnect bất thường | online users/sockets lệch hoặc reconnect tăng | `health/system`, app log |
| Dịch/LLM | latency, fallback rate, breaker state | breaker open, fallback tăng, timeout | tracing + `health/system` |
| Database | pool checked-out, overflow, latency query | pool gần cạn, request treo | `health/system` + PostgreSQL metrics |
| Reminder | scheduler running, reminder đến hạn chưa xử lý | scheduler dừng hoặc due rows tăng | `health/system` + DB query |
| Calendar | `last_sync_error`, thời gian sync thành công gần nhất | lỗi OAuth/Google kéo dài | Calendar link + app log |

Không dùng một con số đơn lẻ để kết luận có incident. Ví dụ cache hit rate giảm sau restart
là bình thường; breaker mở mới là tín hiệu provider có vấn đề, nhưng có thể vẫn là graceful
degradation chứ không phải backend down. Cảnh báo nên tách ít nhất ba mức: **cảnh báo sớm**
(xu hướng xấu), **suy giảm dịch vụ** (người dùng bắt đầu thấy fallback/lỗi), và **mất dịch vụ**
(login, WebSocket hoặc database không dùng được).

## 8. Phụ thuộc bên ngoài và chiến lược suy giảm

| Phụ thuộc | Failure mode chính | Hành vi hiện tại | Việc cần xác minh khi lỗi |
|---|---|---|---|
| LLM/embedding | quota, timeout, 5xx | circuit breaker; dịch/retrieval đi fallback phù hợp | API key, quota, provider status, breaker |
| Fallback translator | timeout/response lỗi | breaker riêng; cuối cùng giữ đường fallback an toàn | network/provider, timeout cấu hình |
| PostgreSQL | hết kết nối, chậm, unavailable | request phụ thuộc DB thất bại; không có in-memory substitute | pool, DB health, lock, dung lượng |
| Google Calendar | token revoked, OAuth lỗi, `410 Gone`, API lỗi | lưu `last_sync_error`; full sync lại khi token incremental hết hạn | redirect URI, token, scope, Google status |
| Daily RTC | room/token API lỗi | call chuyển lỗi an toàn, token/provider key không lộ | `DAILY_API_KEY`, Daily status, browser media/network |
| SMTP | xác thực/kết nối lỗi | production fail-fast cấu hình; gửi lỗi không silent-drop | credential, TLS/port, provider log |
| Attachment/STT | storage hay transcription provider lỗi | attachment bền; transcription có retry có giới hạn | storage credential, quota, retry status |

Timeout và retry không được nhân bản qua nhiều tầng mà không có budget chung: retry của
client, proxy và backend cùng một lỗi có thể biến một outage nhỏ thành tải đột biến. Với
provider không idempotent, chỉ retry khi operation có idempotency key hoặc backend chứng minh
được thao tác không tạo dữ liệu trùng. Không log access token, refresh token, Daily API key,
payload chat hoặc file attachment khi chẩn đoán phụ thuộc ngoài.

## 9. Ranh giới scale ngang và trạng thái in-memory

Hiện tại backend được thiết kế single-process. Các trạng thái sau là process-local:

| Thành phần | Điều mất đi khi restart | Rủi ro khi chạy nhiều instance |
|---|---|---|
| SlowAPI rate limit | Bộ đếm cửa sổ hiện tại | Mỗi instance có quota riêng, dễ vượt tổng quota |
| Translation cache | Cache L2 và hit/miss counter | Cache miss tăng, metric không đại diện toàn cụm |
| Circuit breaker | Chuỗi lỗi và cooldown | Một instance tiếp tục gọi provider hỏng |
| ConnectionManager | Danh sách socket | Broadcast/realtime chỉ tới socket cùng process |
| Background task references | Theo dõi task đang chạy | Health không thấy task của instance khác |
| APScheduler | Đồng hồ poll cục bộ | Nhiều scheduler có thể cùng quét, dù claim DB vẫn chặn reminder trùng |

Không scale số worker/replica chỉ bằng thay đổi cấu hình. Trước khi chạy nhiều instance cần:

1. Chuyển rate-limit/cache/breaker sang store phân tán phù hợp, có TTL và namespace rõ ràng.
2. Dùng message broker/pub-sub cho WebSocket fan-out hoặc sticky-session với giới hạn được chấp nhận.
3. Chọn một scheduler leader hoặc lock phân tán cho calendar polling; reminder vẫn phải giữ
   claim condition ở PostgreSQL làm hàng rào cuối.
4. Tổng hợp metric theo instance và theo toàn cụm; không lấy `/health/system` của một pod
   để tuyên bố toàn hệ thống khỏe.
5. Load test và failure test lại sau khi thay topology, đặc biệt flow reconnect và idempotency.

## 10. Độ bền dữ liệu, sao lưu và khôi phục

PostgreSQL là nguồn sự thật cho user, hội thoại, message, đề xuất, event, reminder,
consent và link Calendar. Cache, breaker, socket list, scheduler state và background-task
set không phải dữ liệu khôi phục. Attachment storage là dữ liệu bền riêng và cần có chính
sách backup/retention tương ứng với nhà cung cấp storage.

Release production tạo logical PostgreSQL backup trước migration theo [`DEPLOY.md`](DEPLOY.md). Một release
thất bại **không** tự restore hay rollback database; tự động làm vậy có thể ghi đè dữ liệu đã
được tạo giữa lúc deploy. Khôi phục là thao tác có chủ đích của người vận hành:

1. Dừng ghi hoặc đưa dịch vụ vào maintenance để tránh dữ liệu mới xuất hiện giữa các bước.
2. Xác định commit/image, migration và thời điểm backup đúng; kiểm tra integrity backup trong
   môi trường tách biệt trước khi chạm production.
3. Khôi phục database/attachment theo runbook hạ tầng, rồi chạy migration phù hợp và xác minh
   login, REST, WebSocket, reminder, calendar link và attachment authorization.
4. Ghi nhận khoảng dữ liệu có thể mất và kiểm tra token Calendar sau restore; không in token ra log.

Chi tiết câu lệnh backup/release nằm tại [`DEPLOY.md`](DEPLOY.md); tài liệu này không sao chép lệnh
vì lệnh khôi phục phụ thuộc vào VPS, provider storage và cửa sổ dữ liệu được phép mất.

## 11. Kiểm thử hiệu năng, lỗi và khôi phục

Trước mỗi mốc production hoặc thay đổi provider/topology, thực hiện tối thiểu các kịch bản:

| Nhóm | Kịch bản | Tiêu chí quan sát |
|---|---|---|
| Pagination | Hội thoại lớn, tải trang cũ bằng cursor liên tiếp | Không dùng offset mới; không trùng/mất item tại ranh timestamp |
| Rate limit | Burst login, REST, request LLM của cùng user | 429 + `Retry-After`; user khác không bị chặn nhầm |
| Provider outage | Giả lập timeout/5xx LLM, embedding, fallback | breaker mở đúng; latency giảm sau khi mở; UI có fallback an toàn |
| Database pressure | Pool gần cạn hoặc query chậm có kiểm soát | health phản ánh pool; không tạo retry storm |
| Restart | Restart khi reminder đã đến hạn và socket đang kết nối | reminder catch-up một lần; client reconnect theo contract |
| Calendar | Token expired, `410 Gone`, event Google sửa ngoài | `last_sync_error`/full sync đúng; không loop theo etag |
| Security | Request sai JWT/quyền/consent, download attachment ngoài hội thoại | Không lộ existence/content/token |

Load test phải chạy trên môi trường cô lập với provider sandbox/mock khi có thể. Không bắn
traffic benchmark trực tiếp vào quota LLM, Google Calendar hoặc Daily production. Kết quả cần
ghi lại concurrency, payload, database size, phiên bản image và các p50/p95/p99 quan sát được;
không có các thông số đó thì hai lần benchmark không thể so sánh.

## 12. Runbook phản ứng sự cố

1. **Xác định phạm vi:** REST, WebSocket, translation, calendar, reminder, RTC hay một account.
   Đừng restart ngay; lấy timestamp, request/correlation id an toàn và trạng thái health trước.
2. **Kiểm tra dependency:** DB pool, breaker, scheduler, provider status, quota và release gần nhất.
3. **Giảm tác động:** để breaker/fallback hoạt động; tắt scheduler bằng cấu hình chỉ khi cần chặn
   gửi reminder; không xóa queue, cache hay Calendar link để “làm sạch” khi chưa hiểu nguyên nhân.
4. **Khôi phục có kiểm chứng:** gọi health, kiểm thử login + WebSocket + một flow phụ thuộc bị lỗi,
   rồi theo dõi metric sau recovery. Với Calendar, xác nhận sync thủ công và `last_sync_error`.
5. **Ghi nhận:** timeline, phạm vi account bị ảnh hưởng, dữ liệu có thể mất/trễ, nguyên nhân và
   hành động ngăn lặp lại. Không đưa nội dung hội thoại, token hay secrets vào bản ghi sự cố.

`/health` chứng minh process sống; `/health/system` cho biết trạng thái runtime của instance.
Cả hai không thay thế synthetic check từ bên ngoài, kiểm tra backup restore định kỳ, hoặc một
cuộc gọi media/Google OAuth thật trong môi trường staging.

## Liên kết kỹ thuật

- [`CONTRACT.md`](CONTRACT.md): API, schema, lỗi chuẩn và WebSocket protocol.
- [`DEPLOY.md`](DEPLOY.md): release, secrets, backup, migration và sự cố nền tảng.
- [`FEATURE_OPERATIONS.md`](FEATURE_OPERATIONS.md): flow RTC, Calendar, consent, retrieval, reminder và UI.
- [`RECONNECT_CONTRACT.md`](RECONNECT_CONTRACT.md): reconnect, resend và idempotency của WebSocket.
