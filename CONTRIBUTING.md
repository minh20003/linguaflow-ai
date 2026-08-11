# QUY ĐỊNH LÀM VIỆC NHÓM

**Dự án:** LinguaFlow (P-217) · **Nhóm thực hiện:** 4U
**Phiên bản:** 1.0 · **Ngày cập nhật:** 10/08/2026 · **Trạng thái:** Đang áp dụng

---

## Phạm vi và hiệu lực

Tài liệu này chuẩn hoá quy định làm việc của nhóm, tổng hợp từ `docs/T217/1. T217 - Project Chart + Report.xlsx` (sheet *Quy Định*, *Quy Định Nội Bộ*) và `docs/T217/2. T217 - Team Project Management.xlsx`.

Đây là nguồn tham chiếu duy nhất về quy trình làm việc. Trường hợp có khác biệt với các tệp Excel nêu trên, áp dụng theo tài liệu này.

> **Ghi chú:** thư mục `docs/T217/` không được đưa vào kho mã nguồn (khai báo trong `.gitignore`). Các tệp Excel nêu trên được lưu trữ và chia sẻ qua kênh nội bộ của nhóm. Danh mục đầy đủ: xem [`ARCHITECTURE.md`](ARCHITECTURE.md) mục 10.2.

## Mục lục

