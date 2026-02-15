"""LLMプロバイダ基底クラス"""

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class LLMResponse:
    """LLMからのレスポンス"""
    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0


class BaseLLMProvider(ABC):
    """LLMプロバイダの基底クラス"""

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        messages: list[dict],
        max_tokens: int,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """
        LLMにリクエストを送信し、レスポンスを返す。
        タイムアウトは設けない（ローカルLLM対応のため）。
        """
        pass

    @abstractmethod
    def validate_config(self) -> bool:
        """接続設定の妥当性を検証する"""
        pass
