import type { Metadata } from "next";
import Link from "next/link";
import Logo from "@/shared/ui/Logo";
import styles from "../legal.module.css";

export const metadata: Metadata = {
  title: "Chính sách riêng tư — LinguaFlow",
  description: "Dữ liệu nào được lưu, ai đọc được, và nội dung tin nhắn đi tới những dịch vụ nào.",
};

/**
 * Written from `ARCHITECTURE.md` section 6, not from a template.
 *
 * The point of the page is section 6.4: translating a message means sending it
 * to a third party, and the person typing it deserves to know that before they
 * type. A privacy page that omitted this would be worse than no page.
 */
export default function PrivacyPage() {
  return (
    <main className={styles.page}>
      <article className={styles.sheet}>
        <Link className={styles.brand} href="/login">
          <Logo size={24} />
          LinguaFlow
        </Link>

        <h1>Chính sách riêng tư</h1>
        <p className={styles.updated}>Áp dụng cho bản MVP dùng trong học phần.</p>

        <p className={styles.callout}>
          LinguaFlow là bài tập của môn học, không phải dịch vụ thương mại.
          <strong> Đừng gửi thông tin thật hoặc nhạy cảm qua hệ thống này.</strong> Môi
          trường phát triển dùng SQLite không mã hoá, và nội dung tin nhắn được gửi
          tới các dịch vụ bên ngoài như mô tả bên dưới.
        </p>

        <h2>Dữ liệu được lưu</h2>
        <p>
          Toàn bộ nội dung hội thoại — cả bản gốc lẫn bản dịch — được lưu dài hạn để
          bạn tra cứu lại lịch sử. Hệ thống không giữ một kho ngữ cảnh riêng: phần
          ngữ cảnh đưa cho mô hình dịch chỉ là kết quả truy vấn 3–5 tin nhắn gần nhất
          trong chính cuộc trò chuyện đó.
        </p>
        <p>
          Tài khoản lưu email, tên đăng nhập, tên hiển thị và ngôn ngữ bạn chọn để
          đọc. Mật khẩu chỉ lưu dưới dạng băm, không bao giờ lưu bản rõ.
        </p>

        <h2>Ai đọc được</h2>
        <ul>
          <li>Quyền truy cập được kiểm tra theo từng cuộc trò chuyện và từng người dùng.</li>
          <li>Khoá API và bí mật nằm trong tệp cấu hình môi trường, không nằm trong mã nguồn.</li>
          <li>
            Bản triển khai thật bật mã hoá dữ liệu khi lưu trữ. Môi trường phát triển
            thì không — đó là lý do cảnh báo ở đầu trang.
          </li>
        </ul>

        <h2>Nội dung tin nhắn rời khỏi hệ thống ở đâu</h2>
        <p>
          Dịch một tin nhắn nghĩa là gửi nó cho một dịch vụ bên ngoài. Có ba kênh, và
          cả ba đều tắt được bằng cấu hình — nhưng tắt kênh đầu tiên thì không còn
          dịch được nữa.
        </p>
        <table className={styles.table}>
          <thead>
            <tr>
              <th>Kênh</th>
              <th>Gửi đi những gì</th>
              <th>Ghi chú</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Nhà cung cấp mô hình ngôn ngữ (Groq, DeepSeek, Gemini hoặc OpenAI)</td>
              <td>Tin nhắn của bạn và tối đa 5 tin nhắn gần nhất làm ngữ cảnh</td>
              <td>Theo điều khoản của nhà cung cấp đang được chọn</td>
            </tr>
            <tr>
              <td>Provider dịch dự phòng (Google Translate qua thư viện `deep-translator`)</td>
              <td>Toàn văn tin nhắn</td>
              <td>
                Dùng endpoint web không chính thức, <strong>không có hợp đồng xử lý
                dữ liệu</strong>. Chỉ kích hoạt khi kênh trên thất bại.
              </td>
            </tr>
            <tr>
              <td>Langfuse (ghi vết để đo chất lượng)</td>
              <td>Toàn bộ prompt và kết quả, tức gồm cả tin nhắn lẫn ngữ cảnh</td>
              <td>Tắt hoàn toàn khi không cấu hình khoá</td>
            </tr>
          </tbody>
        </table>

        <h2>Xoá dữ liệu</h2>
        <p>
          Tính năng tự xoá hội thoại theo yêu cầu chưa có trong bản MVP. Nếu bạn cần
          xoá dữ liệu, hãy liên hệ nhóm phát triển.
        </p>

        <Link className={styles.back} href="/register">← Quay lại đăng ký</Link>
      </article>
    </main>
  );
}
