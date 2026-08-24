# TRIỂN KHAI LINGUAFLOW

Tài liệu vận hành: đưa hệ thống lên chạy công khai, và xử lý khi có sự cố.
Lý do đằng sau các lựa chọn nằm ở `ARCHITECTURE.md` ADR-06 và ADR-18.

**Hình dạng bản triển khai**

| Thành phần | Nơi chạy | Ghi chú |
|---|---|---|
| Backend + Agent | Railway, dựng từ `Dockerfile` | **Đúng 1 bản sao**, không autoscale |
| Cơ sở dữ liệu | PostgreSQL (plugin của Railway) | Supabase thay được, xem §6 |
| Tệp đính kèm | Supabase Storage (bucket private `attachments`) khi có đủ `SUPABASE_URL`/`SUPABASE_SERVICE_ROLE_KEY`; nếu không, Volume gắn vào `/app/data` của container backend | Backend tự chọn theo biến môi trường có đặt hay không (xem §2 bước 4) |
| Frontend | Vercel, thư mục gốc `frontend-v1/` (v1 — chờ chuyển sang frontend mới của `develop_v2`) | Biến môi trường nhúng lúc build |

> **Chỉ được chạy một bản sao.** `ConnectionManager` giữ danh sách socket trong bộ
> nhớ tiến trình. Bản sao thứ hai sẽ nhận một nửa số kết nối và **âm thầm đánh rơi**
> tin nhắn phát cho nửa còn lại. Không đặt `--workers`, không bật autoscale, không
> tăng số replica cho tới khi có backplane dùng chung (ADR-08).

---

## 1. Chuẩn bị

Cần có: tài khoản GitHub (đã đẩy nhánh), tài khoản Railway, tài khoản Vercel, và
một khoá API của LLM provider (Groq là mặc định, miễn phí).

Sinh khoá ký JWT — **không dùng lại giá trị mẫu trong `.env.example`**, ứng dụng
sẽ từ chối khởi động ở production nếu gặp nó:

```bash
python -c "import secrets; print(secrets.token_urlsafe(48))"
```

## 2. Backend trên Railway

1. **New Project → Deploy from GitHub repo**, chọn kho này. Railway nhận ra
   `Dockerfile` ở thư mục gốc và dùng nó.
2. **Add → Database → PostgreSQL** trong cùng project.
3. Ở dịch vụ backend, mở **Variables** và đặt:

   | Biến | Giá trị |
   |---|---|
   | `APP_ENV` | `production` |
   | `JWT_SECRET` | chuỗi vừa sinh ở §1 |
   | `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (tham chiếu của Railway) |
   | `CORS_ORIGINS` | `https://<ten-app>.vercel.app` |
| `SUPABASE_URL` | URL project Supabase |
| `SUPABASE_SERVICE_ROLE_KEY` | Service role key, chỉ đặt ở backend |
| `SUPABASE_STORAGE_BUCKET` | `attachments` |
   | `LLM_PROVIDER` | `groq` |
   | `GROQ_API_KEY` | khoá của bạn |
   | `EMAIL_PROVIDER` | `smtp` |
   | `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL` | thông tin máy chủ gửi thư |

   **Năm biến SMTP là bắt buộc, không phải tuỳ chọn.** `Settings` từ chối khởi tạo
   khi `APP_ENV=production` mà `EMAIL_PROVIDER` vẫn là `memory` hoặc `console`, hoặc
   là `smtp` nhưng thiếu một trong bốn giá trị còn lại — container sẽ lặp vô hạn
   *trước khi* uvicorn kịp chạy. Bảng này trước đây bỏ sót chúng trong khi §5.1 lại
   ghi là bắt buộc, và hai chỗ nói ngược nhau thì chỗ người ta làm theo là chỗ có
   các bước. Không có SMTP thì mã OTP không gửi được, tức **không ai đăng ký được
   tài khoản mới** dù mọi thứ khác đã chạy.

   Tuỳ chọn: `CORS_ORIGIN_REGEX` cho bản xem trước của Vercel, `BRAINTRUST_API_KEY`
   để bật tracing (hoặc `OBSERVABILITY_PROVIDER=langfuse` cùng `LANGFUSE_*`), `FALLBACK_TRANSLATOR_ENABLED=false` để **không** gửi văn bản tin
   nhắn sang endpoint Google Translate không chính thức (ADR-07, ADR-15).

   Không cần đặt `PORT`: Railway tự tiêm, và `CMD` trong `Dockerfile` đọc nó.

