"""Test cho tích hợp Langfuse (F-03.4).

Trọng tâm: thiếu cấu hình hoặc lỗi khởi tạo đều không được làm hỏng luồng dịch.
"""

from __future__ import annotations

from unittest.mock import patch

from src.agents import observability
from src.agents.observability import build_runnable_config, get_langfuse_handler

MODULE = "src.agents.observability"


def setup_function() -> None:
    """Xoá cache giữa các test — handler được cache bằng lru_cache."""
    observability._init_langfuse_handler.cache_clear()


def make_settings(public_key: str = "", secret_key: str = ""):
    class FakeSettings:
        langfuse_public_key = public_key
        langfuse_secret_key = secret_key
        langfuse_host = "https://cloud.langfuse.com"

    return FakeSettings()


def test_khong_co_key_thi_tra_none():
    with patch(f"{MODULE}.get_settings", return_value=make_settings()):
        assert get_langfuse_handler() is None


def test_chi_co_mot_key_thi_tra_none():
    """Thiếu secret_key cũng phải bỏ qua, không được khởi tạo nửa vời."""
    with patch(f"{MODULE}.get_settings", return_value=make_settings(public_key="pk")):
        assert get_langfuse_handler() is None


def test_config_rong_khi_khong_co_tracing():
    with patch(f"{MODULE}.get_settings", return_value=make_settings()):
        assert build_runnable_config() == {}


def test_metadata_duoc_dua_vao_config():
    with patch(f"{MODULE}.get_settings", return_value=make_settings()):
        config = build_runnable_config(conversation_id="c1", message_id="m1")

    assert config["metadata"] == {"conversation_id": "c1", "message_id": "m1"}
    assert "callbacks" not in config


def test_metadata_bo_qua_gia_tri_none():
    with patch(f"{MODULE}.get_settings", return_value=make_settings()):
        config = build_runnable_config(conversation_id="c1", translation_id=None)

    assert config["metadata"] == {"conversation_id": "c1"}


def test_loi_khoi_tao_khong_lam_vo_luong():
    """Langfuse lỗi (sai key, không kết nối được) thì Agent vẫn phải chạy."""
    settings = make_settings(public_key="pk", secret_key="sk")

    with (
        patch(f"{MODULE}.get_settings", return_value=settings),
        patch("langfuse.Langfuse", side_effect=RuntimeError("connection refused")),
    ):
        assert get_langfuse_handler() is None
        assert build_runnable_config() == {}
