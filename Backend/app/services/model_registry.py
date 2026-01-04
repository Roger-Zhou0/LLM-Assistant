from __future__ import annotations

import os
from typing import List, Optional

from dotenv import load_dotenv

load_dotenv()

from app.services.llm_providers import ModelSpec


_CATALOG: List[ModelSpec] = [
    ModelSpec(provider="openai", model="gpt-5.2", display_name="OpenAI GPT-5.2"),
    ModelSpec(provider="anthropic", model="claude-sonnet-4-5", display_name="Claude Sonnet 4.5"),
    ModelSpec(provider="anthropic", model="claude-opus-4-5", display_name="Claude Opus 4.5"),
    ModelSpec(provider="deepseek", model="deepseek-chat", display_name="DeepSeek Chat"),
    ModelSpec(provider="deepseek", model="deepseek-reasoner", display_name="DeepSeek Reasoner"),
    ModelSpec(provider="together", model="moonshotai/Kimi-K2-Thinking", display_name="Together Kimi K2 Thinking"),
]

_TOGETHER_ENV_MODELS = os.getenv("TOGETHER_MODELS")
if _TOGETHER_ENV_MODELS:
    for raw in _TOGETHER_ENV_MODELS.split(","):
        model_name = raw.strip()
        if model_name:
            _CATALOG.append(
                ModelSpec(
                    provider="together",
                    model=model_name,
                    display_name=f"Together {model_name}",
                )
            )


def _provider_enabled(provider: str) -> bool:
    provider = provider.lower()
    if provider == "openai":
        return bool(os.getenv("OPENAI_API_KEY"))
    if provider == "anthropic":
        return bool(os.getenv("ANTHROPIC_API_KEY"))
    if provider == "deepseek":
        return bool(os.getenv("DEEPSEEK_API_KEY"))
    if provider == "together":
        return bool(os.getenv("TOGETHER_API_KEY"))
    return False


def list_available_models() -> List[ModelSpec]:
    return [spec for spec in _CATALOG if _provider_enabled(spec.provider)]


def resolve_default_model() -> Optional[ModelSpec]:
    preferred_provider = os.getenv("DEFAULT_LLM_PROVIDER")
    preferred_model = os.getenv("DEFAULT_LLM_MODEL")
    if preferred_provider:
        preferred_provider = preferred_provider.lower()
    available = list_available_models()
    if preferred_provider and preferred_model:
        for spec in available:
            if spec.provider == preferred_provider and spec.model == preferred_model:
                return spec
    if available:
        return available[0]
    return None


def lookup_model(provider: str, model: str) -> Optional[ModelSpec]:
    for spec in list_available_models():
        if spec.provider == provider and spec.model == model:
            return spec
    return None
