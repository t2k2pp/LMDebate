"""Ollama LLMプロバイダ"""

from __future__ import annotations

import logging

from src.models.settings import LLMProviderConfig
from src.services.llm_providers.base import BaseLLMProvider, LLMResponse

logger = logging.getLogger(__name__)

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore[assignment]


class OllamaProvider(BaseLLMProvider):
    """Ollama REST API を利用するプロバイダ"""

    @staticmethod
    def list_models(base_url: str) -> list[str]:
        """指定されたベースURLからOllamaの利用可能なモデル一覧を取得する。

        Parameters
        ----------
        base_url : Ollama サーバーのベースURL (例: http://localhost:11434)

        Returns
        -------
        list[str]
            利用可能なモデル名のリスト
        """
        if httpx is None:
            raise RuntimeError("httpx パッケージがインストールされていません。")

        with httpx.Client(base_url=base_url, timeout=10.0) as client:
            response = client.get("/api/tags")
            response.raise_for_status()
            data = response.json()
            models = data.get("models", [])
            return [m["name"] for m in models if "name" in m]

    def __init__(self, config: LLMProviderConfig) -> None:
        self.config = config
        self.base_url: str = config.base_url or "http://localhost:11434"
        self.model: str = config.model or "llama3"

        self._client: httpx.AsyncClient | None = None
        if httpx is not None and self.validate_config():
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
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
                "Ollama クライアントが初期化されていません。"
                "httpx パッケージのインストールを確認してください。"
            )

        request_messages: list[dict] = []
        if system_prompt:
            request_messages.append({"role": "system", "content": system_prompt})
        request_messages.extend(messages)

        payload = {
            "model": self.model,
            "messages": request_messages,
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": temperature,
            },
        }

        response = await self._client.post("/api/chat", json=payload)
        response.raise_for_status()
        data = response.json()

        content = data.get("message", {}).get("content", "")

        # Ollama はトークン数を eval_count / prompt_eval_count で返す
        prompt_tokens = data.get("prompt_eval_count", 0)
        completion_tokens = data.get("eval_count", 0)

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
        if not self.model:
            logger.warning("model が設定されていません。")
            return False
        return True
