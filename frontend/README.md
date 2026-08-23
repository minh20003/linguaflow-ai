# LinguaChat Frontend

Next.js App Router frontend for authentication and real-time multilingual chat.

## Commands

```bash
npm install
npm run dev
npm run lint
npx tsc --noEmit --incremental false
npm run build
```

The development app is available at `http://localhost:3000`; the chat route is
`/chat`.

## Source layout

```text
src/
  app/                 Route definitions and layouts
  config/              Public runtime configuration
  features/auth/       Authentication UI, API client and session helpers
  features/chat/       Chat UI, REST/WebSocket clients and styles
```

## Runtime configuration

| Biến | Bắt buộc | Ý nghĩa |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | Có (khi không phải localhost:8000) | Gốc địa chỉ backend, ví dụ `https://api.dquangminh2003.id.vn` hoặc `http://localhost:8000` |
| `NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID` | Không (bắt buộc nếu dùng Google Sign-In) | Google OAuth 2.0 Web Client ID, phải khớp với `GOOGLE_OAUTH_CLIENT_ID` bên backend |

Keep route files thin. Feature-specific code belongs under its feature.

## Docker

The production image is a Next.js standalone server. Build and run it with:

## Google Sign-In

Google Sign-In (Batch G) sử dụng Google Identity Services (GIS) ID-token flow.
Origin của trang (`http://localhost:3000` hoặc `https://agent.dquangminh2003.id.vn`)
phải được thêm vào *Authorized JavaScript origins* trên Google Cloud Console.

Backend và frontend phải dùng cùng một **Web Client ID**. GIS trả ID token cho callback trong
trình duyệt; không cần OAuth redirect callback hay Google client secret cho luồng này. Sau khi backend
xác minh chữ ký, issuer, audience, hạn dùng và `email_verified`, Google login hoạt động theo thứ tự:

1. `google_sub` đã tồn tại: đăng nhập tài khoản đó.
2. Chưa có `google_sub`, nhưng email Google đã xác minh trùng tài khoản chưa liên kết: tự liên kết và đăng nhập cùng tài khoản, giữ nguyên mật khẩu và hồ sơ.
3. Không có khớp nào: tạo tài khoản Google-native (`password_hash = NULL`, role `member`) và đăng nhập ngay.

Nếu email đã thuộc một `google_sub` khác, backend trả conflict và không tự động đổi liên kết. Tài khoản
Google-native không thể hủy liên kết Google khi chưa có mật khẩu, tránh mất phương thức đăng nhập duy nhất.

## Docker

The production image is a Next.js standalone server. Build and run it with:

```bash
NEXT_PUBLIC_API_URL=http://localhost:8000 docker compose up --build
```

`NEXT_PUBLIC_API_URL` must point to the API address available from the visitor's
browser, not a Docker-only service hostname.
