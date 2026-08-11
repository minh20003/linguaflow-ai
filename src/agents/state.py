"""State schema cho Translation Agent.

Định nghĩa bắt buộc theo docs/CONTRACT.md §2. Không đổi tên trường —
Frontend, Backend và Agent dùng chung bộ tên này.
"""

from __future__ import annotations

from typing import TypedDict


class AgentState(TypedDict, total=False):
    """State truyền giữa các node trong translation graph.

    total=False cho phép mọi trường là tuỳ chọn: node chỉ trả về phần
    mình thay đổi, LangGraph tự gộp vào state chung.
    """

    # Định danh — do Chat Service truyền vào
    conversation_id: str
    message_id: str
    sender_id: str

    # Đầu vào
    original_text: str
    source_language: str  # ISO 639-1; giá trị tạm khi vào, detect sẽ ghi đè
    target_language: str  # Lấy từ users.preferred_language của người nhận

    # Ngữ cảnh hội thoại
    context_messages: list[str]  # 3-5 tin gần nhất, đã định dạng cho prompt

    # Kết quả
    translated_text: str
    translation_id: str  # Định danh bản ghi translation_results, phục vụ F-05
    is_valid: bool  # Kết quả của node validate_output
    is_fallback: bool  # True khi trả về bản gốc do lỗi hoặc timeout

    # Đo lường — ghi vào translation_results và Langfuse
    model: str
    latency_ms: int

    error: str