4. Tạo bucket private `attachments` trong Supabase Storage. Backend tự dùng
   object storage khi có đủ `SUPABASE_URL` và `SUPABASE_SERVICE_ROLE_KEY`.
5. **Settings → Networking → Generate Domain** để lấy tên miền công khai.
6. Kiểm tra: `curl https://<backend>/health` phải trả `{"status":"ok","env":"production"}`.

Migration chạy tự động: `CMD` là `alembic upgrade head && uvicorn …`, nên container
**không khởi động** nếu schema không nâng cấp được — đó là hành vi mong muốn, hơn
là phục vụ trên một cơ sở dữ liệu sai hình dạng.

## 3. Frontend trên Vercel

1. **Add New → Project**, chọn kho này, đặt **Root Directory** là `frontend-v1`.
2. Environment Variables: `NEXT_PUBLIC_API_URL = https://<backend>.up.railway.app`
   (không có dấu `/` ở cuối).
3. Deploy. Sau đó quay lại Railway đặt `CORS_ORIGINS` đúng bằng tên miền Vercel
   vừa nhận được.

**Đổi `NEXT_PUBLIC_API_URL` thì phải build lại.** Biến `NEXT_PUBLIC_*` được nhúng
vào mã JavaScript lúc build; sửa giá trị mà không redeploy thì trang vẫn gọi địa
chỉ cũ. Địa chỉ WebSocket suy ra từ chính biến này (`https` → `wss`).

## 4. Chạy thử tại chỗ trước khi đẩy lên

```bash
docker compose up --build      # backend + PostgreSQL, giống production
cd frontend-v1 && npm run dev  # giao diện, trỏ vào localhost:8000
```

Chỉ cần cơ sở dữ liệu thôi thì dựng riêng nó, rồi chạy backend ở ngoài container:

```bash
docker compose up -d postgres   # PostgreSQL + pgvector, cổng 5432
make migrate              # bắt buộc: ứng dụng không còn tự tạo bảng
make reset-db             # xoá sạch rồi tạo lại, kèm hai tài khoản mẫu
make seed-glossary        # nạp bộ thuật ngữ mẫu en↔vi (88 mục)
make run
```

`make seed-glossary` đọc `seed/glossary_en_vi.jsonl` và chạy lại được nhiều lần: mục
được đối chiếu theo đúng khoá mà cơ sở dữ liệu ràng buộc duy nhất (thuật ngữ đã chuẩn
hoá, cặp ngôn ngữ, `domain`, `audience`) rồi cập nhật tại chỗ, nên sửa tệp và chạy lại
là cách đổi glossary trong lúc phát triển. Nó tồn tại vì đường khai thác tự động cần
nhiều người cùng sửa một thuật ngữ trước khi đề xuất được gì — đúng cho việc phát hiện
quy ước của đội, và vô dụng cho một buổi demo hoặc cho những tuần đầu dùng thật.
Mặc định mỗi mục tốn một lượt nhúng; `--no-embed` bỏ qua, khi đó mục vẫn khớp chính xác
nhưng chưa khớp được các biến thể người ta hay gõ.

**Không còn đường chạy trên SQLite** kể từ ADR-22: schema có cột `vector` của
pgvector, mà SQLite không có kiểu đó nên bảng còn không tạo được. Docker Engine
là đủ, không cần Docker Desktop — trên Windows, bản CLI cài trong WSL2 chạy tốt
và Windows nối được qua `localhost:5432`. Lưu ý máy ảo WSL tự tắt sau khoảng 60
giây không hoạt động và kéo PostgreSQL tắt theo; biểu hiện là
`ConnectionRefusedError` xuất hiện giữa chừng một lần chạy test.

