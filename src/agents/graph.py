"""Translation Agent — LangGraph state machine.

Luồng theo Agent Flow (docs/architecture_diagram.md §2):

    START -> detect_language -> [nguồn == đích?]
                                  ├── Có    -> passthrough      -> END
                                  ├── Lỗi   -> validate_output  -> END  (fallback)
                                  └── Không -> build_context -> translate
                                                             -> validate_output -> END
"""

from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from src.agents.context_provider import (
    DEFAULT_CONTEXT_SIZE,
    ContextProvider,
)
from src.agents.nodes.translation import (
    detect_language,
    make_build_context,
    passthrough,
    translate,
    validate_output,
)
from src.agents.state import AgentState


def route_after_detect(state: AgentState) -> str:
    """Quyết định nhánh sau khi xác định ngôn ngữ nguồn.

    - Có lỗi ở bước detect: đi thẳng validate_output để trả fallback.
    - Ngôn ngữ nguồn trùng đích: bỏ qua LLM (tiết kiệm token và độ trễ).
    - Còn lại: dịch bình thường.
    """
    if state.get("error"):
        return "validate_output"

    source_language = state.get("source_language")
    target_language = state.get("target_language")
    if source_language and source_language == target_language:
        return "passthrough"

    return "build_context"


def build_translation_graph(
    context_provider: ContextProvider | None = None,
    context_size: int = DEFAULT_CONTEXT_SIZE,
):
    """Dựng và compile translation graph.

    Args:
        context_provider: nguồn lấy 3-5 tin gần nhất. Mặc định không có ngữ cảnh
            (xem src/agents/context_provider.py).
        context_size: số tin nhắn dùng làm ngữ cảnh.
    """
    graph = StateGraph(AgentState)

    graph.add_node("detect_language", detect_language)
    graph.add_node("build_context", make_build_context(context_provider, context_size))
    graph.add_node("translate", translate)
    graph.add_node("validate_output", validate_output)
    graph.add_node("passthrough", passthrough)

    graph.add_edge(START, "detect_language")
    graph.add_conditional_edges(
        "detect_language",
        route_after_detect,
        {
            "passthrough": "passthrough",
            "build_context": "build_context",
            "validate_output": "validate_output",
        },
    )
    graph.add_edge("build_context", "translate")
    graph.add_edge("translate", "validate_output")
    graph.add_edge("validate_output", END)
    graph.add_edge("passthrough", END)

    return graph.compile()


# Instance mặc định (không có ngữ cảnh). Chat Service nên tự dựng graph riêng
# với ContextProvider thật thay vì dùng biến này.
#
# LƯU Ý: tên `agent` được src/api/routes.py import. Không đổi tên khi chưa gỡ
# endpoint legacy /chat (xem docs/CONTRACT.md §3.3).
agent = build_translation_graph()
