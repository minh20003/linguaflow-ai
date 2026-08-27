# 🤖 AI SUPPORT LOG — DAY 23 PRODUCT METRICS LAB

**Học viên:** Nguyễn Thị Trà My  
**MSSV / MHV:** 2A202601026  
**Dự án:** LinguaFlow  

---

### 1. AI đã giúp tôi ở đâu?

* **Brainstorm & Phản biện ứng viên Core Action:** AI giúp tôi liệt kê các hành vi tiềm năng trong một ứng dụng nhắn tin đa ngôn ngữ (mở app, gửi tin nhắn, bật dịch tự động, phản hồi bản dịch). Đồng thời, AI đóng vai một "PM khó tính" để phản biện vì sao "gửi tin nhắn gốc" chỉ là thao tác giao diện, còn "AI tạo ra bản dịch" mới chỉ là output hệ thống.
* **Gợi ý tên Event & Acceptance Criteria:** AI đề xuất chuẩn hóa tên event theo dạng `object_action` (ví dụ: `multilingual_message_exchanged`, `translation_flagged`) và gợi ý các trường dữ liệu quan trọng để đưa vào Acceptance Criteria chống bẫy duplicate event khi reconnect WebSocket.
* **Cấu trúc bộ Retention 6 thành phần:** AI hỗ trợ kiểm tra tính đầy đủ của 6 thành phần trong định nghĩa Retention (Unit, Cohort Entry, Return Event, Window, Threshold, Segment), đảm bảo không bị thiếu sót thành phần nào theo đúng slide giảng bài Day 23.

---

### 2. AI sai, hời hợt hoặc đề xuất metric sai nature ở đâu?

* **Đề xuất Cadence kiểu lối mòn Dashboard (Daily DAU/D1 Retention):** Ban đầu, AI có xu hướng gợi ý đo lường "Daily Active Users (DAU)" và "D1/D7 Retention" cho LinguaFlow chỉ vì đây là các chỉ số phổ biến trên các dashboard mẫu. Tôi đã phản biện rằng: Giao tiếp công việc song ngữ giữa các chi nhánh đa quốc gia phát sinh theo nhịp dự án (2–3 ngày/lần), không phải app mạng xã hội lướt hàng ngày. Do đó, ép Daily Retention là sai lệch bản chất tự nhiên (Nature).
* **Đề xuất North Star Metric thiếu Quality Threshold:** AI ban đầu gợi ý North Star Metric là "Tổng số tin nhắn được dịch hàng tuần (Total Weekly Translated Messages)". Chỉ số này là một bẫy nguy hiểm vì nó hoàn toàn mang tính lượng (volume), không có chất lượng. Người dùng có thể phải gửi rất nhiều tin nhắn chỉ vì AI dịch sai, dịch ngô nghê làm họ phải đính chính liên tục.
* **Đề xuất Product Loop dựa vào External Notification (Spam):** AI từng gợi ý vòng lặp giữ chân người dùng bằng cách "Gửi Push Notification nhắc nhở user vào chat". Tôi đã loại bỏ gợi ý này vì notification chỉ là Nurture, không phải lý do quay lại tự nhiên (Reason to return). Vòng lặp sản phẩm thật sự phải dựa trên việc hệ thống tích luỹ ngữ cảnh (Context Memory & Domain Glossary).

---

### 3. Tôi đã tự sửa hoặc quyết định lại điều gì?

* **Chốt Core Action chuẩn chỉnh:** Tôi quyết định chọn Core Action là **"Thực hiện thành công 1 lượt giao tiếp song ngữ" (`multilingual_message_exchanged`)** — yêu cầu phải có cả người gửi, bản dịch AI ngữ cảnh và sự tiếp nhận/phản hồi từ người nhận.
* **Thiết lập lại North Star Metric (WSMC):** Tôi chủ động xây dựng lại NSM theo đúng công thức 3 thành phần: **Weekly Successful Multilingual Conversations (WSMC)** với Quality Threshold khắt khe ($< 5\%$ tin nhắn bị báo lỗi dịch và phải có tương tác 2 chiều).
* **Bổ sung Counter-Metric sắc bén:** Tôi tự đưa vào chỉ số **Translation Flagged / Correction Rate** và **P95 AI Translation Latency** để làm đối trọng với NSM, đảm bảo team không chạy theo số lượng tin nhắn mà đánh đổi trải nghiệm thời gian thực và độ chính xác dịch thuật.
* **Viết Acceptance Criteria chống bẫy kĩ thuật:** Tôi tự quy định rõ tiêu chí nghiệm thu cho tracking event: không được bắn trùng event `multilingual_message_exchanged` khi user reload trang hoặc reconnect WebSocket, đảm bảo dữ liệu analytics hoàn toàn sạch và đáng tin cậy.
