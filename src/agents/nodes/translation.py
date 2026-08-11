"""Các node của Translation Agent.

Chuỗi node theo Agent Flow (docs/architecture_diagram.md §2):
    detect_language -> build_context -> translate -> validate_output

Nguyên tắc bắt buộc: không node nào được raise. Mọi lỗi ghi vào state["error"]
và đi tiếp theo đường fallback (trả về bản gốc), để luồng chat không bị chặn
khi LLM lỗi hoặc timeout (NFR-02).
"""

from __future__ import annotations

import logging
import re
import time

from src.agents.context_provider import (
    DEFAULT_CONTEXT_SIZE,
    ContextProvider,
    NullContextProvider,
)
from src.agents.prompts import (
    DETECT_LANGUAGE_PROMPT,
    TRANSLATE_SYSTEM_PROMPT,
    TRANSLATE_USER_PROMPT,
    build_context_block,
)
from src.agents.state import AgentState
from src.services.llm import get_llm

logger = logging.getLogger(__name__)

# Mã ISO 639-1: đúng 2 chữ cái
_ISO_639_1 = re.compile(r"^[a-z]{2}$")

# Văn bản không chứa chữ cái (chỉ emoji, số, dấu câu, URL) thì không cần dịch
_HAS_LETTER = re.compile(r"[^\W\d_]", re.UNICODE)


def _extract_text(response: object) -> str:
    """Lấy phần text từ response của LangChain chat model."""
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content.strip()
    # Một số provider trả content dạng list block
    if isinstance(content, list):
        parts = [
            block.get("text", "")
            for block in content
            if isinstance(block, dict) and block.get("type") == "text"
        ]
        return "".join(parts).strip()
    return str(content).strip()


async def detect_language(state: AgentState) -> dict:
    """Xác định ngôn ngữ nguồn thật của tin nhắn.

    Giá trị `source_language` đi vào node này chỉ là giá trị tạm (preferred_language
    của người gửi) theo quy tắc docs/CONTRACT.md §4.3. Kết quả detect sẽ ghi đè.
    Khi không detect được, giữ nguyên giá trị tạm thay vì để trống.
    """
    original_text = (state.get("original_text") or "").strip()
    fallback_language = state.get("source_language", "")

    if not original_text:
        return {"error": "original_text rỗng, không thể xác định ngôn ngữ"}

    # Không có chữ cái thì không đủ căn cứ detect — giữ giá trị tạm
    if not _HAS_LETTER.search(original_text):
        return {"source_language": fallback_language}

    try:
        llm = get_llm()
        response = await llm.ainvoke(
            DETECT_LANGUAGE_PROMPT.format(text=original_text[:500])
        )
        detected = _extract_text(response).lower()
    except Exception as exc:
        logger.warning("detect_language thất bại: %s", exc)
        return {"source_language": fallback_language}

    if not _ISO_639_1.match(detected):
        logger.warning("detect_language trả về mã không hợp lệ: %r", detected)
        return {"source_language": fallback_language}

    return {"source_language": detected}


def make_build_context(
    context_provider: ContextProvider | None = None,
    limit: int = DEFAULT_CONTEXT_SIZE,
):
    """Tạo node build_context gắn với một nguồn ngữ cảnh cụ thể.

    Dùng closure thay vì đọc biến toàn cục để graph có thể chạy song song với
    nhiều nguồn khác nhau (ví dụ: nguồn thật ở production, nguồn giả khi test).
    """
    provider = context_provider or NullContextProvider()

    async def build_context(state: AgentState) -> dict:
        conversation_id = state.get("conversation_id", "")
        if not conversation_id:
            return {"context_messages": []}

        try:
            messages = await provider.get_recent_messages(conversation_id, limit)
        except Exception as exc:
            # Thiếu ngữ cảnh làm giảm chất lượng dịch nhưng không chặn luồng
            logger.warning("build_context thất bại: %s", exc)
            return {"context_messages": []}

        return {"context_messages": list(messages)}

    return build_context


async def translate(state: AgentState) -> dict:
    """Gọi LLM dịch tin nhắn, có kèm ngữ cảnh hội thoại."""
    original_text = (state.get("original_text") or "").strip()
    target_language = state.get("target_language", "")

    if not original_text:
        return {"error": "original_text rỗng, không có gì để dịch"}
    if not target_language:
        return {"error": "target_language chưa được cung cấp"}

    system_prompt = TRANSLATE_SYSTEM_PROMPT.format(target_language=target_language)
    user_prompt = TRANSLATE_USER_PROMPT.format(
        context_block=build_context_block(state.get("context_messages", [])),
        original_text=original_text,
    )

    started = time.perf_counter()
    try:
        llm = get_llm()
        response = await llm.ainvoke(
            [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ]
        )
    except Exception as exc:
        logger.warning("translate thất bại: %s", exc)
        return {
            "error": f"Lỗi gọi LLM: {type(exc).__name__}",
            "latency_ms": int((time.perf_counter() - started) * 1000),
        }

    latency_ms = int((time.perf_counter() - started) * 1000)
    model_name = getattr(llm, "model_name", None) or getattr(llm, "model", "")

    return {
        "translated_text": _extract_text(response),
        "model": str(model_name),
        "latency_ms": latency_ms,
    }


async def validate_output(state: AgentState) -> dict:
    """Kiểm tra bản dịch và quyết định có phải dùng fallback không.

    Fallback trả về nguyên văn bản gốc: người nhận vẫn đọc được tin nhắn, chỉ
    mất phần dịch. Đây là hành vi bắt buộc theo NFR-02.
    """
    original_text = (state.get("original_text") or "").strip()
    translated_text = (state.get("translated_text") or "").strip()

    def fallback(reason: str) -> dict:
        if reason:
            logger.info("Dùng fallback: %s", reason)
        return {
            "translated_text": original_text,
            "is_valid": False,
            "is_fallback": True,
        }

    if state.get("error"):
        return fallback(state["error"])
    if not translated_text:
        return fallback("LLM trả về nội dung rỗng")

    # LLM đôi khi trả lại nguyên văn kèm lời giải thích thay vì dịch
    if len(translated_text) > max(len(original_text) * 4, 200):
        return fallback("Bản dịch dài bất thường so với bản gốc")

    return {"is_valid": True, "is_fallback": False}


async def passthrough(state: AgentState) -> dict:
    """Nhánh không cần dịch: ngôn ngữ nguồn trùng ngôn ngữ đích.

    Bỏ qua hoàn toàn việc gọi LLM (Agent Flow, nhánh "Có").
    """
    return {
        "translated_text": state.get("original_text", ""),
        "is_valid": True,
        "is_fallback": False,
        "latency_ms": 0,
    }
