# Deliverable #6: Video Demo Sản phẩm

**Dự án:** LinguaFlow (P-217) · **Nhóm thực hiện:** 4U  

---

## 1. Video Demo

Video minh hoạ toàn bộ quá trình vận hành của LinguaFlow được lưu trữ trực tiếp trong kho mã nguồn:

- **Tệp video nội bộ trong repository**: [`presentation/video_demo.mp4`](../presentation/video_demo.mp4) 

---

## 2. Nguồn nội dung thể hiện trong Video

Video minh hoạ 3 nhóm tính năng cốt lõi:

1. **Dịch thuật Realtime Đa ngôn ngữ (Pha 1)**:
   - Nhắn tin 1-1 và Chat nhóm song ngữ/đa ngữ (Tiếng Việt, Tiếng Anh, Tiếng Nhật).
   - Tự động nhận diện ngôn ngữ nguồn, duy trì ngữ cảnh 3-5 tin nhắn gần nhất để giải quyết đại từ/chủ ngữ bị lược.
   - Chuyển đổi linh hoạt giữa bản dịch và văn bản gốc, phản hồi và sửa đổi bản dịch.
   - Tin nhắn thoại (Voice Message) tự động chuyển văn bản bằng Gemini 3.5 Transcribe và dịch ngữ cảnh.

2. **Trợ lý AI Cá nhân — Assistant Agent (Phát triển bổ sung ở pha sau này)**:
   - Tương tác chủ động với Trợ lý AI qua hội thoại.
   - Tự động trích xuất cam kết/lịch hẹn từ lịch sử chat thành thẻ đề xuất sự kiện (Action Proposals).
   - Cơ chế duyệt Human-in-the-Loop: Người dùng duyệt/từ chối kèm chú thích trước khi sự kiện được ghi chính thức.
   - Đồng bộ 2 chiều với Google Calendar và hộp nhiệm vụ cá nhân (Task Inbox).

3. **Giao diện Quản trị & Giám sát**:
   - Trang Admin thống kê chất lượng dịch và kiểm tra sức khỏe hệ thống real-time.
