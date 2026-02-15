"""llama.cpp サーバー LLMプロバイダ"""

from __future__ import annotations

import logging

from src.models.settings import LLMProviderConfig
from src.services.llm_providers.base import BaseLLMProvider, LLMResponse

logger = logging.getLogger(__name__)

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore[assignment]


class LlamaCppProvider(BaseLLMProvider):
    """llama.cpp HTTP サーバー (/completion エンドポイント) を利用するプロバイダ"""

    def __init__(self, config: LLMProviderConfig) -> None:
        self.config = config
        self.base_url: str = config.base_url or "http://localhost:8080"

        self._client: httpx.AsyncClient | None = None
        if httpx is not None and self.validate_config():
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=None,
            )

    def _build_prompt(self, system_prompt: str, messages: list[dict]) -> str:
        """system_prompt とメッセージリストから単一のプロンプト文字列を構築する。"""
        parts: list[str] = []
        if system_prompt:
            parts.append(f"### System:\n{system_prompt}\n")
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "user":
                parts.append(f"### User:\n{content}\n")
            elif role == "assistant":
                parts.append(f"### Assistant:\n{content}\n")
            else:
                parts.append(f"### {role.capitalize()}:\n{content}\n")
        # アシスタントの応答を促すプレフィックス
        parts.append("### Assistant:\n")
        return "\n".join(parts)

    async def generate(
        self,
        system_prompt: str,
        messages: list[dict],
        max_tokens: int,
        temperature: float = 0.7,
    ) -> LLMResponse:
        if self._client is None:
            raise RuntimeError(
                "llama.cpp クライアントが初期化されていません。"
                "httpx パッケージのインストールを確認してください。"
            )

        prompt = self._build_prompt(system_prompt, messages)

        payload = {
            "prompt": prompt,
            "n_predict": max_tokens,
            "temperature": temperature,
            "stop": ["### User:", "### System:"],
            "stream": False,
        }

        response = await self._client.post("/completion", json=payload)
        response.raise_for_status()
        data = response.json()

        content = data.get("content", "")

        # llama.cpp サーバーは tokens_predicted / tokens_evaluated を返す
        prompt_tokens = data.get("tokens_evaluated", 0)
        completion_tokens = data.get("tokens_predicted", 0)

        return LLMResponse(
            content=content,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    def validate_config(self) -> bool:
        if httpx is None:
            logger.warning("httpx パッケージがインストールされていません。")
            return False
        if not self.base_url:
            logger.warning("base_url が設定されていません。")
            return False
        return True
