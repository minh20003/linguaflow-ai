# Submission: Day 23 Product Metrics Lab Framework

- **Họ và Tên:** Nguyễn Thị Trà My
- **Mã Học Viên (MSSV):** 2A202601026
- **Dự án chọn phân tích:** **LinguaFlow** — Realtime Multilingual Chat with Context-Aware AI Translation
- **Link Metrics Pack:** [Metrics Pack Document](./metrics-pack.md) *(Bản trình bày chi tiết 00–07)*
- **AI Support Log:** [AI Support Log](./ai-support-log.md)

---

## 🌟 Điều tôi mang về áp dụng cho dự án LinguaFlow thực tế

1. **Phân biệt rành rọt Core Action với Thao tác UI & Output Hệ thống**:
   - Trước lab này, team dễ sa vào cái bẫy đo *Số lượt gửi tin nhắn* hoặc *Số lượt mở app*. Qua bài lab, tôi nhận ra đó chỉ là thao tác giao diện. Output của hệ thống (AI tạo ra bản dịch) cũng chưa phải value. Core Action thực sự phải là **Thực hiện thành công 1 lượt giao tiếp song ngữ (multilingual_message_exchanged)** — nơi người nhận đọc hiểu bản dịch ngữ cảnh và tương tác lại.

2. **Xác định Cadence từ Nature thay vì thói quen Dashboard**:
   - Giao tiếp công việc liên ngôn ngữ không xảy ra liên tục 24/7 như ứng dụng mạng xã hội giải trí. Nhịp tự nhiên của nó gắn liền với tiến độ công việc/dự án (2–3 ngày/lần hoặc 3–4 lần/tuần). Do đó, việc áp đặt Daily Retention (D1, D7) là sai lệch bản chất. **Weekly Retention (W1, W2, W4) với Threshold >= 2 lượt/tuần** mới phản ánh đúng sức khỏe thực của sản phẩm.

3. **Thiết lập North Star Metric có Quality Threshold & Counter-Metric khắt khe**:
   - North Star Metric không thể chỉ là con số lượng thuần túy (như *Tổng số tin nhắn*). NSM của LinguaFlow được thiết kế là **Weekly Successful Multilingual Conversations (WSMC)** — yêu cầu cuộc hội thoại phải có tương tác 2 chiều và tỷ lệ lỗi dịch < 5%. Đồng thời, việc cài đặt Counter-Metric **Translation Flagged Rate** giúp bảo vệ sản phẩm khỏi bẫy metric chính tăng nhưng trải nghiệm tệ đi (người dùng chat nhiều hơn chỉ vì AI dịch sai làm họ phải đính chính).

4. **Product Loop dựa vào Context Memory thay vì Spam Notification**:
   - Sản phẩm giữ chân người dùng (Retention) nhờ **tích luỹ ngữ cảnh dự án & từ vựng chuyên ngành (Context Memory)** qua từng lượt chat. Càng dùng nhiều, AI dịch càng chuẩn thuật ngữ của team, tạo ra rào cản chuyển đổi (switching cost) và giá trị lặp lại thực sự (Reason to return tự nhiên).

---

## 📁 Cấu trúc Repository

``nTrack1_Day23_2A202601026_NguyenThiTraMy/
├── README.md          # Thông tin cá nhân, dự án chọn, bài học thực tế & link tài liệu
├── metrics-pack.md    # Bộ Metrics Pack đầy đủ 8 mục (00 đến 07) theo chuẩn Day 23
└── ai-support-log.md  # Nhật ký tương tác và phản biện với AI
``n