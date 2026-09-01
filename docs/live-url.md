# Deliverable #5: Live URL & Deployment Endpoints

**Dự án:** LinguaFlow (P-217) · **Nhóm thực hiện:** 4U  
**Trạng thái Triển khai:** Hoạt động ổn định trên Ubuntu VPS + Docker Compose + Caddy Reverse Proxy + PostgreSQL pgvector.

---

## 1. Địa chỉ Truy cập Sản phẩm (Live URLs)

| Dịch vụ | URL Trực tuyến | Ghi chú |
|---|---|---|
| **Web Chat Application (Frontend)** | [https://c3-lingua-flow-217.dquangminh2003.id.vn](https://c3-lingua-flow-217.dquangminh2003.id.vn) | Next.js Production Build |
| **Backend REST & WebSocket API** | [https://api-c3-lingua-flow-217.dquangminh2003.id.vn](https://api-c3-lingua-flow-217.dquangminh2003.id.vn) | FastAPI + Uvicorn Async |
| **Health Check Endpoint** | [https://api-c3-lingua-flow-217.dquangminh2003.id.vn/health](https://api-c3-lingua-flow-217.dquangminh2003.id.vn/health) | Trả về HTTP 200 OK & DB Status |
| **API Documentation** | [https://api-c3-lingua-flow-217.dquangminh2003.id.vn/docs](https://api-c3-lingua-flow-217.dquangminh2003.id.vn/docs) | OpenAPI Interactive Swagger Docs |

---

## 2. Tài khoản Trải nghiệm Nhanh (Demo Accounts)

Hệ thống có sẵn các tài khoản thử nghiệm:

| Email | Password | Ngôn ngữ dịch | Vai trò |
|---|---|---|---|
| `member@test.com` | `testpass123` | English (`en`) | Thành viên |
| `admin@test.com` | `adminpass123` | Tiếng Việt (`vi`) | Quản trị viên |

---

## 3. Tài liệu Vận hành & Hướng dẫn Deploy Chi tiết
- [Tài liệu Triển khai Kỹ thuật (docs/DEPLOY.md)](DEPLOY.md)
- [Tài liệu Vận hành Tính năng (docs/FEATURE_OPERATIONS.md)](FEATURE_OPERATIONS.md)
