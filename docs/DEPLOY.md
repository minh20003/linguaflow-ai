# TRIỂN KHAI LINGUAFLOW

Tài liệu vận hành: đưa hệ thống lên chạy công khai, và xử lý khi có sự cố.
Lý do đằng sau các lựa chọn nằm ở `ARCHITECTURE.md` ADR-06 và ADR-18.

**Hình dạng bản triển khai**

| Thành phần | Nơi chạy | Ghi chú |
|---|---|---|
| Backend + Agent | Ubuntu VPS, container GHCR prebuilt | **Đúng 1 bản sao**, không autoscale |
| Cơ sở dữ liệu | `pgvector/pgvector:pg16` trên VPS | volume `postgres-data` bền vững |
| Tệp đính kèm | volume `backend-uploads` trên VPS khi không cấu hình đủ Supabase Storage | không xoá/tạo lại trong deploy bình thường |
| Frontend | Ubuntu VPS, container GHCR prebuilt sau Caddy | `NEXT_PUBLIC_*` nhúng lúc GitHub Actions build image |

> **Chỉ được chạy một bản sao.** `ConnectionManager` giữ danh sách socket trong bộ
> nhớ tiến trình. Bản sao thứ hai sẽ nhận một nửa số kết nối và **âm thầm đánh rơi**
> tin nhắn phát cho nửa còn lại. Không đặt `--workers`, không bật autoscale, không
> tăng số replica cho tới khi có backplane dùng chung (ADR-08).

---

## 1. Production VPS release contract (CD-1)

Production source of truth is `docker-compose.production.yml`, Caddy, and the
protected VPS runtime file `/etc/linguaflow/production.env` (root-owned, mode
`0600`). Do not use the Railway/Vercel instructions from older revisions as a
production runbook.

The Compose file consumes only these immutable application images:

```text
ghcr.io/ai20k-build-phase-cohort-3/p-217-backend:${RELEASE_SHA}
ghcr.io/ai20k-build-phase-cohort-3/p-217-frontend:${RELEASE_SHA}
```

OCI image names are lowercase; the organization and repository names are
normalized to `ai20k-build-phase-cohort-3` and `p-217`. `RELEASE_SHA` is a
required full 40-character Git commit SHA supplied by the release command. It
is never `latest`, a branch name, or an unpinned tag.

Every future production Compose command must use this exact envelope so
interpolation and Docker identities remain stable:

```bash
RELEASE_SHA=<full-40-character-sha> docker compose \
  --env-file /etc/linguaflow/production.env \
  -p linguaflow \
  -f docker-compose.production.yml \
  <command>
```

`--env-file` is required because a service-level `env_file:` only injects values
into a container; it does **not** provide values for Compose `${VAR}`
interpolation. Compose needs the same protected file to resolve Postgres/Caddy
variables and the release input needs `RELEASE_SHA` from the deployment command.

Normal deployment must preserve exactly these durable volumes:
`postgres-data`, `backend-uploads`, `caddy-data`, and `caddy-config`. Never use
`docker compose down -v`, `docker volume rm`, a database reset/seed, or an
automatic Alembic downgrade. PostgreSQL stays on `pgvector/pgvector:pg16`.
Caddy remains the only public port publisher and backend/frontend stay on the
private Compose network.

The backend remains exactly one Uvicorn worker and one service replica because
the WebSocket `ConnectionManager` is in-process memory. Do not add workers,
replicas, or autoscaling.

`NEXT_PUBLIC_API_URL` and `NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID` are public
build-time inputs. A future GitHub Actions build supplies them to
`frontend/Dockerfile`; they are not runtime secrets and do not belong in a VPS
Compose build block.

`scripts/configure_vps_env.sh` is **INITIAL VPS PROVISIONING ONLY**. It
generates `POSTGRES_PASSWORD` and refuses a non-empty existing value; do not
run it as a release command after PostgreSQL initialization.

This phase defines the contract only. It does not add a GitHub Actions workflow,
GHCR login, SSH behavior, or a VPS change.

### 1.1. Release helpers (CD-2)

