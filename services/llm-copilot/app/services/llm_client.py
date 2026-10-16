# OpenAI/Gemini wrapper

"""
LLM Client — Unified wrapper for free/local LLM runtimes.
Supports: Ollama (local), Gemini (free tier), OpenAI.
"""
from typing import Optional, Dict, Any
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings


class LLMClient:
    """Unified LLM client with fallback support."""

    def __init__(self):
        self.provider = settings.llm_provider.lower()
        self._client = None
        self._init_client()

    def _init_client(self):
        """Initialize the appropriate LLM client."""
        if self.provider == "ollama":
            try:
                import ollama
                self._client = ollama
                logger.info(f"Ollama client initialized (model: {settings.ollama_model})")
            except ImportError:
                logger.warning("Ollama not installed, falling back to Gemini")
                self.provider = "gemini"
                self._init_gemini()
        elif self.provider == "gemini":
            self._init_gemini()
        elif self.provider == "openai":
            self._init_openai()
        else:
            raise ValueError(f"Unknown LLM provider: {self.provider}")

    def _init_gemini(self):
        import google.generativeai as genai
        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY not set in .env")
        genai.configure(api_key=settings.gemini_api_key)
        self._client = genai.GenerativeModel(settings.gemini_model)
        logger.info(f"Gemini client initialized (model: {settings.gemini_model})")

    def _init_openai(self):
        from openai import OpenAI
        self._client = OpenAI()
        logger.info("OpenAI client initialized")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    def generate(self, prompt: str, system_prompt: Optional[str] = None, temperature: float = 0.3) -> str:
        """Generate text from the LLM with retry logic."""
        try:
            if self.provider == "ollama":
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})
                response = self._client.chat(model=settings.ollama_model, messages=messages)
                return response["message"]["content"]

            elif self.provider == "gemini":
                full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
                response = self._client.generate_content(
                    full_prompt,
                    generation_config={"temperature": temperature},
                )
                return response.text

            elif self.provider == "openai":
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})
                response = self._client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=messages,
                    temperature=temperature,
                )
                return response.choices[0].message.content

        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise


# Singleton
llm_client = LLMClient()