"""
LLM Provider Factory: Configures Groq and Ollama instances for multi-agent reasoning.
- Orchestrator, Destination, Logistics, Budget -> Groq (openai/gpt-oss-120b / oss-120b)
- Review & QA Agent -> Ollama (nemotron-3-ultra)
Provides automatic graceful fallback to deterministic local engines when services are not reachable.
"""

import os
import urllib.request
from typing import Optional, Any
from dotenv import load_dotenv

load_dotenv()


def is_groq_available() -> bool:
    """Checks if a valid Groq API key is present in environment."""
    key = os.getenv("GROQ_API_KEY")
    return bool(key and key.strip() and key != "your_groq_api_key_here")


def is_ollama_available(base_url: Optional[str] = None, api_key: Optional[str] = None) -> bool:
    """Checks if Ollama daemon or cloud endpoint is reachable at the configured base URL."""
    url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    key = api_key or os.getenv("OLLAMA_API_KEY")
    try:
        req = urllib.request.Request(f"{url.rstrip('/')}/api/tags", method="GET")
        if key and key.strip() and key.strip() != "your_ollama_api_key_here":
            auth_val = key.strip() if key.strip().startswith("Bearer ") else f"Bearer {key.strip()}"
            req.add_header("Authorization", auth_val)
            req.add_header("x-api-key", key.strip())
        with urllib.request.urlopen(req, timeout=2.0) as resp:
            return resp.status in (200, 204)
    except Exception:
        return False


def is_gemini_available() -> bool:
    """Checks if a valid Gemini/Google API key is present in environment."""
    key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    return bool(key and key.strip() and key != "your_gemini_api_key_here")


def get_groq_llm(
    model: Optional[str] = None,
    temperature: float = 0.2,
    max_tokens: int = 2048
):
    """
    Returns an initialized LangChain ChatGroq instance for:
    - Orchestrator Agent
    - Destination Research Agent
    - Logistics Planning Agent
    - Budget Analysis Agent
    Uses 'openai/gpt-oss-120b' (oss-120b) by default.
    Returns None if GROQ_API_KEY is not configured.
    """
    if not is_groq_available():
        return None

    try:
        from langchain_groq import ChatGroq
        raw_model = model or os.getenv("GROQ_MODEL", "openai/gpt-oss-120b")
        # Normalize oss-120b aliases
        if raw_model in ["oss-120b", "gpt-oss-120b"]:
            model_name = "openai/gpt-oss-120b"
        else:
            model_name = raw_model

        return ChatGroq(
            model=model_name,
            temperature=temperature,
            max_tokens=max_tokens,
            max_retries=1,
            timeout=15,
            groq_api_key=os.getenv("GROQ_API_KEY")
        )
    except Exception as e:
        print(f"⚠️ Failed to initialize ChatGroq: {e}. Falling back to deterministic reasoning.")
        return None


def extract_text_content(response: Optional[Any]) -> str:
    """Safely extracts text content whether response.content is str, list of blocks, or raw object."""
    if response is None:
        return ""
    content = getattr(response, "content", response)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                parts.append(item.get("text", ""))
            elif hasattr(item, "text"):
                parts.append(getattr(item, "text", ""))
            else:
                parts.append(str(item))
        return " ".join(p for p in parts if p).strip()
    return str(content).strip()


def get_ollama_llm(
    model: Optional[str] = None,
    temperature: float = 0.1,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None
):
    """
    Returns an initialized LangChain ChatOllama instance for:
    - Review & Quality Assurance Agent
    Supports both local Ollama (http://localhost:11434) and Cloud-hosted Ollama (e.g. https://api.ollama.ai
    or custom cloud endpoint) with optional API key authentication (Bearer token & x-api-key).
    Uses 'nemotron-3-ultra' by default.
    Returns None if Ollama is not available or initialization fails.
    """
    url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model_name = model or os.getenv("OLLAMA_MODEL", "nemotron-3-ultra")
    key = api_key or os.getenv("OLLAMA_API_KEY")

    client_kwargs = {}
    if key and key.strip() and key.strip() != "your_ollama_api_key_here":
        auth_val = key.strip() if key.strip().startswith("Bearer ") else f"Bearer {key.strip()}"
        client_kwargs["headers"] = {
            "Authorization": auth_val,
            "x-api-key": key.strip()
        }

    try:
        from langchain_ollama import ChatOllama
        kwargs = {
            "model": model_name,
            "base_url": url,
            "temperature": temperature,
            "timeout": 20
        }
        if client_kwargs:
            kwargs["client_kwargs"] = client_kwargs

        return ChatOllama(**kwargs)
    except Exception as e:
        print(f"⚠️ Failed to initialize ChatOllama ({e}). Falling back to deterministic auditor.")
        return None


def get_review_llm(
    model: Optional[str] = None,
    temperature: float = 0.1,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None
):
    """
    Primary accessor for Review & QA Agent LLM.
    Defaults to Ollama's nemotron-3-ultra model on local or cloud host.
    """
    return get_ollama_llm(model=model, temperature=temperature, base_url=base_url, api_key=api_key)


def get_gemini_llm(
    model: Optional[str] = None,
    temperature: float = 0.1,
    max_tokens: int = 2048
):
    """
    Returns an initialized LangChain ChatGoogleGenerativeAI instance (legacy support).
    """
    if not is_gemini_available():
        return None

    try:
        from langchain_google_genai import ChatGoogleGenerativeAI
        raw_model = model or os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")
        if raw_model in ["gemini-flash-latest", "gemini-2.5-flash", "gemini-1.5-flash", "gemini-3.8-flash"]:
            model_name = "gemini-3.1-flash-lite"
        else:
            model_name = raw_model

        api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
        return ChatGoogleGenerativeAI(
            model=model_name,
            temperature=temperature,
            max_output_tokens=max_tokens,
            max_retries=1,
            timeout=15,
            google_api_key=api_key
        )
    except Exception as e:
        print(f"⚠️ Failed to initialize ChatGoogleGenerativeAI: {e}. Falling back to deterministic auditor.")
        return None