`scripts/deploy_release.sh` accepts only a full 40-character hexadecimal commit
SHA. It lowercases that SHA before selecting the two GHCR images, so branches,
tags, `latest`, and abbreviated SHAs cannot reach a production Compose command.
It resolves the repository root itself and applies the fixed Compose envelope on
every call; callers must not use the current directory to infer the project.

Run the deterministic plan first. It validates the SHA and prints the release
order but never calls Docker, PostgreSQL, SSH, a registry, or last-known-good
state:

```bash
sh scripts/deploy_release.sh --dry-run <full-40-character-sha>
```

The actual command is a VPS-only operation for the future deploy channel:

```bash
sh scripts/deploy_release.sh <full-40-character-sha>
```

Its fixed order is: logical PostgreSQL backup under
`/var/backups/linguaflow/`, pull the two exact images, validate Caddy, run
`alembic upgrade head` in the new backend image, recreate only backend/frontend/
Caddy with each service explicitly scaled to one replica, then make bounded
public checks against the production API and frontend.
Any failed backup, pull, Caddy validation, migration, rollout, or verification
stops the remaining release steps. It never automatically rolls back, restores
a database, marks a release last-known-good, removes a volume, or runs a
destructive cleanup.

`scripts/verify_production.sh` is independently runnable from any networked
host with `curl`; it follows redirects and expects API HTTP 200 JSON with
`service: "LinguaFlow API"` and `database: "ok"`, plus a frontend HTTP 200
response containing `LinguaFlow`. Retries are bounded by `VERIFY_ATTEMPTS`,
`VERIFY_DELAY_SECONDS`, and `VERIFY_TIMEOUT_SECONDS`.

After independent acceptance of those checks, an operator may explicitly
record the deployed SHA, and only then:

```bash
sh scripts/finalize_release.sh <full-40-character-sha>
```

The finalizer performs fresh public and running-image verification before it
writes `/opt/linguaflow/state/last-known-good-sha`; ordinary deployment does
not call it. The unresolved future SSH privilege model must allow the
deploy channel to read the protected Compose environment indirectly through
Docker Compose, while never granting it a way to print, copy, or source
`/etc/linguaflow/production.env`. Choose and review either a constrained sudo/
forced-command wrapper or a carefully scoped deployment group before CD-3; this
repository phase makes no VPS permission change. Future GHCR authentication must
use a transient stdin credential and a temporary `DOCKER_CONFIG` that is removed
after the job. Runtime application secrets remain on the VPS.

### 1.2. Finalization image identity guard (CD-2R)

Public health alone does not prove which release is serving traffic. Before
`scripts/finalize_release.sh` writes LKG, it re-runs public verification, uses
the fixed Compose envelope to resolve exactly one **running** `backend` and
`frontend` container, and uses `docker inspect` to require exact equality with
the requested SHA-tagged image references. A missing container, multiple
containers, or either image mismatch fails without changing LKG. Its dry-run
only describes these checks; it does not inspect Docker.

Tag equality is sufficient for this CD-2R guard. CD-3 must additionally build
both application images with
`org.opencontainers.image.revision=<full-sha>` and record their immutable image
digests as release evidence. Because backend still has `depends_on: postgres`,
CD-4/CD-5 must capture the PostgreSQL container and all durable-volume identity
before and after the first real deployment as acceptance evidence. This is a
verification requirement, not permission to recreate, reset, or remove
PostgreSQL state.

## 2. Chạy thử tại chỗ trước khi đẩy lên

```bash
docker compose up --build      # backend + PostgreSQL, giống production
cd frontend && npm run dev     # giao diện, trỏ vào localhost:8000
```

Wheel `imageio-ffmpeg` cung cấp binary FFmpeg cho cả container và local vì trình
duyệt phổ biến thường ghi WebM/Opus, OGG/Opus hoặc MP4/AAC, trong khi Gemini
Transcribe nhận một tập input trực tiếp hẹp hơn. Không cần cài gói multimedia hệ
thống; wheel Linux khoảng 29,5 MiB thay vì dependency closure Debian khoảng
466 MiB. Nếu binary wheel bị thiếu/hỏng, voice message cần chuyển mã đi vào
trạng thái `failed`, còn text/file/image và audio Gemini nhận trực tiếp không bị
đổi.

