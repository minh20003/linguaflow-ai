import Link from "next/link";

const sections = [
  ["Dịch vụ này làm gì", "LinguaFlow dịch tin nhắn trong cuộc trò chuyện sang ngôn ngữ mà mỗi người nhận đã chọn để đọc, có tham chiếu các tin nhắn gần nhất làm ngữ cảnh."],
  ["Về chất lượng bản dịch", "Bản dịch do mô hình ngôn ngữ tạo ra và có thể sai. Khi đường dịch chính thất bại, hệ thống chuyển sang nhà cung cấp dự phòng; nếu vẫn không dịch được thì gửi nguyên văn bản gốc. Với nội dung quan trọng, hãy đối chiếu bản gốc thay vì chỉ dựa vào bản dịch."],
  ["Bạn có trách nhiệm", "Không gửi nội dung vi phạm pháp luật, quấy rối hoặc xâm phạm quyền của người khác. Không gửi thông tin cá nhân nhạy cảm và giữ an toàn cho thông tin đăng nhập của mình."],
  ["Tài khoản", "Đây là môi trường học tập và phát triển. Nhóm phát triển có thể xoá tài khoản hoặc dữ liệu trong quá trình phát triển, kể cả không báo trước; đây không phải môi trường vận hành thật."],
];

export default function TermsPage() {
  return <main className="min-h-screen bg-slate-50 px-4 py-10 text-slate-800 sm:px-6"><article className="mx-auto max-w-3xl rounded-2xl border border-slate-200 bg-white p-6 shadow-sm sm:p-10"><p className="text-sm font-semibold text-indigo-600">LinguaFlow</p><h1 className="mt-1 text-3xl font-bold tracking-tight">Điều khoản dịch vụ</h1><p className="mt-2 text-sm text-slate-500">Áp dụng cho bản MVP dùng trong học phần.</p><div className="mt-7 rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm leading-6 text-amber-900">LinguaFlow là sản phẩm của một bài tập môn học, do nhóm sinh viên phát triển. Hệ thống được cung cấp <strong>nguyên trạng, không kèm bảo đảm</strong>, và có thể ngừng hoạt động hoặc mất dữ liệu bất cứ lúc nào.</div><div className="mt-8 space-y-7">{sections.map(([title, text]) => <section key={title}><h2 className="text-lg font-bold">{title}</h2><p className="mt-2 text-sm leading-6 text-slate-600">{text}</p></section>)}</div><Link href="/register" className="mt-10 inline-flex text-sm font-semibold text-indigo-600 hover:underline">← Quay lại đăng ký</Link></article></main>;
}
