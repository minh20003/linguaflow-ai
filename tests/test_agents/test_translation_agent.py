"""Test cho Translation Agent (F-03.1).

Toàn bộ test mock LLM, không gọi API thật: kết quả LLM không tất định, gọi thật
thì chậm, tốn chi phí và test sẽ đỏ khi hết hạn mức free tier.

Fixture đặt cục bộ trong file này thay vì tests/conftest.py để tránh xung đột với
nhánh feature/f-01-2-auth-user-config (nhánh đó viết lại conftest).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from src.agents.context_provider import InMemoryContextProvider, NullContextProvider
from src.agents.graph import build_translation_graph, route_after_detect
from src.agents.nodes.translation import validate_output

NODES_MODULE = "src.agents.nodes.translation"


def make_llm(*responses: str) -> AsyncMock:
    """LLM giả trả về lần lượt các nội dung được truyền vào."""
    llm = AsyncMock()
    llm.ainvoke = AsyncMock(
        side_effect=[type("Msg", (), {"content": r})() for r in responses]
    )
    llm.model_name = "mock-model"
    return llm


# ============================================================
# Routing
# ============================================================


def test_route_bo_qua_llm_khi_cung_ngon_ngu():
    state = {"source_language": "vi", "target_language": "vi"}
    assert route_after_detect(state) == "passthrough"


def test_route_dich_khi_khac_ngon_ngu():
    state = {"source_language": "vi", "target_language": "en"}
    assert route_after_detect(state) == "build_context"


def test_route_di_thang_validate_khi_co_loi():
    state = {"error": "detect that bai", "source_language": "vi", "target_language": "en"}
    assert route_after_detect(state) == "validate_output"


# ============================================================
# Luồng end-to-end
# ============================================================


@pytest.mark.asyncio
async def test_cung_ngon_ngu_thi_khong_goi_llm_dich():
    """Nguồn trùng đích: chỉ tốn 1 lần gọi LLM để detect, không gọi để dịch."""
    llm = make_llm("vi")  # chỉ có 1 response -> gọi lần 2 sẽ StopIteration

    with patch(f"{NODES_MODULE}.get_llm", return_value=llm):
        graph = build_translation_graph(NullContextProvider())
        result = await graph.ainvoke(
            {
                "conversation_id": "c1",
                "original_text": "Chào bạn",
                "source_language": "vi",
                "target_language": "vi",
            }
        )

    assert result["translated_text"] == "Chào bạn"
    assert result["is_fallback"] is False
    assert llm.ainvoke.await_count == 1


@pytest.mark.asyncio
async def test_khac_ngon_ngu_thi_dich():
    llm = make_llm("vi", "Hello there")

    with patch(f"{NODES_MODULE}.get_llm", return_value=llm):
        graph = build_translation_graph(NullContextProvider())
        result = await graph.ainvoke(
            {
                "conversation_id": "c1",
                "original_text": "Chào bạn",
                "source_language": "vi",
                "target_language": "en",
            }
        )

    assert result["translated_text"] == "Hello there"
    assert result["is_valid"] is True
    assert result["is_fallback"] is False
    assert result["model"] == "mock-model"
    assert "latency_ms" in result


@pytest.mark.asyncio
async def test_detect_ghi_de_gia_tri_tam():
    """source_language vào là giá trị tạm, detect phải ghi đè (CONTRACT §4.3)."""
    llm = make_llm("en", "Xin chào")

    with patch(f"{NODES_MODULE}.get_llm", return_value=llm):
        graph = build_translation_graph(NullContextProvider())
        result = await graph.ainvoke(
            {
                "conversation_id": "c1",
                "original_text": "Hello",
                "source_language": "vi",  # giá trị tạm, sai
                "target_language": "vi",
            }
        )

    # Detect ra "en" khác đích "vi" -> phải dịch, không passthrough
    assert result["source_language"] == "en"
    assert result["translated_text"] == "Xin chào"


@pytest.mark.asyncio
async def test_context_duoc_dua_vao_prompt():
    llm = make_llm("vi", "Did you deploy it yet?")
    provider = InMemoryContextProvider()
    provider.add_message("c1", "An: Tôi vừa merge PR rồi")
    provider.add_message("c1", "Bình: Ok để tôi review")

    with patch(f"{NODES_MODULE}.get_llm", return_value=llm):
        graph = build_translation_graph(provider)
        result = await graph.ainvoke(
            {
                "conversation_id": "c1",
                "original_text": "Deploy chưa?",
                "source_language": "vi",
                "target_language": "en",
            }
        )

    assert result["context_messages"] == [
        "An: Tôi vừa merge PR rồi",
        "Bình: Ok để tôi review",
    ]
    # Lần gọi thứ 2 là dịch — prompt user phải chứa lịch sử hội thoại
    user_prompt = llm.ainvoke.await_args_list[1].args[0][1]["content"]
    assert "Tôi vừa merge PR rồi" in user_prompt
    assert "Deploy chưa?" in user_prompt


# ============================================================
# Fallback — NFR-02: lỗi LLM không được làm mất tin nhắn
# ============================================================


@pytest.mark.asyncio
async def test_llm_loi_thi_fallback_tra_ban_goc():
    llm = AsyncMock()
    llm.ainvoke = AsyncMock(side_effect=RuntimeError("API down"))

    with patch(f"{NODES_MODULE}.get_llm", return_value=llm):
        graph = build_translation_graph(NullContextProvider())
        result = await graph.ainvoke(
            {
                "conversation_id": "c1",
                "original_text": "Chào bạn",
                "source_language": "vi",
                "target_language": "en",
            }
        )

    assert result["translated_text"] == "Chào bạn"
    assert result["is_fallback"] is True
    assert result["is_valid"] is False


@pytest.mark.asyncio
async def test_llm_tra_ve_rong_thi_fallback():
    llm = make_llm("vi", "   ")

    with patch(f"{NODES_MODULE}.get_llm", return_value=llm):
        graph = build_translation_graph(NullContextProvider())
        result = await graph.ainvoke(
            {
                "conversation_id": "c1",
                "original_text": "Chào bạn",
                "source_language": "vi",
                "target_language": "en",
            }
        )

    assert result["translated_text"] == "Chào bạn"
    assert result["is_fallback"] is True


@pytest.mark.asyncio
async def test_context_provider_loi_thi_van_dich_duoc():
    """Mất ngữ cảnh làm giảm chất lượng nhưng không được chặn luồng."""

    class BrokenProvider:
        async def get_recent_messages(self, conversation_id, limit=5):
            raise ConnectionError("DB down")

    llm = make_llm("vi", "Hello")

    with patch(f"{NODES_MODULE}.get_llm", return_value=llm):
        graph = build_translation_graph(BrokenProvider())
        result = await graph.ainvoke(
            {
                "conversation_id": "c1",
                "original_text": "Chào",
                "source_language": "vi",
                "target_language": "en",
            }
        )

    assert result["translated_text"] == "Hello"
    assert result["is_fallback"] is False


@pytest.mark.asyncio
async def test_ban_dich_dai_bat_thuong_thi_fallback():
    """Chặn trường hợp LLM trả lời kèm giải thích thay vì chỉ dịch."""
    state = {
        "original_text": "Chào",
        "translated_text": "Đây là bản dịch của bạn: " + "x" * 300,
    }
    result = await validate_output(state)

    assert result["is_fallback"] is True
    assert result["translated_text"] == "Chào"


@pytest.mark.asyncio
async def test_original_text_rong_thi_bao_loi_khong_crash():
    llm = make_llm("vi")

    with patch(f"{NODES_MODULE}.get_llm", return_value=llm):
        graph = build_translation_graph(NullContextProvider())
        result = await graph.ainvoke(
            {"conversation_id": "c1", "original_text": "", "target_language": "en"}
        )

    assert result["is_fallback"] is True
    assert "error" in result
