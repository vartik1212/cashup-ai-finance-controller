"""
ReconAI — Gemini API Client Manager
====================================
Centralized Gemini client handling:
- Primary model: gemini-3.7-flash
- Fallback model: gemini-2.5-flash
- Uses official Google GenAI Python SDK (`google-genai`)
- Strict security: Never prints or logs API keys
- Automatic graceful fallback when API key is missing or quota is exhausted
"""

from __future__ import annotations

import os
import time
import logging
from pathlib import Path
from typing import Optional, Tuple, Any

# Attempt to load local .env if present without raising if python-dotenv is missing
_ENV_LOADED = False

def _load_env_file():
    global _ENV_LOADED
    if _ENV_LOADED:
        return
    _ENV_LOADED = True
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        try:
            with open(env_path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        v = v.strip().strip('"').strip("'")
                        if k and not os.environ.get(k):
                            os.environ[k] = v
        except Exception:
            pass

_load_env_file()

PRIMARY_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.7-flash")
FALLBACK_MODEL = os.environ.get("GEMINI_FALLBACK_MODEL", "gemini-3.6-flash")

logger = logging.getLogger("reconai.gemini")


def get_api_key() -> Optional[str]:
    """Retrieve the Gemini API key from environment without logging it."""
    key = os.environ.get("GEMINI_API_KEY")
    if key and key.strip():
        return key.strip()
    return None


def is_gemini_configured() -> bool:
    """Check whether a non-empty Gemini API key is configured."""
    return get_api_key() is not None


def get_genai_client() -> Optional[Any]:
    """Instantiate and return the official Google GenAI client if key is configured."""
    api_key = get_api_key()
    if not api_key:
        return None
    try:
        from google import genai
        return genai.Client(api_key=api_key, http_options={"timeout": 15000})
    except Exception as e:
        logger.error(f"Failed to initialize Google GenAI Client: {e}")
        return None


def generate_content_with_fallback(
    prompt: str,
    system_instruction: Optional[str] = None,
    response_schema: Optional[Any] = None,
    timeout_seconds: float = 12.0,
) -> Tuple[Optional[str], Optional[str], float, Optional[str]]:
    """
    Executes content generation using primary model (gemini-3.7-flash).
    Falls back to gemini-3.6-flash and gemini-flash-latest on error.

    Returns:
        (content_text, model_used, latency_ms, error_message)
    """
    client = get_genai_client()
    if not client:
        return None, None, 0.0, "GEMINI_API_KEY is not configured"

    from google.genai import types

    config_kwargs: dict = {}
    if system_instruction:
        config_kwargs["system_instruction"] = system_instruction
    if response_schema:
        config_kwargs["response_mime_type"] = "application/json"
        config_kwargs["response_schema"] = response_schema

    gen_config = types.GenerateContentConfig(**config_kwargs) if config_kwargs else None

    # Candidate models to try in sequence
    models_to_try = [PRIMARY_MODEL, FALLBACK_MODEL, "gemini-flash-latest"]
    # De-duplicate while preserving order
    seen = set()
    candidate_models = [m for m in models_to_try if not (m in seen or seen.add(m))]

    last_error = None
    t0 = time.perf_counter()

    for model_name in candidate_models:
        t_model = time.perf_counter()
        # Try up to 2 attempts per model for transient server issues
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=gen_config,
                )
                latency = round((time.perf_counter() - t_model) * 1000, 2)
                if response and response.text:
                    return response.text, model_name, latency, None
            except Exception as e:
                last_error = e
                err_str = str(e)
                # If 404 not found, immediately break to next model
                if "404" in err_str or "NOT_FOUND" in err_str:
                    logger.warning("Model %s not found. Trying next candidate...", model_name)
                    break
                # If 429 quota exhausted, fast-fail immediately across all models to prevent hanging
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
                    logger.warning("Gemini quota exhausted (429). Fast-failing without hanging.")
                    return None, None, round((time.perf_counter() - t0) * 1000, 2), "RESOURCE_EXHAUSTED"
                # If transient error, brief pause before 2nd attempt
                if attempt == 0:
                    time.sleep(0.5)

    total_latency = round((time.perf_counter() - t0) * 1000, 2)
    err_msg = f"All Gemini models failed: {type(last_error).__name__} {last_error}"
    logger.error(err_msg)
    return None, None, total_latency, err_msg

