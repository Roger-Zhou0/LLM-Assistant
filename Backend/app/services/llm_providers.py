from __future__ import annotations

import os
from dataclasses import dataclass
from typing import List, Optional, Protocol

import httpx
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()


class LLMProvider(Protocol):
    def chat(self, messages: List[dict], model: str, temperature: float = 0.0) -> str:
        ...


@dataclass(frozen=True)
class ModelSpec:
    provider: str
    model: str
    display_name: str
    max_output_tokens: Optional[int] = None


class OpenAIProvider:
    def __init__(self, api_key: str, base_url: Optional[str] = None) -> None:
        client_kwargs = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        self._client = OpenAI(**client_kwargs)

    def chat(self, messages: List[dict], model: str, temperature: float = 0.0) -> str:
        resp = self._client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
        )
        return resp.choices[0].message.content or ""


class AnthropicProvider:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._endpoint = "https://api.anthropic.com/v1/messages"
        self._client = httpx.Client(timeout=60.0)

    def _build_payload(self, messages: List[dict], model: str, temperature: float) -> dict:
        system_messages: List[str] = []
        chat_messages: List[dict] = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content", "")
            if role == "system":
                system_messages.append(content)
            elif role in {"user", "assistant"}:
                chat_messages.append({"role": role, "content": content})

        payload = {
            "model": model,
            "max_tokens": 1024,
            "temperature": temperature,
            "messages": chat_messages,
        }
        if system_messages:
            payload["system"] = "\n".join(system_messages)
        return payload

    def chat(self, messages: List[dict], model: str, temperature: float = 0.0) -> str:
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }
        payload = self._build_payload(messages, model, temperature)
        resp = self._client.post(self._endpoint, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        # Claude response content is a list of blocks
        parts = data.get("content", [])
        return "".join(part.get("text", "") for part in parts)


def build_provider(provider: str) -> LLMProvider:
    provider = provider.lower()
    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        return OpenAIProvider(api_key=api_key)
    if provider == "deepseek":
        api_key = os.getenv("DEEPSEEK_API_KEY")
        if not api_key:
            raise RuntimeError("DEEPSEEK_API_KEY is not set")
        base_url = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        return OpenAIProvider(api_key=api_key, base_url=base_url)
    if provider == "together":
        api_key = os.getenv("TOGETHER_API_KEY")
        if not api_key:
            raise RuntimeError("TOGETHER_API_KEY is not set")
        base_url = os.getenv("TOGETHER_BASE_URL", "https://api.together.xyz/v1")
        return OpenAIProvider(api_key=api_key, base_url=base_url)
    if provider == "anthropic":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        return AnthropicProvider(api_key=api_key)
    raise RuntimeError(f"Unsupported provider: {provider}")