**Nếu bạn đã có `data/app.db` từ trước ngày 15/08**, tệp đó do `create_all` tạo ra
nên không có dấu phiên bản của Alembic, và `make migrate` sẽ báo lỗi "table already
exists". Đánh dấu nó là đã ở phiên bản mới nhất — giữ nguyên dữ liệu — bằng:

```bash
alembic stamp head
alembic check     # "No new upgrade operations detected" là đúng
```

## 5. Biến môi trường

Nguồn sự thật là `src/config.py`; `.env.example` là bản chép có chú thích.
Chỉ **`JWT_SECRET`** là bắt buộc — thiếu nó tiến trình dừng ngay lúc khởi động.

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `APP_ENV` | `development` | `production` bật kiểm tra `JWT_SECRET` và tắt việc trả mã đặt lại mật khẩu trong phản hồi |
| `JWT_SECRET` | — | **Bắt buộc.** Ở production: không được là giá trị mẫu, tối thiểu 32 ký tự |
| `DATABASE_URL` | PostgreSQL cục bộ của `docker compose` | Bắt buộc là PostgreSQL có `pgvector` (ADR-22). `postgres://` và `postgresql://` được tự đổi sang `postgresql+asyncpg://` |
| `DATABASE_POOL_SIZE` / `DATABASE_MAX_OVERFLOW` | 5 / 10 | Chỉ dùng cho PostgreSQL. Mỗi WebSocket giữ một phiên suốt thời gian mở |
| `CORS_ORIGINS` | `http://localhost:3000` | Danh sách ngăn cách bằng dấu phẩy. Cũng là danh sách kiểm tra `Origin` của WebSocket |
| `CORS_ORIGIN_REGEX` | rỗng | Cho bản xem trước của Vercel |
| `UPLOAD_DIR` | `./data/uploads` | Trỏ vào volume khi chạy trong container |
| `MAX_UPLOAD_SIZE_BYTES` | 20 MiB | |
| `SUPABASE_URL` | rỗng | Có giá trị cùng service role key thì bật Supabase Storage |
| `SUPABASE_SERVICE_ROLE_KEY` | rỗng | Chỉ đặt ở backend, không bao giờ dùng `NEXT_PUBLIC_*` |
| `SUPABASE_STORAGE_BUCKET` | `attachments` | Bucket private chứa nội dung file |
| `LLM_PROVIDER` + khoá tương ứng | `groq` | `groq` \| `deepseek` \| `gemini` \| `openai` |
| `JWT_EXPIRE_MINUTES` | 1440 | Access token **không thu hồi được** trước khi hết hạn |
| `REFRESH_EXPIRE_DAYS` | 30 | |
| `PASSWORD_RESET_EXPIRE_MINUTES` | 30 | |
| `FALLBACK_TRANSLATOR_ENABLED` | `true` | Xem cảnh báo quyền riêng tư ở ADR-15 |
| `EMAIL_PROVIDER` | `smtp` | `smtp` \| `console` \| `memory`. Ở `APP_ENV=production` bắt buộc dùng `smtp`, cấm `memory`/`console` |
| `SMTP_HOST`, `SMTP_PORT` | `smtp.gmail.com` / `587` | Bắt buộc ở production khi dùng SMTP |
| `SMTP_USER`, `SMTP_PASSWORD` | — | Bắt buộc ở production |
| `SMTP_FROM_EMAIL`, `SMTP_FROM_NAME` | — / `LinguaFlow` | Địa chỉ email gửi OTP |
| `SMTP_USE_TLS` | `true` | Bật STARTTLS cho cổng 587 |
| `OBSERVABILITY_PROVIDER` | `braintrust` | `braintrust` \| `langfuse` \| `none`. Chọn backend nhận trace (ADR-29) |
| `BRAINTRUST_API_KEY`, `BRAINTRUST_PROJECT` | rỗng / `linguaflow` | Rỗng là tắt tracing. Khoá Braintrust bắt đầu bằng `sk-` |
| `LANGFUSE_*` | rỗng | Chỉ dùng khi `OBSERVABILITY_PROVIDER=langfuse`. Rỗng là tắt tracing. Vùng của host phải khớp vùng cấp khoá |

