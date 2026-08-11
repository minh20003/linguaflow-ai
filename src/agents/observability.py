"""Tích hợp Langfuse để theo dõi token, độ trễ và vết xử lý của Agent (F-03.4).

Xác minh với langfuse 4.14.3: `CallbackHandler` nằm ở `langfuse.langchain` và
chỉ nhận `public_key`; `secret_key` cùng `host` được cấu hình trên client
`Langfuse(...)`. Các phiên bản 2.x và 3.x có API khác — nếu nâng cấp hoặc hạ cấp
gói, phải kiểm tra lại module này.

Nguyên tắc: thiếu cấu hình hoặc lỗi khởi tạo đều không được làm hỏng luồng dịch.
Mọi trường hợp thất bại đều trả về None và Agent chạy bình thường, chỉ mất tracing.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from src.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _init_langfuse_handler() -> Any | None:
    """Khởi tạo Langfuse callback handler. Kết quả được cache cho toàn tiến trình."""
    settings = get_settings()

    if not (settings.langfuse_public_key and settings.langfuse_secret_key):
        logger.info(
            "Chưa cấu hình LANGFUSE_PUBLIC_KEY/LANGFUSE_SECRET_KEY, bỏ qua tracing"
        )
        return None

    try:
        from langfuse import Langfuse
        from langfuse.langchain import CallbackHandler
    except ImportError:
        logger.info("Chưa cài gói langfuse, bỏ qua tracing")
        return None

    try:
        # Khởi tạo client singleton — handler sẽ dùng lại client này
        Langfuse(
            public_key=settings.langfuse_public_key,
            secret_key=settings.langfuse_secret_key,
            host=settings.langfuse_host,
        )
        return CallbackHandler(public_key=settings.langfuse_public_key)
    except Exception as exc:
        logger.warning("Khởi tạo Langfuse thất bại, bỏ qua tracing: %s", exc)
        return None


def get_langfuse_handler() -> Any | None:
    """Trả về Langfuse callback handler, hoặc None nếu không khả dụng."""
    return _init_langfuse_handler()


def build_runnable_config(**metadata: Any) -> dict[str, Any]:
    """Dựng config truyền vào `graph.ainvoke()`.

    Gắn Langfuse callback khi khả dụng và đính kèm metadata (conversation_id,
    message_id, target_language...) để lọc trace trên giao diện Langfuse.

    Ví dụ:
        config = build_runnable_config(conversation_id=cid, message_id=mid)
        result = await graph.ainvoke(state, config=config)
    """
    config: dict[str, Any] = {}

    handler = get_langfuse_handler()
    if handler is not None:
        config["callbacks"] = [handler]

    if metadata:
        config["metadata"] = {k: v for k, v in metadata.items() if v is not None}

    return config
