import os
from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)

# High-Contrast Bright & Clear Theme
BG_LIGHT = RGBColor(248, 249, 252)       # Clean bright off-white
HEADER_NAVY = RGBColor(15, 23, 60)       # Deep rich navy
TEXT_DARK = RGBColor(30, 38, 55)         # High contrast dark text
ACCENT_BLUE = RGBColor(12, 100, 235)     # Vibrant blue accent
ACCENT_PURPLE = RGBColor(105, 45, 210)   # Deep purple accent
GOLD_DARK = RGBColor(195, 120, 0)        # Visible rich gold/orange
CARD_BORDER = RGBColor(220, 225, 240)

blank_slide_layout = prs.slide_layouts[6]

def set_slide_background(slide):
    background = slide.background
    fill = background.fill
    fill.solid()
    fill.fore_color.rgb = BG_LIGHT

def add_header(slide, title_text, subtitle_text):
    txBox = slide.shapes.add_textbox(Inches(0.8), Inches(0.4), Inches(11.7), Inches(1.3))
    tf = txBox.text_frame
    tf.word_wrap = True
    
    p = tf.paragraphs[0]
    p.text = title_text
    p.font.size = Pt(32)
    p.font.bold = True
    p.font.color.rgb = HEADER_NAVY
    
    p2 = tf.add_paragraph()
    p2.text = subtitle_text
    p2.font.size = Pt(16)
    p2.font.bold = True
    p2.font.color.rgb = ACCENT_BLUE

# Slide 1: Title
slide1 = prs.slides.add_slide(blank_slide_layout)
set_slide_background(slide1)
tx1 = slide1.shapes.add_textbox(Inches(1.0), Inches(1.8), Inches(11.3), Inches(4.5))
tf1 = tx1.text_frame
tf1.word_wrap = True

p = tf1.paragraphs[0]
p.text = "LinguaFlow (P-217)"
p.font.size = Pt(50)
p.font.bold = True
p.font.color.rgb = ACCENT_BLUE

p = tf1.add_paragraph()
p.text = "AI Agent Dịch tin nhắn Real-time & Trợ lý Hội thoại Thông minh"
p.font.size = Pt(26)
p.font.bold = True
p.font.color.rgb = HEADER_NAVY

p = tf1.add_paragraph()
p.text = "\nNhóm 4U · VinUni AI20K Build Phase · Pitch Deck & Báo cáo Nghiệm thu"
p.font.size = Pt(18)
p.font.color.rgb = TEXT_DARK

# Slide 2: Pain Points
slide2 = prs.slides.add_slide(blank_slide_layout)
set_slide_background(slide2)
add_header(slide2, "1. Bài toán & Pain Points Thực tế", "Rào cản ngôn ngữ trong giao tiếp ba bên (PM ↔ Dev ↔ Khách hàng quốc tế)")

tx2 = slide2.shapes.add_textbox(Inches(0.8), Inches(1.8), Inches(11.7), Inches(5.3))
tf2 = tx2.text_frame
tf2.word_wrap = True

bullets2 = [
    ("❌ Hiểu sai Ngữ cảnh & Thuật ngữ:", "Từ viết tắt (API, DB, BE, FE, PR, deploy, hotfix) nếu dịch rời rạc theo nghĩa đen sẽ làm sai lệch specification."),
    ("❌ Trải nghiệm Dịch bị đứt đoạn:", "Công cụ ngoài (Google Translate / DeepL) bắt buộc copy-paste liên tục, gây đứt mạch thảo luận."),
    ("❌ Bỏ sót Action Items & Deadline:", "Trong các phòng chat dài, cam kết và thời hạn dễ bị trôi mất mà không có trợ lý trích xuất tự động."),
    ("❌ Rủi ro Bảo mật & Quyền riêng tư (PII):", "Nguy cơ rò rỉ dữ liệu cá nhân, mật khẩu, STK hoặc tin nhắn nội bộ khi sử dụng AI không có Guardrail.")
]
for title, desc in bullets2:
    p = tf2.add_paragraph()
    p.text = title
    p.font.bold = True
    p.font.size = Pt(18)
    p.font.color.rgb = GOLD_DARK
    
    p_desc = tf2.add_paragraph()
    p_desc.text = "   " + desc
    p_desc.font.size = Pt(16)
    p_desc.font.color.rgb = TEXT_DARK

# Slide 3: Market Gap
slide3 = prs.slides.add_slide(blank_slide_layout)
set_slide_background(slide3)
add_header(slide3, "2. Khảo sát Thị trường & Khoảng trống (Market Gap)", "Khoảng trống giữa công cụ truyền thống và nhu cầu làm việc doanh nghiệp")

tx3 = slide3.shapes.add_textbox(Inches(0.8), Inches(1.8), Inches(11.7), Inches(5.3))
tf3 = tx3.text_frame
tf3.word_wrap = True