### 5.1. Khoá bí mật — cần cấp những gì

| Khoá | Bắt buộc? | Hậu quả nếu thiếu |
|---|---|---|
| `JWT_SECRET` | **Có** | Tiến trình dừng ngay lúc khởi động |
| `GROQ_API_KEY` (hoặc khoá của provider đang chọn) | **Có, trên thực tế** | Server vẫn chạy, nhưng mọi tin nhắn rơi xuống đường dự phòng rồi trả nguyên bản |
| `DATABASE_URL` | Có, khi triển khai | Mặc định là tệp SQLite trong container — mất sạch sau mỗi lần deploy |
| `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL` | **Có, ở production** | Server từ chối khởi động nếu thiếu ở `APP_ENV=production` |
| `AI_LOG_API_KEY`, `AI_LOG_SERVER` | Chỉ trên máy lập trình viên | Hook trước khi push không nộp được nhật ký. **Không cần** đặt trên máy chủ |
| `BRAINTRUST_API_KEY` (hoặc `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` khi chọn Langfuse) | Không | Để trống là tắt tracing, luồng dịch không bị ảnh hưởng |
| `ANTHROPIC_API_KEY`, `LANGCHAIN_*` | Không | Thuộc về công cụ lập trình, `src/config.py` không đọc |

### 5.2. Cấu hình Email Provider & Bảo mật OTP (Batch F)

- **Production (`APP_ENV=production`)**:
  - Bắt buộc `EMAIL_PROVIDER=smtp`.
  - Hệ thống kiểm tra nghiêm ngặt lúc khởi động (fail-fast) và **từ chối chạy** nếu cấu hình là `memory` hoặc `console`, hoặc thiếu bất kỳ biến nào trong: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL`.
  - Không bao giờ silent-drop email nếu SMTP gặp lỗi kết nối/xác thực.
- **Môi trường Test & Development**:
  - Mặc định sử dụng `EMAIL_PROVIDER=memory` (hoặc `console` khi phát triển cục bộ).
  - Memory provider lưu trữ danh sách email gửi đi trong bộ nhớ tiến trình (`_memory_sender.sent_emails`), cho phép test suite chạy độc lập không phụ thuộc vào internet hay dịch vụ SMTP bên ngoài.
- **Nguyên tắc bảo mật OTP**:
  - Tuyệt đối **không ghi log** mã OTP plaintext ở bất kỳ cấp độ log nào.
  - Cơ sở dữ liệu chỉ lưu trữ băm một chiều (bcrypt hash) của mã OTP trong bảng `pending_registrations`.
  - Validation error 422 tự động redact toàn bộ mật khẩu, mã OTP, token ở mọi độ sâu dữ liệu.

### 5.3. Cấu hình Google Sign-In (Batch G)

**Tạo OAuth Client ID trên Google Cloud Console:**

1. Truy cập [Google Cloud Console](https://console.cloud.google.com/apis/credentials?project=_)
2. Chọn hoặc tạo project
3. **APIs & Services → Credentials → Create Credentials → OAuth client ID**
4. Application type: **Web application**
5. Thêm **Authorized JavaScript origins**:
   - Development: `http://localhost:3000`
   - Production / Tunnel: `https://agent.dquangminh2003.id.vn` (hoặc domain Vercel/Cloudflare của bạn)
6. Copy **Client ID** (format: `xxx.apps.googleusercontent.com`)

**Địa chỉ API Backend Production:**
- Production API: `https://api.dquangminh2003.id.vn`

**Đặt biến môi trường:**

| Vị trí | Biến | Giá trị |
|---|---|---|
| Backend `.env` | `GOOGLE_OAUTH_CLIENT_ID` | Client ID vừa tạo |
| Frontend `.env.local` | `NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID` | **Cùng Client ID** |

