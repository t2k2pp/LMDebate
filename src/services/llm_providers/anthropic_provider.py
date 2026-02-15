"""Anthropic (Claude) LLMプロバイダ"""

from __future__ import annotations

import logging

from src.models.settings import LLMProviderConfig
from src.services.llm_providers.base import BaseLLMProvider, LLMResponse
from src.utils.config_loader import get_env

logger = logging.getLogger(__name__)

try:
    from anthropic import AsyncAnthropic
except ImportError:
    AsyncAnthropic = None  # type: ignore[assignment,misc]


class AnthropicProvider(BaseLLMProvider):
    """Anthropic Claude API を利用するプロバイダ"""

    def __init__(self, config: LLMProviderConfig) -> None:
        self.config = config
        self.api_key: str = get_env("ANTHROPIC_API_KEY", "") or ""
        self.model: str = config.model or "claude-3-5-sonnet-20241022"

        self._client: AsyncAnthropic | None = None
        if AsyncAnthropic is not None and self.validate_config():
            self._client = AsyncAnthropic(
                api_key=self.api_key,
                timeout=None,
            )

    async def generate(
        self,
        system_prompt: str,
        messages: list[dict],
        max_tokens: int,
        temperature: float = 0.7,
    ) -> LLMResponse:
        if self._client is None:
            raise RuntimeError(
                "Anthropic クライアントが初期化されていません。"
                "anthropic パッケージのインストールと環境変数の設定を確認してください。"
            )

        # Anthropic API: system prompt は system パラメータで渡す
        response = await self._client.messages.create(
            model=self.model,
            system=system_prompt if system_prompt else "",
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        content_text = ""
        for block in response.content:
            if block.type == "text":
                content_text += block.text

        return LLMResponse(
            content=content_text,
            prompt_tokens=response.usage.input_tokens,
            completion_tokens=response.usage.output_tokens,
        )

    def validate_config(self) -> bool:
        if AsyncAnthropic is None:
            logger.warning("anthropic パッケージがインストールされていません。")
            return False
        if not self.api_key:
            logger.warning("ANTHROPIC_API_KEY が設定されていません。")
            return False
        if not self.model:
            logger.warning("model が設定されていません。")
            return False
        return True
