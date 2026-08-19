"""
LLM Provider Factory supporting Local Models (Ollama, vLLM) and Cloud APIs (Gemini, OpenAI, Anthropic).
"""

import os
import logging
from typing import Optional, Any

logger = logging.getLogger("LLMFactory")

def get_llm_provider(
    provider: str = "auto",
    model_name: Optional[str] = None,
    api_base: Optional[str] = None,
    temperature: float = 0.1
) -> Optional[Any]:
    """
    Instantiates an LLM client for local or cloud model providers.
    
    Supported providers:
      - "ollama": Local Ollama instance (default base: http://localhost:11434)
      - "vllm": Local vLLM / LocalAI server (default base: http://localhost:8000/v1)
      - "gemini": Google Gemini API (gemini-2.5-flash)
      - "openai": OpenAI API (gpt-4o)
      - "auto": Auto-detects available environment variables or local services.
    """
    provider = provider.lower()

    if provider == "ollama":
        try:
            from langchain_community.chat_models import ChatOllama
            model = model_name or "codellama:7b"
            base_url = api_base or os.getenv("OLLAMA_HOST", "http://localhost:11434")
            logger.info(f"[LLM Factory] Initializing Ollama provider (model='{model}', base='{base_url}')")
            return ChatOllama(model=model, base_url=base_url, temperature=temperature)
        except Exception as e:
            logger.warning(f"[LLM Factory] Could not initialize Ollama: {e}")
            return None

    elif provider == "vllm":
        try:
            from langchain_openai import ChatOpenAI
            model = model_name or "Qwen/Qwen2.5-Coder-7B-Instruct"
            base_url = api_base or os.getenv("VLLM_API_BASE", "http://localhost:8000/v1")
            api_key = os.getenv("VLLM_API_KEY", "EMPTY")
            logger.info(f"[LLM Factory] Initializing vLLM provider (model='{model}', base='{base_url}')")
            return ChatOpenAI(model=model, openai_api_base=base_url, openai_api_key=api_key, temperature=temperature)
        except Exception as e:
            logger.warning(f"[LLM Factory] Could not initialize vLLM: {e}")
            return None

    elif provider == "gemini":
        try:
            from langchain_google_genai import ChatGoogleGenerativeAI
            model = model_name or "gemini-2.5-flash"
            logger.info(f"[LLM Factory] Initializing Gemini provider (model='{model}')")
            return ChatGoogleGenerativeAI(model=model, temperature=temperature)
        except Exception as e:
            logger.warning(f"[LLM Factory] Could not initialize Gemini: {e}")
            return None

    elif provider == "openai":
        try:
            from langchain_openai import ChatOpenAI
            model = model_name or "gpt-4o"
            logger.info(f"[LLM Factory] Initializing OpenAI provider (model='{model}')")
            return ChatOpenAI(model=model, temperature=temperature)
        except Exception as e:
            logger.warning(f"[LLM Factory] Could not initialize OpenAI: {e}")
            return None

    elif provider == "auto":
        if os.getenv("GEMINI_API_KEY"):
            return get_llm_provider("gemini", model_name, api_base, temperature)
        elif os.getenv("OPENAI_API_KEY"):
            return get_llm_provider("openai", model_name, api_base, temperature)
        elif os.getenv("OLLAMA_HOST"):
            return get_llm_provider("ollama", model_name, api_base, temperature)
        else:
            logger.info("[LLM Factory] No explicit API key or endpoint found. Defaulting to offline simulation mode.")
            return None

    logger.warning(f"[LLM Factory] Unknown provider '{provider}'. Operating in offline simulation mode.")
    return None
