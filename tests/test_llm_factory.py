"""
Unit tests for LLM Factory (src/ast_healing_coder/llm_factory.py).
Verifies provider resolution, offline fallback, and environment-based auto-detection.
"""

import sys
import os
from unittest.mock import patch, MagicMock
from ast_healing_coder.llm_factory import get_llm_provider

def test_auto_fallback_offline_mode():
    with patch.dict(os.environ, {}, clear=True):
        llm = get_llm_provider("auto")
        assert llm is None

def test_unknown_provider_fallback():
    llm = get_llm_provider("nonexistent_provider")
    assert llm is None

def test_auto_gemini_routing():
    with patch.dict(os.environ, {"GEMINI_API_KEY": "test_gemini_key"}):
        with patch("ast_healing_coder.llm_factory.get_llm_provider") as mock_get:
            mock_get.return_value = "mock_gemini_client"
            res = mock_get("gemini", None, None, 0.1)
            assert res == "mock_gemini_client"

def test_ollama_provider_invocation():
    mock_module = MagicMock()
    mock_instance = MagicMock()
    mock_module.chat_models.ChatOllama.return_value = mock_instance

    with patch.dict(sys.modules, {
        "langchain_community": mock_module,
        "langchain_community.chat_models": mock_module.chat_models
    }):
        llm = get_llm_provider("ollama", model_name="qwen2.5-coder:7b", api_base="http://localhost:11434")
        assert llm == mock_instance

def test_vllm_provider_invocation():
    mock_module = MagicMock()
    mock_instance = MagicMock()
    mock_module.ChatOpenAI.return_value = mock_instance

    with patch.dict(sys.modules, {
        "langchain_openai": mock_module
    }):
        llm = get_llm_provider("vllm", model_name="Qwen/Qwen2.5-Coder-7B-Instruct", api_base="http://localhost:8000/v1")
        assert llm == mock_instance
