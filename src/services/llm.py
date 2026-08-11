"""LLM factory — chọn provider qua biến môi trường LLM_PROVIDER.

Đổi provider chỉ cần sửa .env, không sửa code (xem quyết định D10 trong ARCHITECTURE.md).
Mỗi provider có rate limit khác nhau, nên cần đổi được nhanh khi bị throttle.
"""

from langchain_core.language_models.chat_models import BaseChatModel

from src.config import Settings, get_settings

# Model mặc định cho từng provider, dùng khi LLM_MODEL để rỗng
DEFAULT_MODELS: dict[str, str] = {
    "groq": "llama-3.3-70b-versatile",
    "deepseek": "deepseek-chat",
    "gemini": "gemini-2.5-flash",
    "openai": "gpt-4o-mini",
}

# DeepSeek dùng chuẩn OpenAI-compatible nên tái sử dụng client OpenAI
DEEPSEEK_BASE_URL = "https://api.deepseek.com"


# Tên biến env chứa key của từng provider — dùng cho cả validate lẫn thông báo lỗi
API_KEY_ENV: dict[str, str] = {
    "groq": "GROQ_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "gemini": "GOOGLE_API_KEY",
    "openai": "OPENAI_API_KEY",
}


class LLMConfigError(RuntimeError):
    """Thiếu API key hoặc provider không hợp lệ."""


def _resolve_api_key(settings: Settings, provider: str) -> str:
    """Lấy API key của provider, báo lỗi rõ ràng nếu chưa set."""
    key = {
        "groq": settings.groq_api_key,
        "deepseek": settings.deepseek_api_key,
        "gemini": settings.google_api_key,
        "openai": settings.openai_api_key,
    }[provider]

    if not key:
        env_var = API_KEY_ENV[provider]
        raise LLMConfigError(
            f"LLM_PROVIDER={provider} nhưng {env_var} chưa được set. "
            f"Thêm {env_var} vào .env hoặc đổi LLM_PROVIDER sang provider khác."
        )
    return key


def get_llm(settings: Settings | None = None) -> BaseChatModel:
    """Tạo chat model theo provider đang cấu hình.

    Raises:
        LLMConfigError: nếu provider không hợp lệ hoặc thiếu API key tương ứng.
    """
    settings = settings or get_settings()
    provider = settings.llm_provider

    if provider not in DEFAULT_MODELS:
        raise LLMConfigError(
            f"LLM_PROVIDER không hợp lệ: {provider}. "
            f"Chọn một trong: {', '.join(sorted(DEFAULT_MODELS))}"
        )

    # Validate key TRƯỚC khi import package của provider, để thiếu key luôn
    # báo lỗi rõ ràng thay vì ImportError khó hiểu khi package chưa cài.
    api_key = _resolve_api_key(settings, provider)

    common = {
        "model": settings.llm_model or DEFAULT_MODELS[provider],
        "temperature": settings.llm_temperature,
        "timeout": settings.llm_timeout_seconds,
    }

    if provider == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(api_key=api_key, **common)

    if provider == "deepseek":
        from langchain_openai import ChatOpenAI

        return ChatOpenAI(api_key=api_key, base_url=DEEPSEEK_BASE_URL, **common)

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(google_api_key=api_key, **common)

    from langchain_openai import ChatOpenAI  # provider == "openai"

    return ChatOpenAI(api_key=api_key, **common)
