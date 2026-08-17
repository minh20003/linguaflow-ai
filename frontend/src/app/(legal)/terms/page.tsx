import type { Metadata } from "next";
import Link from "next/link";
import Logo from "@/shared/ui/Logo";
import styles from "../legal.module.css";

export const metadata: Metadata = {
  title: "Điều khoản dịch vụ — LinguaFlow",
  description: "Phạm vi sử dụng, giới hạn trách nhiệm và chất lượng bản dịch của LinguaFlow.",
};

export default function TermsPage() {
  return (
    <main className={styles.page}>
      <article className={styles.sheet}>
        <Link className={styles.brand} href="/login">
          <Logo size={24} />
          LinguaFlow
        </Link>

        <h1>Điều khoản dịch vụ</h1>
        <p className={styles.updated}>Áp dụng cho bản MVP dùng trong học phần.</p>

        <p className={styles.callout}>
          LinguaFlow là sản phẩm của một bài tập môn học, do nhóm sinh viên phát
          triển. Hệ thống được cung cấp <strong>nguyên trạng, không kèm bảo đảm</strong>,
          và có thể ngừng hoạt động hoặc mất dữ liệu bất cứ lúc nào.
        </p>

        <h2>Dịch vụ này làm gì</h2>
        <p>
          LinguaFlow dịch tin nhắn trong cuộc trò chuyện sang ngôn ngữ mà mỗi người
          nhận đã chọn để đọc, có tham chiếu vài tin nhắn gần nhất làm ngữ cảnh.
        </p>

        <h2>Về chất lượng bản dịch</h2>
        <p>
          Bản dịch do mô hình ngôn ngữ tạo ra và <strong>có thể sai</strong>. Khi
          đường dịch chính thất bại, hệ thống chuyển sang provider dự phòng, và nếu
          vẫn không dịch được thì gửi nguyên văn bản gốc — tin nhắn không bao giờ bị
          mất, nhưng có thể tới người nhận ở dạng chưa dịch.
        </p>
        <p>
          Mỗi tin nhắn đều xem lại được bản gốc. Với nội dung quan trọng, hãy đối
          chiếu bản gốc thay vì chỉ tin vào bản dịch. Không dùng LinguaFlow cho các
          tình huống mà một câu dịch sai gây hậu quả nghiêm trọng.
        </p>

        <h2>Bạn có trách nhiệm</h2>
        <ul>
          <li>Không gửi nội dung vi phạm pháp luật, quấy rối hoặc xâm phạm quyền của người khác.</li>
          <li>Không gửi thông tin cá nhân nhạy cảm — xem <Link href="/privacy">Chính sách riêng tư</Link> để biết nội dung tin nhắn đi tới đâu.</li>
          <li>Giữ an toàn cho thông tin đăng nhập của mình.</li>
        </ul>

        <h2>Tài khoản</h2>
        <p>
          Nhóm phát triển có thể xoá tài khoản hoặc dữ liệu trong quá trình phát
          triển, kể cả không báo trước, vì đây là môi trường học tập chứ không phải
          môi trường vận hành thật.
        </p>

        <Link className={styles.back} href="/register">← Quay lại đăng ký</Link>
      </article>
    </main>
  );
}