Chỉ cần cơ sở dữ liệu thôi thì dựng riêng nó, rồi chạy backend ở ngoài container:

```bash
docker compose up -d postgres   # PostgreSQL + pgvector, cổng host 5433
make migrate              # bắt buộc: ứng dụng không còn tự tạo bảng
make reset-db             # xoá sạch rồi tạo lại, kèm hai tài khoản mẫu
make seed-glossary        # nạp bộ thuật ngữ mẫu en↔vi (88 mục)
make run
```

**Nếu bạn đã có `data/app.db` từ trước ngày 15/08**, tệp đó do `create_all` tạo ra
nên không có dấu phiên bản của Alembic, và `make migrate` sẽ báo lỗi "table already
exists". Đánh dấu nó là đã ở phiên bản mới nhất — giữ nguyên dữ liệu — bằng:

```bash
alembic stamp head
alembic check     # "No new upgrade operations detected" là đúng
```

### 2.1. Voice message và Gemini STT

Voice ở đây là **tin nhắn ghi âm**, tách biệt hoàn toàn với tính năng gọi
thoại/video. Luồng production là:

```text
audio gốc trong attachment private
→ chuyển mã tạm sang mono 16 kHz FLAC khi cần
→ Gemini Files API
→ gemini-3.5-transcribe / Interactions API / mode=verbatim / tự phát hiện ngôn ngữ
→ xoá best-effort file Gemini tạm
→ Message.original_text
→ pipeline dịch văn bản hiện có
```

`STT_PROVIDER` và `STT_MODEL` không thay đổi `LLM_PROVIDER` hoặc model dịch.
`GOOGLE_API_KEY` được ưu tiên; `GEMINI_API_KEY` là alias tương thích. Không đặt
cả hai khoá vào frontend và không ghi chúng vào log.

Recorder chọn định dạng bằng `MediaRecorder.isTypeSupported()`, không dò tên
trình duyệt. Backend nhận WebM/Opus, OGG/Opus hoặc Vorbis, MP4/AAC hoặc Opus,
AAC, AIFF, FLAC, MP3 và WAV khi phần mở rộng khớp container. Audio browser-native
không được Gemini nhận trực tiếp được chuyển mã qua stdin/stdout bằng câu lệnh
FFmpeg cố định; audio gốc bền vững không bị thay thế, file chuyển mã không ghi ra
đĩa và không đi vào context dịch. Mỗi input/output bị chặn bởi
`MAX_UPLOAD_SIZE_BYTES`, thời gian chuyển mã dùng cùng giới hạn
`STT_TIMEOUT_SECONDS`, và tối đa hai tiến trình chuyển mã chạy đồng thời trong
một backend process.

Lifecycle bền vững là `pending → completed` hoặc `pending → failed`.
`completed` bắt buộc có transcript đầy đủ khác rỗng trong
`Message.original_text`; `pending`/`failed` bắt buộc để trường này rỗng. Retry
dùng lại cùng Message và attachment, chỉ request thắng cập nhật atomic
`failed → pending` mới khởi chạy STT. Lịch sử REST khôi phục trạng thái khi client
bỏ lỡ sự kiện; không có job queue bền vững, nên vẫn tồn tại crash window giữa
commit và publication/scheduling. Audio được buffer toàn bộ trong bộ nhớ, được
giới hạn bởi cap 20 MiB mặc định; Phase này không dùng streaming STT.

Audio và transcript được xử lý plaintext phía server/provider qua TLS và chỉ
truy cập attachment qua xác thực + kiểm tra thành viên. Đây **không phải mã hoá
đầu-cuối**. Gemini file name/URI, provider body, key, audio và transcript không
được ghi vào operational logs; file Gemini tạm được xoá best-effort sau success
hoặc failure sau upload.

Kiểm tra trước deploy:

```bash
alembic upgrade head
alembic heads                 # đúng một head: a3f1c7e9b2d4
pytest -q
cd frontend
npm test
npx tsc --noEmit
npm run lint
npm run build
```