bullets3 = [
    ("🚀 Real-time WebSocket Streaming:", "Google Translate / DeepL không tích hợp sẵn trong chat UI; LinguaFlow hỗ trợ streaming < 1.5s."),
    ("🎯 Glossary theo Đối tượng đọc (Internal vs Client):", "Dịch linh hoạt theo vị thế đọc (Dev giữ 'deploy', Khách hàng đổi thành 'triển khai')."),
    ("🔄 Human-in-the-Loop Glossary Mining:", "Tự động gom cụm phản hồi người dùng (Cosine >= 0.85) -> Đề xuất thuật ngữ mới có Admin duyệt."),
    ("🔒 Song Agent & Privacy Scope (ADR-30):", "Assistant Agent tích hợp RAG, trích xuất Task & Google Calendar với lớp bảo mật quyền riêng tư tuyệt đối.")
]
for title, desc in bullets3:
    p = tf3.add_paragraph()
    p.text = title
    p.font.bold = True
    p.font.size = Pt(18)
    p.font.color.rgb = ACCENT_BLUE
    
    p_desc = tf3.add_paragraph()
    p_desc.text = "   " + desc
    p_desc.font.size = Pt(16)
    p_desc.font.color.rgb = TEXT_DARK

# Slide 4: Dual Agent Architecture
slide4 = prs.slides.add_slide(blank_slide_layout)
set_slide_background(slide4)
add_header(slide4, "3. Kiến trúc Song Agent (Dual-Agent Architecture)", "Phân tách rõ ràng giữa Dịch thuật Real-time và Trợ lý Quản lý Tác vụ")

tx4 = slide4.shapes.add_textbox(Inches(0.8), Inches(1.8), Inches(11.7), Inches(5.3))
tf4 = tx4.text_frame
tf4.word_wrap = True

bullets4 = [
    ("1️⃣ Translation Agent (Real-time LangGraph Flow):", "Chạy tự động cho mọi tin nhắn; Tích hợp 2-tier detect (langdetect 2ms), context 3-5 tin, audience-aware glossary, và 2-level fallback."),
    ("2️⃣ Assistant Agent (Autonomous Planner & RAG):", "Kích hoạt khi @assistant hoặc chat riêng; Trả lời riêng tư (visibility = 'private'); Trích xuất Task, Reminder, đồng bộ 2 chiều với Google Calendar."),
    ("3️⃣ Hạ tầng dùng chung (Shared Infrastructure):", "PostgreSQL + pgvector (RAG Memory), FastAPI WebSocket Gateway, Observability Tracing (Braintrust / Langfuse).")
]
for title, desc in bullets4:
    p = tf4.add_paragraph()
    p.text = title
    p.font.bold = True
    p.font.size = Pt(18)
    p.font.color.rgb = ACCENT_PURPLE
    
    p_desc = tf4.add_paragraph()
    p_desc.text = "   " + desc
    p_desc.font.size = Pt(16)
    p_desc.font.color.rgb = TEXT_DARK

# Slide 5: Edge Cases
slide5 = prs.slides.add_slide(blank_slide_layout)
set_slide_background(slide5)
add_header(slide5, "4. Kỹ thuật Xử lý các Case Khó (Advanced Edge Cases)", "5 nhóm giải pháp kỹ thuật giải quyết trọn vẹn các thách thức thực tế")

tx5 = slide5.shapes.add_textbox(Inches(0.8), Inches(1.8), Inches(11.7), Inches(5.3))
tf5 = tx5.text_frame
tf5.word_wrap = True

bullets5 = [
    ("⚡ Case 1: Tối ưu Latency 2-tier Detect:", "Dùng langdetect cục bộ (~2ms). Bỏ bước LLM detect giảm latency từ 2610ms xuống 1501ms (~42.5%)."),
    ("👔 Case 2: Audience & Honorific Sensitivity:", "Tra cứu Glossary theo đối tượng đọc (Internal vs Client) kết hợp Honorific Profile Fan-out."),
    ("🤖 Case 3: Lọc nhiễu Glossary Mining:", "Gom cụm Semantic Embedding (Cosine >= 0.85). Yêu cầu occurrence >= 3 & distinct_users >= 2."),
    ("🔐 Case 4: Bảo vệ PII & Privacy Guardrails:", "Xác thực Consent Scope (ADR-30); Log telemetry (ADR-16) mask PII hoàn toàn."),
    ("🛡️ Case 5: 2-Level Fallback chống sập Chat:", "Chuyển hướng deep-translator -> Trả nguyên bản với is_fallback=true. Chat hoạt động 100%.")
]
for title, desc in bullets5:
    p = tf5.add_paragraph()
    p.text = title
    p.font.bold = True
    p.font.size = Pt(17)
    p.font.color.rgb = ACCENT_BLUE
    
    p_desc = tf5.add_paragraph()
    p_desc.text = "   " + desc
    p_desc.font.size = Pt(15)
    p_desc.font.color.rgb = TEXT_DARK

# Slide 6: Evaluation
slide6 = prs.slides.add_slide(blank_slide_layout)
set_slide_background(slide6)
add_header(slide6, "5. Hệ thống Chấm điểm & Đánh giá (Evaluation Framework)", "Kết hợp Automated Benchmarking, LLM-as-a-Judge và Human Feedback")

