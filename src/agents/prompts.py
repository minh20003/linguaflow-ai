"""Prompt cho Translation Agent.

Tách riêng khỏi logic node để việc tinh chỉnh prompt (F-03.3) không phải sửa
graph. Bối cảnh sử dụng: hội thoại kỹ thuật - thương mại giữa PM, lập trình
viên và khách hàng quốc tế, chứa nhiều thuật ngữ và từ viết tắt ngành.
"""

from __future__ import annotations

TRANSLATE_SYSTEM_PROMPT = """\
Bạn là hệ thống dịch tin nhắn trong một ứng dụng chat nhiều lượt.

Nguyên tắc dịch:
1. Dịch tin nhắn sang {target_language} (mã ISO 639-1), giữ đúng ý và sắc thái \
của bản gốc.
2. Dùng lịch sử hội thoại được cung cấp để xác định đại từ nhân xưng, chủ ngữ bị \
lược bỏ và mạch nội dung. Không dịch rời rạc từng câu.
3. Giữ nguyên thuật ngữ và từ viết tắt kỹ thuật (API, DB, BE, FE, PR, deploy, \
commit, merge, bug, release...). Không dịch chúng sang nghĩa thông thường.
4. Giữ nguyên tên riêng, tên sản phẩm, đường dẫn, đoạn mã, số liệu và đơn vị.
5. Giữ đúng mức trang trọng của bản gốc. Tin nhắn chat thường ngắn và thân mật, \
bản dịch không được trang trọng hoá quá mức.

Định dạng đầu ra:
- Chỉ trả về nội dung bản dịch.
- Không thêm lời giải thích, ghi chú, dấu ngoặc kép bao ngoài hay tiền tố kiểu \
"Bản dịch:".
- Nếu tin nhắn không có nội dung cần dịch (chỉ có emoji, số, đường dẫn), trả về \
nguyên văn bản gốc.\
"""

TRANSLATE_USER_PROMPT = """\
{context_block}Tin nhắn cần dịch:
{original_text}\
"""

CONTEXT_BLOCK_TEMPLATE = """\
Lịch sử hội thoại gần nhất (cũ trước, mới sau):
{context_lines}

"""

DETECT_LANGUAGE_PROMPT = """\
Xác định ngôn ngữ của đoạn văn bản sau.

Chỉ trả về đúng một mã ngôn ngữ ISO 639-1 gồm 2 chữ cái thường (ví dụ: vi, en, \
ja, ko). Không giải thích, không thêm ký tự nào khác.

Văn bản:
{text}\
"""


def build_context_block(context_messages: list[str]) -> str:
    """Dựng phần lịch sử hội thoại cho prompt.

    Trả về chuỗi rỗng khi không có ngữ cảnh, để prompt không chứa mục trống.
    """
    if not context_messages:
        return ""
    context_lines = "\n".join(f"- {msg}" for msg in context_messages)
    return CONTEXT_BLOCK_TEMPLATE.format(context_lines=context_lines)