Browser support là capability thực tế của từng browser/OS. Chrome/Edge hiện tại
trên Windows đã được kiểm tra có WebM/Opus và MP4/AAC; Firefox và Safari/WebKit
phải được kiểm tra thủ công trên OS đích dù candidate OGG/Opus, WebM/Opus và
MP4/AAC tương ứng đã có. Khi không có candidate tương thích, client báo lỗi trước
upload thay vì đổi đuôi hoặc gửi byte sai nhãn.

## 3. Biến môi trường

Nguồn sự thật là `src/config.py`; `.env.example` là bản chép có chú thích.
Chỉ **`JWT_SECRET`** là bắt buộc — thiếu nó tiến trình dừng ngay lúc khởi động.

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `APP_ENV` | `development` | `production` bật kiểm tra `JWT_SECRET` và tắt việc trả mã đặt lại mật khẩu trong phản hồi |
| `JWT_SECRET` | — | **Bắt buộc.** Ở production: không được là giá trị mẫu, tối thiểu 32 ký tự |
| `DATABASE_URL` | SQLite trong `./data` | `postgres://` và `postgresql://` được tự đổi sang `postgresql+asyncpg://` |
| `DATABASE_POOL_SIZE` / `DATABASE_MAX_OVERFLOW` | 5 / 10 | Chỉ dùng cho PostgreSQL. Mỗi WebSocket giữ một phiên suốt thời gian mở |
| `CORS_ORIGINS` | `http://localhost:3000` | Danh sách ngăn cách bằng dấu phẩy. Cũng là danh sách kiểm tra `Origin` của WebSocket |
| `CORS_ORIGIN_REGEX` | rỗng | Cho hostname xem trước khi thật sự cần dùng |
| `FRONTEND_URL` | `http://localhost:3000` | URL chuẩn dẫn từ email đặt lại mật khẩu. Bắt buộc dùng HTTPS ở production |
| `UPLOAD_DIR` | `./data/uploads` | Trỏ vào volume khi chạy trong container |
| `MAX_UPLOAD_SIZE_BYTES` | 20 MiB | |
| `LLM_PROVIDER` + khoá tương ứng | `groq` | `groq` \| `deepseek` \| `gemini` \| `openai` |
| `STT_PROVIDER` | `gemini` | Provider chuyển giọng nói thành văn bản; độc lập với `LLM_PROVIDER` |
| `STT_MODEL` | `gemini-3.5-transcribe` | Model file transcription non-live cho voice message |
| `STT_TIMEOUT_SECONDS` | `60` | Giới hạn 1..300 giây cho một yêu cầu STT |
| `STT_RETRY_ATTEMPTS` | `3` | Tổng số lượt HTTP, gồm lượt đầu; chỉ retry 408, 429 và 5xx với exponential backoff |
| `DATABASE_ECHO` | `false` | Chỉ bật khi chẩn đoán SQL bằng dữ liệu không nhạy cảm; bound values có thể chứa message/transcript |
| `JWT_EXPIRE_MINUTES` | 1440 | Access token **không thu hồi được** trước khi hết hạn |
| `REFRESH_EXPIRE_DAYS` | 30 | |
| `PASSWORD_RESET_EXPIRE_MINUTES` | 30 | |
| `FALLBACK_TRANSLATOR_ENABLED` | `true` | Xem cảnh báo quyền riêng tư ở ADR-15 |
| `LANGFUSE_*` | rỗng | Rỗng là tắt tracing. Vùng của host phải khớp vùng cấp khoá |

### 3.1. Khoá bí mật — cần cấp những gì

| Khoá | Bắt buộc? | Hậu quả nếu thiếu |
|---|---|---|
| `JWT_SECRET` | **Có** | Tiến trình dừng ngay lúc khởi động |
| Khoá của `LLM_PROVIDER` | **Có, trên thực tế** | Server vẫn chạy, nhưng dịch văn bản rơi xuống đường dự phòng hoặc trả nguyên bản |
| `GOOGLE_API_KEY` hoặc `GEMINI_API_KEY` khi `STT_PROVIDER=gemini` | **Có để dùng voice message** | Tin voice được lưu cùng audio nhưng transcription chuyển sang `failed`; có thể retry sau khi sửa cấu hình |
| `DATABASE_URL` | Có, khi triển khai | Phải trỏ tới PostgreSQL có pgvector; local `docker-compose.yml` publish ở `localhost:5433` |
| `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM_EMAIL` | **Có, ở production** | Server từ chối khởi động nếu thiếu ở `APP_ENV=production` |
| `AI_LOG_API_KEY`, `AI_LOG_SERVER` | Chỉ trên máy lập trình viên | Hook trước khi push không nộp được nhật ký. **Không cần** đặt trên máy chủ |
| `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` | Không | Để trống là tắt tracing, luồng dịch không bị ảnh hưởng |
| `ANTHROPIC_API_KEY`, `LANGCHAIN_*` | Không | Thuộc về công cụ lập trình, `src/config.py` không đọc |

