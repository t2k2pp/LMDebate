"""Azure OpenAI LLMプロバイダ"""

from __future__ import annotations

import logging

from src.models.settings import LLMProviderConfig
from src.services.llm_providers.base import BaseLLMProvider, LLMResponse
from src.utils.config_loader import get_env

logger = logging.getLogger(__name__)

try:
    from openai import AsyncAzureOpenAI
except ImportError:
    AsyncAzureOpenAI = None  # type: ignore[assignment,misc]


class AzureOpenAIProvider(BaseLLMProvider):
    """Azure OpenAI API を利用するプロバイダ"""

    def __init__(self, config: LLMProviderConfig) -> None:
        self.config = config
        self.api_key: str = get_env("AZURE_OPENAI_API_KEY", "") or ""
        self.endpoint: str = get_env("AZURE_OPENAI_ENDPOINT", "") or ""
        self.deployment_name: str = config.deployment_name or ""
        self.api_version: str = config.api_version or "2024-08-01-preview"

        self._client: AsyncAzureOpenAI | None = None
        if AsyncAzureOpenAI is not None and self.validate_config():
            self._client = AsyncAzureOpenAI(
                api_key=self.api_key,
                azure_endpoint=self.endpoint,
                api_version=self.api_version,
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
                "Azure OpenAI クライアントが初期化されていません。"
                "openai パッケージのインストールと環境変数の設定を確認してください。"
            )

        request_messages: list[dict] = []
        if system_prompt:
            request_messages.append({"role": "system", "content": system_prompt})
        request_messages.extend(messages)

        response = await self._client.chat.completions.create(
            model=self.deployment_name,
            messages=request_messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )

        choice = response.choices[0]
        usage = response.usage

        return LLMResponse(
            content=choice.message.content or "",
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
        )

    def validate_config(self) -> bool:
        if AsyncAzureOpenAI is None:
            logger.warning("openai パッケージがインストールされていません。")
            return False
        if not self.api_key:
            logger.warning("AZURE_OPENAI_API_KEY が設定されていません。")
            return False
        if not self.endpoint:
            logger.warning("AZURE_OPENAI_ENDPOINT が設定されていません。")
            return False
        if not self.deployment_name:
            logger.warning("deployment_name が設定されていません。")
            return False
        return True
