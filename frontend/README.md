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
| `NEXT_PUBLIC_API_URL` | Có (khi không phải localhost:8000) | Gốc địa chỉ backend, ví dụ `https://linguaflow.up.railway.app` |

**`NEXT_PUBLIC_*` được nhúng vào mã JavaScript lúc build, không đọc lúc chạy.**
Đổi giá trị rồi mà không build lại thì bản cũ vẫn trỏ về địa chỉ cũ — đây là lỗi
dễ mất thời gian nhất khi triển khai. Địa chỉ WebSocket suy ra từ chính biến này
(`shared/lib/use-websocket.ts`), `http` thành `ws` và `https` thành `wss`, nên
không có biến thứ hai phải nhớ.

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
