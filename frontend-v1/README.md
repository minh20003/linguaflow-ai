# LinguaFlow — giao diện web

Next.js 16 (App Router) + React 19. Đây là toàn bộ phần người dùng nhìn thấy:
đăng ký/đăng nhập, danh sách hội thoại, khung chat và trang cài đặt ngôn ngữ.
Backend nằm ở thư mục gốc của kho (FastAPI), chạy riêng.

## Chạy trên máy

```bash
cp .env.example .env.local     # rồi sửa NEXT_PUBLIC_API_URL nếu backend không ở cổng 8000
npm install
npm run dev                    # http://localhost:3000
```

Backend phải chạy sẵn (`make run` ở thư mục gốc) và địa chỉ của trang này phải
nằm trong `CORS_ORIGINS` của backend, nếu không mọi lời gọi API sẽ bị trình duyệt
chặn.

## Biến môi trường

| Biến | Bắt buộc | Ý nghĩa |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | Có (khi không phải localhost:8000) | Gốc địa chỉ backend, ví dụ `https://api.dquangminh2003.id.vn` hoặc `http://localhost:8000` |
| `NEXT_PUBLIC_GOOGLE_OAUTH_CLIENT_ID` | Không (bắt buộc nếu dùng Google Sign-In) | Google OAuth 2.0 Web Client ID, phải khớp với `GOOGLE_OAUTH_CLIENT_ID` bên backend |

**`NEXT_PUBLIC_*` được nhúng vào mã JavaScript lúc build, không đọc lúc chạy.**
Đổi giá trị rồi mà không build lại thì bản cũ vẫn trỏ về địa chỉ cũ — đây là lỗi
dễ mất thời gian nhất khi triển khai. Địa chỉ WebSocket suy ra từ chính biến này
(`shared/lib/use-websocket.ts`), `http` thành `ws` và `https` thành `wss`, nên
không có biến thứ hai phải nhớ.

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

## Lệnh

```bash
npm run dev      # máy chủ phát triển
npm run build    # bản dựng production
npm run start    # chạy bản đã dựng
npm run lint     # eslint
npx tsc --noEmit # kiểm tra kiểu, chạy trước khi mở PR
```

## Cấu trúc

```
src/app/         # định tuyến: (auth), chat, settings, (legal)
src/features/    # auth, chat, settings — mỗi thư mục một miền nghiệp vụ
src/shared/lib/  # gọi API, phiên đăng nhập, WebSocket, hằng số
src/shared/ui/   # thành phần giao diện dùng lại
```

Cách triển khai lên Vercel: xem `docs/DEPLOY.md` ở thư mục gốc.
