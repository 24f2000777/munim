"""
Multi-Model AI Router
=====================
Automatically rotates between free-tier AI models when one hits quota limits (429).
Priority: Gemini → Groq → Mistral → Together → OpenRouter

Supports:
  - Text generation (reports, insights, schema detection)
  - Vision/multimodal (image-to-table extraction)

All non-Gemini providers use the OpenAI-compatible API format.
No extra SDKs needed — plain httpx.Client.

Usage:
    from services.ai.model_router import router

    text = router.call_text(prompt, max_tokens=600, temperature=0.4)
    text = router.call_vision(image_bytes, "image/jpeg", prompt)
"""

import base64
import json
import logging
from datetime import datetime, timedelta, timezone

import httpx
from google import genai
from google.genai import types as genai_types

from config import settings

logger = logging.getLogger(__name__)


class AIModelRouter:
    """
    Singleton AI model router.
    Tries models in priority order, skipping ones that returned 429 recently.
    Auto-resets exhausted models after RESET_AFTER (default 1 hour).
    """

    # TEXT model priority — tried in sequence until one succeeds
    TEXT_MODELS = [
        {"provider": "gemini",     "model": "gemini-2.0-flash-lite"},
        {"provider": "gemini",     "model": "gemini-2.0-flash"},
        {"provider": "groq",       "model": "llama-3.3-70b-versatile"},
        {"provider": "groq",       "model": "mixtral-8x7b-32768"},
        {"provider": "groq",       "model": "gemma2-9b-it"},
        {"provider": "mistral",    "model": "mistral-small-latest"},
        {"provider": "together",   "model": "meta-llama/Llama-3.3-70B-Instruct-Turbo"},
        {"provider": "openrouter", "model": "deepseek/deepseek-chat-v3-0324:free"},
        {"provider": "openrouter", "model": "meta-llama/llama-3.3-70b-instruct:free"},
        {"provider": "openrouter", "model": "qwen/qwen-2.5-72b-instruct:free"},
        {"provider": "openrouter", "model": "mistralai/mistral-7b-instruct:free"},
    ]

    # VISION model priority — multimodal (image input) support
    VISION_MODELS = [
        {"provider": "gemini",     "model": "gemini-2.0-flash"},
        {"provider": "gemini",     "model": "gemini-2.0-flash-lite"},
        {"provider": "groq",       "model": "meta-llama/llama-4-scout-17b-16e-instruct"},
        {"provider": "groq",       "model": "llama-3.2-11b-vision-preview"},
        {"provider": "groq",       "model": "llama-3.2-90b-vision-preview"},
        {"provider": "openrouter", "model": "meta-llama/llama-3.2-11b-vision-instruct:free"},
        {"provider": "openrouter", "model": "qwen/qwen-2.5-vl-7b-instruct:free"},
    ]

    # Re-try exhausted models after this duration
    RESET_AFTER = timedelta(hours=1)

    def __init__(self):
        self._exhausted: dict[str, datetime] = {}  # "provider/model" → exhausted_at

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def call_text(
        self,
        prompt: str,
        max_tokens: int = 600,
        temperature: float = 0.4,
    ) -> str:
        """
        Generate text using the best available model.
        Tries models in TEXT_MODELS priority order.
        Raises RuntimeError if all models are exhausted/unavailable.
        """
        for entry in self.TEXT_MODELS:
            provider, model = entry["provider"], entry["model"]

            if not self._is_available(provider, model):
                continue
            if not self._has_key(provider):
                continue

            try:
                logger.info("[model_router] Trying %s/%s for text", provider, model)
                result = self._call_provider(
                    provider, model, prompt, max_tokens, temperature, image_bytes=None, mime_type=None
                )
                logger.info("[model_router] Success: %s/%s", provider, model)
                return result

            except Exception as exc:
                exc_str = str(exc)
                if self._is_quota_error(exc_str):
                    logger.warning(
                        "[model_router] %s/%s quota exhausted — skipping. Error: %s",
                        provider, model, exc_str[:120],
                    )
                    self._mark_exhausted(provider, model)
                else:
                    logger.warning(
                        "[model_router] %s/%s failed (non-quota): %s",
                        provider, model, exc_str[:120],
                    )

        raise RuntimeError(
            "All AI models are currently unavailable or quota-exhausted. "
            "Add API keys for Groq/OpenRouter/Mistral in .env to extend coverage."
        )

    def call_vision(
        self,
        image_bytes: bytes,
        mime_type: str,
        prompt: str,
        max_tokens: int = 2048,
    ) -> str:
        """
        Extract text/data from an image using vision-capable models.
        Tries models in VISION_MODELS priority order.
        Raises RuntimeError if all vision models are exhausted.
        """
        for entry in self.VISION_MODELS:
            provider, model = entry["provider"], entry["model"]

            if not self._is_available(provider, model):
                continue
            if not self._has_key(provider):
                continue

            try:
                logger.info("[model_router] Trying %s/%s for vision", provider, model)
                result = self._call_provider(
                    provider, model, prompt, max_tokens, 0.1,
                    image_bytes=image_bytes, mime_type=mime_type,
                )
                logger.info("[model_router] Vision success: %s/%s", provider, model)
                return result

            except Exception as exc:
                exc_str = str(exc)
                if self._is_quota_error(exc_str):
                    logger.warning(
                        "[model_router] %s/%s vision quota exhausted — skipping",
                        provider, model,
                    )
                    self._mark_exhausted(provider, model)
                else:
                    logger.warning(
                        "[model_router] %s/%s vision failed: %s",
                        provider, model, exc_str[:120],
                    )

        raise RuntimeError("All vision models are currently unavailable or quota-exhausted.")

    # ------------------------------------------------------------------
    # Internal: quota tracking
    # ------------------------------------------------------------------

    def _mark_exhausted(self, provider: str, model: str) -> None:
        key = f"{provider}/{model}"
        self._exhausted[key] = datetime.now(timezone.utc)
        logger.info("[model_router] Marked exhausted: %s (resets in %s)", key, self.RESET_AFTER)

    def _is_available(self, provider: str, model: str) -> bool:
        key = f"{provider}/{model}"
        exhausted_at = self._exhausted.get(key)
        if exhausted_at is None:
            return True
        if datetime.now(timezone.utc) - exhausted_at > self.RESET_AFTER:
            del self._exhausted[key]
            logger.info("[model_router] Reset exhausted model: %s", key)
            return True
        return False

    def _has_key(self, provider: str) -> bool:
        """Return True if the provider's API key is configured."""
        key_map = {
            "gemini":     settings.GOOGLE_API_KEY,
            "groq":       settings.GROQ_API_KEY,
            "mistral":    settings.MISTRAL_API_KEY,
            "together":   settings.TOGETHER_API_KEY,
            "openrouter": settings.OPENROUTER_API_KEY,
        }
        has = bool(key_map.get(provider, ""))
        if not has:
            logger.debug("[model_router] No API key for provider=%s — skipping", provider)
        return has

    @staticmethod
    def _is_quota_error(error_str: str) -> bool:
        lower = error_str.lower()
        return any(kw in lower for kw in (
            "429", "quota", "rate limit", "resource_exhausted",
            "too many requests", "ratelimit", "rate-limit",
        ))

    # ------------------------------------------------------------------
    # Internal: provider dispatch
    # ------------------------------------------------------------------

    def _call_provider(
        self,
        provider: str,
        model: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
        image_bytes: bytes | None,
        mime_type: str | None,
    ) -> str:
        if provider == "gemini":
            return self._call_gemini(model, prompt, max_tokens, temperature, image_bytes, mime_type)
        else:
            return self._call_openai_compatible(provider, model, prompt, max_tokens, temperature, image_bytes, mime_type)

    def _call_gemini(
        self,
        model: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
        image_bytes: bytes | None,
        mime_type: str | None,
    ) -> str:
        client = genai.Client(api_key=settings.GOOGLE_API_KEY)

        if image_bytes and mime_type:
            # Multimodal vision request
            contents = [
                genai_types.Content(parts=[
                    genai_types.Part(text=prompt),
                    genai_types.Part(
                        inline_data=genai_types.Blob(
                            mime_type=mime_type,
                            data=image_bytes,
                        )
                    ),
                ])
            ]
        else:
            contents = prompt

        response = client.models.generate_content(
            model=model,
            contents=contents,
            config=genai_types.GenerateContentConfig(
                max_output_tokens=max_tokens,
                temperature=temperature,
                top_p=0.8,
                http_options=genai_types.HttpOptions(timeout=20_000),
            ),
        )

        text = (response.text or "").strip()
        if not text:
            raise ValueError(f"Gemini {model} returned empty response")
        return text

    def _call_openai_compatible(
        self,
        provider: str,
        model: str,
        prompt: str,
        max_tokens: int,
        temperature: float,
        image_bytes: bytes | None,
        mime_type: str | None,
    ) -> str:
        """
        Single implementation for Groq, Mistral, Together, OpenRouter —
        all use the OpenAI chat completions format.
        """
        base_urls = {
            "groq":       "https://api.groq.com/openai/v1/chat/completions",
            "mistral":    "https://api.mistral.ai/v1/chat/completions",
            "together":   "https://api.together.xyz/v1/chat/completions",
            "openrouter": "https://openrouter.ai/api/v1/chat/completions",
        }
        api_keys = {
            "groq":       settings.GROQ_API_KEY,
            "mistral":    settings.MISTRAL_API_KEY,
            "together":   settings.TOGETHER_API_KEY,
            "openrouter": settings.OPENROUTER_API_KEY,
        }

        url = base_urls[provider]
        api_key = api_keys[provider]

        # Build message content — supports vision for providers that have it
        if image_bytes and mime_type:
            b64_image = base64.b64encode(image_bytes).decode("utf-8")
            content = [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{b64_image}"}},
            ]
        else:
            content = prompt

        payload = {
            "model": model,
            "messages": [{"role": "user", "content": content}],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        # OpenRouter requires these extra headers
        if provider == "openrouter":
            headers["HTTP-Referer"] = settings.APP_URL
            headers["X-Title"] = "Munim"

        with httpx.Client(timeout=25.0) as client:
            response = client.post(url, json=payload, headers=headers)

        # Raise on 429 so caller can mark as exhausted
        if response.status_code == 429:
            raise RuntimeError(f"429 quota exhausted for {provider}/{model}: {response.text[:200]}")
        response.raise_for_status()

        data = response.json()
        text = data["choices"][0]["message"]["content"].strip()
        if not text:
            raise ValueError(f"{provider}/{model} returned empty content")
        return text


# ---------------------------------------------------------------------------
# Singleton instance — import this everywhere
# ---------------------------------------------------------------------------
router = AIModelRouter()