1. [Thành viên và phân vai](#1-thành-viên-và-phân-vai)
2. [Thời gian làm việc và báo cáo hàng ngày](#2-thời-gian-làm-việc-và-báo-cáo-hàng-ngày)
3. [Kênh liên lạc](#3-kênh-liên-lạc)
4. [Quản lý mã nguồn](#4-quản-lý-mã-nguồn)
5. [Quy trình giao việc](#5-quy-trình-giao-việc)
6. [Tiêu chuẩn chất lượng](#6-tiêu-chuẩn-chất-lượng)
7. [Ra quyết định và xử lý bất đồng](#7-ra-quyết-định-và-xử-lý-bất-đồng)
8. [Báo cáo và quy trình leo thang](#8-báo-cáo-và-quy-trình-leo-thang)
9. [Nguyên tắc làm việc](#9-nguyên-tắc-làm-việc)

---

## 1. Thành viên và phân vai

| Họ tên | Vai trò chính | Vai trò phụ | Cam kết |
|---|---|---|---|
| Nguyễn Thị Trà My | Team Lead / AI | Backend | 40 giờ/tuần |
| Nguyễn Văn Hưởng | AI | Knowledge Base | 40 giờ/tuần |
| Nguyễn Ngọc Thuận | Frontend | Tester | 40 giờ/tuần |
| Đinh Quang Minh | Backend | Knowledge Base | 40 giờ/tuần |

**Mentor phụ trách:** Đoàn Viết Thắng
**Kho mã nguồn:** https://github.com/AI20K-Build-Phase-Cohort-3/P-217.git

## 2. Thời gian làm việc và báo cáo hàng ngày

| Hạng mục | Quy định |
|---|---|
| Thời gian làm việc | Thứ Hai đến Thứ Bảy, tối thiểu 40 giờ/tuần |
| Khung giờ bắt buộc trực tuyến | 09:00-11:30 và 14:00-17:00 |
| Daily standup | 09:00 hàng ngày, gửi trên Discord. Nội dung: công việc đã hoàn thành, công việc trong ngày, vướng mắc |
| Mentor Meeting | Tối Thứ Tư (toàn khoá, 90 phút) và Thứ Bảy (riêng nhóm, 45 phút). Bắt buộc tham dự |
| Nghỉ phép | Thông báo Team Lead trước tối thiểu 24 giờ. Tối đa 2 ngày trong 6 tuần, không nghỉ liên tiếp gần thời điểm bàn giao. Trường hợp vắng mặt vẫn phải gửi standup |

## 3. Kênh liên lạc

| Kênh | Phạm vi sử dụng | Thời gian phản hồi |
|---|---|---|
| Discord `#team-217` | Trao đổi hàng ngày, hỏi đáp nhanh | Tối đa 2 giờ trong giờ làm việc |
| Discord `#team-217-Thảo luận` | Daily standup dạng văn bản | Gửi trước 09:30 |
| GitHub Issues / Pull Request | Thảo luận kỹ thuật, báo lỗi, đề xuất tính năng | Tối đa 1 ngày làm việc |
| Google Meet | Nội dung cần trao đổi trực tiếp | Hẹn trước; ghi lại kết luận lên Discord sau cuộc họp |
| Email | Liên hệ mentor và đối tác, nội dung chính thức | Tối đa 24 giờ |

Khi cần phản hồi từ một thành viên cụ thể, sử dụng chức năng tag trực tiếp và mô tả rõ vấn đề.

## 4. Quản lý mã nguồn

### 4.1. Nhánh

| Hạng mục | Quy định |
|---|---|
| Nhánh chính | `main` — chỉ merge mã nguồn đã qua review và kiểm thử. Không push trực tiếp |
| Nhánh tính năng | `feature/<tên-tính-năng>` |
| Nhánh sửa lỗi | `bugfix/<tên-lỗi>` |
| Nhánh sửa khẩn cấp | `hotfix/<tên-lỗi>` |

### 4.2. Commit message

Áp dụng chuẩn [Conventional Commits](https://www.conventionalcommits.org/), nội dung viết bằng tiếng Anh:

```
feat: add websocket routing for group chat
fix: correct source_language update after detection
refactor: extract llm provider factory
docs: update api contract for translation_id
test: add unit tests for translate node
chore: bump langchain-groq version
```

> Quy định này thay thế hướng dẫn trong tệp Excel gốc. Hướng dẫn cũ không nhất quán: quy định viết tiếng Anh nhưng ví dụ minh hoạ sử dụng tiền tố tiếng Việt (`Thêm:`, `Sửa:`, `Cập nhật:`).

### 4.3. Pull Request và review

| Hạng mục | Quy định |
|---|---|
| Phạm vi áp dụng | Bắt buộc với mọi thay đổi mã nguồn |
| Nội dung mô tả | Thay đổi gì, lý do, phương pháp kiểm thử. Liên kết issue nếu có |
| Kích thước | Dưới 400 dòng thay đổi. Vượt ngưỡng phải tách nhỏ |
| Người review | Tối thiểu 1 thành viên khác |
| Thời gian review | Tối đa 4 giờ làm việc |
| Sau khi merge | Xoá nhánh đã merge |

### 4.4. Tệp không đưa vào kho mã nguồn

Không commit: `node_modules`, `.env`, API key, tệp build, tệp tạm. Các mục này phải được khai báo trong `.gitignore`.

## 5. Quy trình giao việc

1. Team Lead là người phân công công việc. Trường hợp Team Lead không sẵn sàng, thành viên được uỷ quyền thực hiện thay.
2. Mỗi đầu việc phải có một người chịu trách nhiệm chính, thời hạn cụ thể và kết quả mong đợi được mô tả rõ ràng.
3. Người nhận việc xác nhận trong vòng 2 giờ. Trường hợp chưa rõ yêu cầu, cần trao đổi lại ngay thay vì tự suy đoán.
4. Khi dự kiến không kịp thời hạn, thông báo Team Lead trước tối thiểu 4 giờ.
5. Cập nhật trạng thái công việc qua GitHub Issues và daily standup.

## 6. Tiêu chuẩn chất lượng

| Hạng mục | Tiêu chuẩn |
|---|---|
| Mã nguồn | Tên biến và tên hàm mang ngữ nghĩa rõ ràng; chú thích tại các đoạn xử lý phức tạp; không để lại mã không sử dụng |
| Kiểm thử | Mỗi tính năng chính có tối thiểu một test cho luồng thành công và một test cho luồng lỗi |
| Tài liệu | `README.md`, `ARCHITECTURE.md`, `docs/CONTRACT.md` cập nhật đồng thời với thay đổi thiết kế |
| Hiệu năng | API phản hồi dưới 1 giây; dịch thuật dưới 1 giây (NFR-01); trang chính tải dưới 3 giây. Trường hợp không đạt phải ghi nhận nguyên nhân và kế hoạch tối ưu |
| Bảo mật | Không hard-code API key và mật khẩu; sử dụng `.env`; kiểm tra hợp lệ toàn bộ dữ liệu đầu vào từ người dùng |
| Giao diện | Không có lỗi hiển thị ảnh hưởng khả năng sử dụng (vỡ bố cục, chồng lấn văn bản, thành phần không tương tác được) |

## 7. Ra quyết định và xử lý bất đồng

### 7.1. Quy trình

1. Các bên trình bày quan điểm kèm căn cứ.
2. Lắng nghe và ghi nhận quan điểm đối lập.
3. Xác định điểm thống nhất.
4. Trường hợp không đạt được đồng thuận, Team Lead ra quyết định cuối cùng.

### 7.2. Thẩm quyền quyết định

| Loại vấn đề | Người quyết định |
|---|---|
| Kỹ thuật | Thành viên có chuyên môn phù hợp nhất với vấn đề |
| Tiến độ và phạm vi | Team Lead |
| Ảnh hưởng toàn nhóm | Biểu quyết toàn nhóm; Team Lead quyết định khi kết quả cân bằng |

Sau khi quyết định được ban hành, toàn nhóm thực hiện thống nhất. Bất đồng kéo dài quá 2 ngày không giải quyết được phải báo cáo mentor.

## 8. Báo cáo và quy trình leo thang

| Tình huống | Hành động |
|---|---|
| Vướng mắc kỹ thuật | Đăng lên Discord `#team-217`. Mentor phản hồi trong 24 giờ |
| Vướng mắc với đối tác | Báo cáo mentor ngay, không tự xử lý |
| Báo cáo tuần | Tổng hợp trước Mentor Meeting Thứ Tư theo mẫu sheet *Báo Cáo Tuần*. Nội dung bắt buộc: tiến độ, chỉ số, vướng mắc, kế hoạch tuần sau, tối thiểu một ảnh chụp minh chứng |
| Thành viên không hoàn thành trách nhiệm | Cảnh báo lần thứ nhất; tiếp diễn thì tổ chức họp với mentor |

## 9. Nguyên tắc làm việc

| Nguyên tắc | Nội dung |
|---|---|
| Trách nhiệm cá nhân | Mỗi thành viên chịu trách nhiệm hoàn thành phần việc được giao |
| Báo cáo trung thực | Báo cáo đúng thực trạng, kể cả khi kết quả chưa đạt yêu cầu. Việc che giấu vấn đề gây hậu quả lớn hơn bản thân vấn đề |
| Ưu tiên sản phẩm vận hành được | Sản phẩm hoạt động được với người dùng thật có mức ưu tiên cao hơn mã nguồn hoàn thiện nhưng chưa kịp bàn giao |
| Khắc phục nhanh | Sai sót được ghi nhận và khắc phục sớm; không quy trách nhiệm cá nhân |
| Tôn trọng thời gian | Tham dự đúng giờ các cuộc họp đã thống nhất |