> **Quan trọng:**
> - Frontend và Backend phải dùng **cùng một Google OAuth Web Client ID**. Frontend sử dụng Client ID để tải thư viện Google Identity Services (GIS), backend dùng Client ID đó để xác minh chữ ký token JWT.
> - Luồng GIS ID-token này xác minh chữ ký JWT trực tiếp với JWKS của Google nên **không cần Google client secret hoặc OAuth redirect callback**.
> - **Full Authentication Provider:** Đăng nhập bằng Google tự động đăng nhập nếu đã có `google_sub`, tự động liên kết nếu trùng `email` đã xác thực (`google_sub` là NULL), và tự động tạo tài khoản Google-native mới nếu chưa từng tồn tại.
> - Email Google phải đã xác minh; nếu email đã thuộc `google_sub` khác, server trả `409 Conflict` và không đổi liên kết.
> - **Bảo vệ hủy liên kết:** Tài khoản tạo thuần bằng Google (`password_hash = NULL`) không thể hủy liên kết Google nếu chưa đặt mật khẩu.

**Migration database:**
```bash
alembic upgrade head
```
Migration `7b2c91d4a08` thêm cột `google_sub` vào bảng `users` với unique constraint.
Migration `8c3d1e4f5a6b` chuyển cột `password_hash` sang `nullable=True` để hỗ trợ tài khoản Google-native, kèm check constraint buộc mỗi user phải còn mật khẩu hoặc `google_sub`.

**Tắt Google Sign-In:**
- Để trống `NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID` → nút Google ẩn trên giao diện đăng nhập và cài đặt
- Để trống `GOOGLE_OAUTH_CLIENT_ID` → endpoint `/auth/google/*` và `/auth/me/google/link` trả `401 Unauthorized` (báo chưa cấu hình)

**Nguyên tắc:** `.env` chứa giá trị thật và **không bao giờ được commit**;
`.env.example` là bản mẫu **được commit** nên mọi giá trị trong đó là công khai
với cả tổ chức. Từ 15/08 `.gitignore` bắt `.env*` (trừ `.env.example`) và bắt
`**/.ai-log/*.jsonl` ở mọi cấp thư mục, chứ không chỉ ở thư mục gốc.

Kiểm tra nhanh trước khi push — không được có kết quả nào:

```bash
git grep -nIE "(gsk_|sk-ant-|sk-proj-|AIza|sk-lf-|pk-lf-)[A-Za-z0-9_-]{15,}"
```

## 6. Dùng Supabase thay cho PostgreSQL của Railway

Không phải sửa dòng mã nào, chỉ đổi `DATABASE_URL`. Hai điều dễ vấp:

- **Cổng 6543 là pooler ở chế độ transaction**, không dùng được prepared statement
  của `asyncpg`. Hoặc dùng kết nối trực tiếp cổng **5432**, hoặc thêm
  `?prepared_statement_cache_size=0` vào cuối URL.
- Chuỗi Supabase cấp bắt đầu bằng `postgresql://`; ứng dụng tự đổi sang
  `postgresql+asyncpg://` nên dán nguyên cũng chạy.

## 7. Quên mật khẩu — cách làm hiện tại

Chưa gắn dịch vụ gửi email. Ở `APP_ENV=production`, `POST /auth/password/forgot`
**không** trả mã trong phản hồi mà ghi vào log máy chủ ở mức `WARNING`:

```
WARNING src.api.routes: Password reset requested for an@example.com. Reset token: ... (valid 30 minutes)
```

Quản trị viên mở log của Railway, tìm dòng đó, đọc mã cho người dùng; người dùng
dán vào ô **"Mã đặt lại"** ở màn hình khôi phục rồi đặt mật khẩu mới. Mã dùng một
lần và hết hạn sau 30 phút.

Đây là giải pháp tạm và không mở rộng được. Bước tiếp theo là cấu hình SMTP (hoặc
Resend) và gửi liên kết đặt lại — khi đó bỏ hẳn phần ghi log này.

