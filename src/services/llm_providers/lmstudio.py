"""LM Studio LLMプロバイダ"""

from __future__ import annotations

import logging

from src.models.settings import LLMProviderConfig
from src.services.llm_providers.base import BaseLLMProvider, LLMResponse

logger = logging.getLogger(__name__)

try:
    from openai import AsyncOpenAI
except ImportError:
    AsyncOpenAI = None  # type: ignore[assignment,misc]


class LMStudioProvider(BaseLLMProvider):
    """LM Studio (OpenAI互換API) を利用するプロバイダ"""

    def __init__(self, config: LLMProviderConfig) -> None:
        self.config = config
        self.base_url: str = config.base_url or "http://localhost:1234/v1"
        # LM Studio ではモデル名は任意（ロード済みモデルが使用される）
        self.model: str = config.model or "local-model"

        self._client: AsyncOpenAI | None = None
        if AsyncOpenAI is not None and self.validate_config():
            self._client = AsyncOpenAI(
                base_url=self.base_url,
                api_key="lm-studio",  # LM Studio は API キー不要だがダミー値が必要
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
                "LM Studio クライアントが初期化されていません。"
                "openai パッケージのインストールを確認してください。"
            )

        request_messages: list[dict] = []
        if system_prompt:
            request_messages.append({"role": "system", "content": system_prompt})
        request_messages.extend(messages)

        response = await self._client.chat.completions.create(
            model=self.model,
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
        if AsyncOpenAI is None:
            logger.warning("openai パッケージがインストールされていません。")
            return False
        if not self.base_url:
            logger.warning("base_url が設定されていません。")
            return False
        return True