tx6 = slide6.shapes.add_textbox(Inches(0.8), Inches(1.8), Inches(11.7), Inches(5.3))
tf6 = tx6.text_frame
tf6.word_wrap = True

bullets6 = [
    ("📊 Golden Set Test Suite (eval/golden_set.jsonl):", "62+ kịch bản kiểm thử có nhãn (viết tắt, từ lóng, code snippets, xưng hô)."),
    ("🎯 Bộ Chỉ số Đánh giá Toàn diện:", "- BLEU & ChrF Score: Đo độ chính xác n-gram từ vựng chuẩn.\n- LLM-as-a-Judge: Đánh giá Fidelity & Completeness (thang điểm 1-5).\n- Telemetry 5 Exit Points: Ghi nhận tỷ lệ thành công & fallback.\n- User Upvote/Downvote Ratio: Thống kê tỷ lệ hài lòng thực tế người dùng.")
]
for title, desc in bullets6:
    p = tf6.add_paragraph()
    p.text = title
    p.font.bold = True
    p.font.size = Pt(18)
    p.font.color.rgb = GOLD_DARK
    
    p_desc = tf6.add_paragraph()
    p_desc.text = "   " + desc
    p_desc.font.size = Pt(16)
    p_desc.font.color.rgb = TEXT_DARK

# Slide 7: Acceptance & Results
slide7 = prs.slides.add_slide(blank_slide_layout)
set_slide_background(slide7)
add_header(slide7, "6. Kết quả Nghiệm thu Sản phẩm (Product Acceptance)", "Hoàn thành 100% MVP & Triển khai thực tế trên Production")

tx7 = slide7.shapes.add_textbox(Inches(0.8), Inches(1.8), Inches(11.7), Inches(5.3))
tf7 = tx7.text_frame
tf7.word_wrap = True

bullets7 = [
    ("✅ Mức độ Hoàn thiện Tính năng:", "Đã hoàn thành toàn bộ F-01 -> F-06 + F-07 (Glossary Mining & Admin Panel) + F-08 (Assistant Agent & RAG)."),
    ("🧪 Test Suite Pass Rate 100%:", "- test_glossary_mining.py: 16/16 PASSED.\n- Full Glossary & Admin Suite: 52/52 PASSED.\n- Unit & Integration Test Suite: PASSED."),
    ("🌐 Triển khai Thực tế (Live Deployment):", "- Frontend: Vercel (linguaflow-4-u3.vercel.app)\n- Backend API: Railway (FastAPI + WebSocket Gateway)\n- Database: PostgreSQL + pgvector (Railway / Supabase Production DB)")
]
for title, desc in bullets7:
    p = tf7.add_paragraph()
    p.text = title
    p.font.bold = True
    p.font.size = Pt(18)
    p.font.color.rgb = ACCENT_BLUE
    
    p_desc = tf7.add_paragraph()
    p_desc.text = "   " + desc
    p_desc.font.size = Pt(16)
    p_desc.font.color.rgb = TEXT_DARK

# Slide 8: Roadmap
slide8 = prs.slides.add_slide(blank_slide_layout)
set_slide_background(slide8)
add_header(slide8, "7. Hướng Phát triển & Lộ trình Doanh nghiệp (Roadmap)", "Tích hợp sâu vào quy trình công việc thực tế của Doanh nghiệp")

tx8 = slide8.shapes.add_textbox(Inches(0.8), Inches(1.8), Inches(11.7), Inches(5.3))
tf8 = tx8.text_frame
tf8.word_wrap = True

bullets8 = [
    ("🔄 Đồng bộ 2 chiều Google Calendar & Work Apps:", "Tự động hóa Webhook 2 chiều với Google Calendar; Đóng gói Plugin cho Slack, MS Teams, Zalo Work."),
    ("🔒 Enterprise RBAC & Phân quyền Bảo mật:", "Ranh giới dữ liệu tuyệt đối: Admin quản lý chi phí/thuật ngữ nhưng KHÔNG CÓ QUYỀN đọc tin nhắn nội bộ của nhân viên."),
    ("📈 Admin Analytics Dashboard:", "Trực quan hóa xu hướng điểm BLEU, tỷ lệ Upvote/Downvote, và chi phí Token theo ngày/model.")
]
for title, desc in bullets8:
    p = tf8.add_paragraph()
    p.text = title
    p.font.bold = True
    p.font.size = Pt(18)
    p.font.color.rgb = ACCENT_PURPLE
    
    p_desc = tf8.add_paragraph()
    p_desc.text = "   " + desc
    p_desc.font.size = Pt(16)
    p_desc.font.color.rgb = TEXT_DARK

# Save
os.makedirs("D:/Python/AiVin/P-217/presentation", exist_ok=True)
prs.save("D:/Python/AiVin/P-217/presentation/pitch_deck.pptx")
print("Bright, high-contrast Pitch Deck PowerPoint updated successfully at presentation/pitch_deck.pptx!")
