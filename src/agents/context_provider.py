"""Nguồn cung cấp ngữ cảnh hội thoại cho Translation Agent.

Agent cần 3-5 tin nhắn gần nhất trong cùng cuộc hội thoại để dịch đúng đại từ
nhân xưng và mạch hội thoại (docs/CONTRACT.md §2, ADR-01).

Bảng `messages` chưa được hiện thực hoá (xem docs/architecture_diagram.md §4),
nên nguồn ngữ cảnh được trừu tượng hoá qua Protocol dưới đây. Khi bảng `messages`
sẵn sàng, chỉ cần bổ sung một implementation mới đọc từ cơ sở dữ liệu — không
phải sửa bất kỳ node nào.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

# Số tin nhắn gần nhất dùng làm ngữ cảnh (PRD quy định 3-5)
DEFAULT_CONTEXT_SIZE = 5


@runtime_checkable
class ContextProvider(Protocol):
    """Giao diện lấy ngữ cảnh hội thoại."""

    async def get_recent_messages(
        self,
        conversation_id: str,
        limit: int = DEFAULT_CONTEXT_SIZE,
    ) -> list[str]:
        """Trả về tối đa `limit` tin nhắn gần nhất, cũ trước mới sau.

        Mỗi phần tử là một dòng đã định dạng sẵn để đưa vào prompt.
        Trả về danh sách rỗng nếu cuộc hội thoại chưa có tin nào.
        """
        ...


class NullContextProvider:
    """Không cung cấp ngữ cảnh. Dùng làm mặc định khi chưa cấu hình nguồn thật.

    Agent vẫn dịch được, chỉ mất khả năng bám ngữ cảnh hội thoại.
    """

    async def get_recent_messages(
        self,
        conversation_id: str,
        limit: int = DEFAULT_CONTEXT_SIZE,
    ) -> list[str]:
        return []


class InMemoryContextProvider:
    """Lưu ngữ cảnh trong bộ nhớ tiến trình. Dùng cho kiểm thử và demo.

    Không bền vững qua các lần khởi động lại — không dùng ở production.
    """

    def __init__(self, messages: dict[str, list[str]] | None = None) -> None:
        self._store: dict[str, list[str]] = messages or {}

    def add_message(self, conversation_id: str, message: str) -> None:
        """Thêm một tin nhắn vào cuối lịch sử của cuộc hội thoại."""
        self._store.setdefault(conversation_id, []).append(message)

    async def get_recent_messages(
        self,
        conversation_id: str,
        limit: int = DEFAULT_CONTEXT_SIZE,
    ) -> list[str]:
        history = self._store.get(conversation_id, [])
        if limit <= 0:
            return []
        return history[-limit:]