### 3.2. Cấu hình Email Provider & Bảo mật OTP (Batch F)

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

### 3.3. Cấu hình Google Sign-In (Batch G)

**Tạo OAuth Client ID trên Google Cloud Console:**

1. Truy cập [Google Cloud Console](https://console.cloud.google.com/apis/credentials?project=_)
2. Chọn hoặc tạo project
3. **APIs & Services → Credentials → Create Credentials → OAuth client ID**
4. Application type: **Web application**
5. Thêm **Authorized JavaScript origins**:
   - Development: `http://localhost:3000`
   - Production: `https://c3-lingua-flow-217.dquangminh2003.id.vn`
6. Copy **Client ID** (format: `xxx.apps.googleusercontent.com`)

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

## 4. Dùng Supabase PostgreSQL (tuỳ chọn)

Không phải sửa dòng mã nào, chỉ đổi `DATABASE_URL`. Hai điều dễ vấp:

- **Cổng 6543 là pooler ở chế độ transaction**, không dùng được prepared statement
  của `asyncpg`. Hoặc dùng kết nối trực tiếp cổng **5432**, hoặc thêm
  `?prepared_statement_cache_size=0` vào cuối URL.
- Chuỗi Supabase cấp bắt đầu bằng `postgresql://`; ứng dụng tự đổi sang
  `postgresql+asyncpg://` nên dán nguyên cũng chạy.

## 5. Quên mật khẩu

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

## 6. Sao lưu

```bash
pg_dump "$DATABASE_URL" > backup-$(date +%F).sql   # cơ sở dữ liệu
```

Với production hiện tại, nội dung tệp đính kèm nằm trong volume
`backend-uploads`, không nằm trong bản dump ở trên; phải sao lưu volume đó cùng
PostgreSQL. Nếu sau này cấu hình đủ Supabase Storage, nội dung mới nằm ở đó và
cũng không có trong PostgreSQL dump. Trước lần deploy đầu tiên dùng Storage,
chuyển file local còn tồn tại bằng:

```bash
python -m scripts.migrate_attachments_to_supabase
```

Lệnh mặc định giữ nguyên file local. Sau khi lượt đầu không có `failed` hoặc
`missing_local`, có thể chạy lại với `--delete-local-after-verify`; script chỉ
xóa từng file sau khi tải object về và xác minh SHA-256 trùng khớp.

## 7. Giới hạn đã biết

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

## 8. Sự cố thường gặp

| Triệu chứng | Nguyên nhân | Cách xử lý |
|---|---|---|
| Trang gọi `http://localhost:8000` dù đã đặt biến | `NEXT_PUBLIC_API_URL` nhúng lúc build | Redeploy frontend sau khi đổi biến |
| Trình duyệt báo lỗi CORS | App domain chưa có trong `CORS_ORIGINS` | Thêm domain HTTPS công khai rồi khởi động lại backend |
| WebSocket đóng ngay với mã `4403` | `Origin` không khớp danh sách CORS | Như trên — WebSocket dùng chung danh sách đó |
| WebSocket đóng với mã `4401` | Token sai, hết hạn, hoặc không gửi khung `auth` trong 10 giây | Đăng nhập lại |
| Container dừng ngay khi khởi động, log nói `asyncio extension requires an async driver` | `DATABASE_URL` trỏ driver đồng bộ | Hiếm — ứng dụng tự đổi tiền tố; kiểm tra xem URL có ghi rõ `+psycopg` không |
| Container dừng, log nói `JWT_SECRET` | Thiếu, hoặc còn là giá trị mẫu ở production | Sinh khoá mới theo §1 |
| Tệp đính kèm biến mất sau khi deploy | Chưa gắn volume, hoặc `UPLOAD_DIR` không trỏ vào volume | Xem §2 bước 4 |
| Tin nhắn gửi được nhưng người kia không nhận | Đang chạy nhiều hơn một bản sao | Đặt lại về 1 replica |
| Tin nhắn không được dịch, cờ `is_fallback` bật | Hết hạn mức LLM hoặc khoá sai | Kiểm tra khoá, `make metrics` xem tỷ lệ fallback |

## 9. Tự động phát hành từ `develop_v2`

Luồng production chuẩn bắt đầu khi một pull request được merge vào
`develop_v2`:

1. job `lint-and-test` hiện hữu phải chạy xanh trên PostgreSQL/pgvector;
2. gate xác minh sự kiện là `push`, dùng đúng `github.sha`, và SHA đó là merge
   commit của PR nhắm vào `develop_v2`;
3. backend và frontend được build hoặc tái sử dụng bằng tag SHA 40 ký tự, rồi
   kiểm tra digest và nhãn OCI revision;
4. job deploy nối hàng trong concurrency group `linguaflow-production`, đăng
   nhập VPS bằng dedicated key và gọi duy nhất root-owned release wrapper;
5. wrapper kiểm tra bundle, health, dung lượng, digest và OCI revision trước khi
   backup, migrate, và recreate riêng backend/frontend/Caddy;
6. PostgreSQL container và bốn durable volume phải giữ nguyên identity; public
   verification phải đạt trước khi ghi LKG.

Pull-request workflow chỉ chạy test, không được build image hoặc deploy. Push
trực tiếp không gắn với PR được gate từ chối. Nhiều merge gần nhau được xếp hàng
và không huỷ release đang chạy. Ngay trước SSH, workflow đọc lại head của
`develop_v2`; release cũ đã bị một merge mới thay thế sẽ dừng ở trạng thái
superseded thay vì triển khai ngược production về SHA cũ.

### 9.1. Công tắc vận hành

- `AUTO_DEPLOY_PRODUCTION=false`: tắt phát hành tự động ngay ở gate. Đây là
  trạng thái mặc định khi bootstrap hoặc xử lý sự cố.
- `AUTO_DEPLOY_PRODUCTION=true`: mỗi merge hợp lệ vào `develop_v2` tự động đi
  qua toàn bộ pipeline.
- `CD_CHANNEL_REHEARSAL=true` chỉ dùng khi `AUTO_DEPLOY_PRODUCTION` đang tắt.
  Rehearsal xác minh SSH/GHCR/wrapper với đúng LKG hiện tại và không backup,
  migrate, recreate container hay ghi LKG.

Workflow `deploy-production.yml` trên default branch `main` là đường fallback
thủ công để gate và tạo exact-SHA artifacts. Nó không bị luồng tự động thay thế
hoặc xoá.

### 9.2. Phân tách secret

GitHub chỉ giữ private key của kênh deploy. Host, port, user, pinned host key và
public build values nằm trong Repository Actions Variables. Token GHCR theo job
được chuyển qua SSH bằng stdin, dùng với một `DOCKER_CONFIG` tạm, logout và xoá
ngay khi kết thúc.

Toàn bộ runtime secret (`JWT_SECRET`, database, SMTP, LLM, OAuth backend, v.v.)
vẫn chỉ nằm trong `/etc/linguaflow/production.env` trên VPS. Workflow và release
wrapper không đọc hoặc in nội dung file này.

### 9.3. Khi pipeline dừng

- Test/gate/build lỗi: production chưa bị chạm; sửa bằng PR mới.
- Digest hoặc OCI revision không khớp: wrapper dừng trước migration/rollout.
- Backup, Caddy validation hoặc migration lỗi: không rollout và không đổi LKG.
- Rollout/public verification lỗi: LKG không đổi; không tự rollback, restore hay
  downgrade database. Người vận hành phải đánh giá thủ công trạng thái thực tế.
- Muốn chặn release tiếp theo: đặt `AUTO_DEPLOY_PRODUCTION=false`. Việc đổi công
  tắc không huỷ job production đang chạy.