## 8. Sao lưu

```bash
pg_dump "$DATABASE_URL" > backup-$(date +%F).sql   # cơ sở dữ liệu
```

Nội dung tệp đính kèm nằm trong Supabase Storage, không nằm trong bản dump ở trên.
Trước lần deploy đầu tiên dùng Storage, chuyển file local còn tồn tại bằng:

```bash
python -m scripts.migrate_attachments_to_supabase
```

Lệnh mặc định giữ nguyên file local. Sau khi lượt đầu không có `failed` hoặc
`missing_local`, có thể chạy lại với `--delete-local-after-verify`; script chỉ
xóa từng file sau khi tải object về và xác minh SHA-256 trùng khớp.

## 9. Giới hạn đã biết

Ghi ra để người vận hành biết, không phải để bỏ qua:

1. **Một bản sao duy nhất.** Xem cảnh báo đầu tài liệu.
2. **Không có giới hạn tần suất** ở `/auth/login`, `/auth/password/forgot` và
   `/users`. Đăng nhập có thể bị dò mật khẩu, và người đã đăng nhập có thể dò xem
   một địa chỉ email có tài khoản hay không. Ưu tiên số một cho vòng sau.
3. **Không xoá được tài khoản.** Bốn khoá ngoại đang là `ON DELETE RESTRICT`, nên
   trên PostgreSQL lệnh xoá sẽ báo lỗi thay vì âm thầm thành công như trên SQLite.
   Khi làm chức năng này thì phải là xoá mềm.
4. **Access token không thu hồi được** cho tới khi hết hạn (mặc định 24 giờ). Đăng
   xuất chỉ huỷ refresh token.
5. **Không phân trang lịch sử tin nhắn**: mỗi hội thoại tải tối đa 100 tin gần nhất.
6. **Không quản trị nhóm**: không đổi tên, không thêm/xoá thành viên, không rời nhóm.
7. **Dữ liệu SQLite cũ không mang sang PostgreSQL được.** `DateTime(timezone=True)`
   trả về giá trị *naive* trên SQLite và *aware* trên PostgreSQL, chép thẳng là sai
   múi giờ. Bản triển khai bắt đầu từ cơ sở dữ liệu rỗng.

## 10. Sự cố thường gặp

| Triệu chứng | Nguyên nhân | Cách xử lý |
|---|---|---|
| Trang gọi `http://localhost:8000` dù đã đặt biến | `NEXT_PUBLIC_API_URL` nhúng lúc build | Redeploy frontend sau khi đổi biến |
| Trình duyệt báo lỗi CORS | Tên miền Vercel chưa có trong `CORS_ORIGINS` | Thêm vào rồi khởi động lại backend |
| WebSocket đóng ngay với mã `4403` | `Origin` không khớp danh sách CORS | Như trên — WebSocket dùng chung danh sách đó |
| WebSocket đóng với mã `4401` | Token sai, hết hạn, hoặc không gửi khung `auth` trong 10 giây | Đăng nhập lại |
| Container dừng ngay khi khởi động, log nói `asyncio extension requires an async driver` | `DATABASE_URL` trỏ driver đồng bộ | Hiếm — ứng dụng tự đổi tiền tố; kiểm tra xem URL có ghi rõ `+psycopg` không |
| Container dừng, log nói `JWT_SECRET` | Thiếu, hoặc còn là giá trị mẫu ở production | Sinh khoá mới theo §1 |
| Upload vẫn ghi vào container | Thiếu `SUPABASE_URL` hoặc `SUPABASE_SERVICE_ROLE_KEY` | Đặt đủ hai biến rồi deploy lại |
| Tin nhắn gửi được nhưng người kia không nhận | Đang chạy nhiều hơn một bản sao | Đặt lại về 1 replica |
| Tin nhắn không được dịch, cờ `is_fallback` bật | Hết hạn mức LLM hoặc khoá sai | Kiểm tra khoá, `make metrics` xem tỷ lệ fallback |
