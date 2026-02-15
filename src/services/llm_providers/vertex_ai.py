"""Google Vertex AI (Gemini) LLMプロバイダ"""

from __future__ import annotations

import asyncio
import logging
from functools import partial

from src.models.settings import LLMProviderConfig
from src.services.llm_providers.base import BaseLLMProvider, LLMResponse
from src.utils.config_loader import get_env

logger = logging.getLogger(__name__)

try:
    import vertexai
    from vertexai.generative_models import Content, GenerativeModel, Part
except ImportError:
    vertexai = None  # type: ignore[assignment]
    GenerativeModel = None  # type: ignore[assignment,misc]
    Content = None  # type: ignore[assignment,misc]
    Part = None  # type: ignore[assignment,misc]


class VertexAIProvider(BaseLLMProvider):
    """Google Vertex AI (Gemini) を利用するプロバイダ"""

    def __init__(self, config: LLMProviderConfig) -> None:
        self.config = config
        self.project_id: str = get_env("VERTEX_AI_PROJECT_ID", "") or ""
        self.location: str = get_env("VERTEX_AI_LOCATION", "us-central1") or "us-central1"
        self.model_name: str = config.model or "gemini-1.5-flash"

        self._initialized = False
        if vertexai is not None and self.validate_config():
            vertexai.init(project=self.project_id, location=self.location)
            self._initialized = True

    def _build_contents(self, messages: list[dict]) -> list:
        """メッセージリストを Vertex AI Content オブジェクトに変換する。"""
        contents = []
        for msg in messages:
            role = msg.get("role", "user")
            # Vertex AI は "user" と "model" のロールのみ受け付ける
            vertex_role = "model" if role == "assistant" else "user"
            contents.append(
                Content(role=vertex_role, parts=[Part.from_text(msg["content"])])
            )
        return contents

    def _sync_generate(
        self,
        system_prompt: str,
        messages: list[dict],
        max_tokens: int,
        temperature: float,
    ) -> LLMResponse:
        """同期的に Vertex AI API を呼び出す。"""
        model = GenerativeModel(
            model_name=self.model_name,
            system_instruction=system_prompt if system_prompt else None,
        )

        generation_config = {
            "max_output_tokens": max_tokens,
            "temperature": temperature,
        }

        contents = self._build_contents(messages)

        response = model.generate_content(
            contents=contents,
            generation_config=generation_config,
        )

        content_text = response.text if response.text else ""

        # usage_metadata から token 数を取得
        prompt_tokens = 0
        completion_tokens = 0
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            prompt_tokens = getattr(response.usage_metadata, "prompt_token_count", 0)
            completion_tokens = getattr(
                response.usage_metadata, "candidates_token_count", 0
            )

        return LLMResponse(
            content=content_text,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

    async def generate(
        self,
        system_prompt: str,
        messages: list[dict],
        max_tokens: int,
        temperature: float = 0.7,
    ) -> LLMResponse:
        if not self._initialized:
            raise RuntimeError(
                "Vertex AI が初期化されていません。"
                "google-cloud-aiplatform パッケージのインストールと環境変数の設定を確認してください。"
            )

        # Vertex AI SDK は同期APIのため、asyncio でラップする
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            None,
            partial(
                self._sync_generate,
                system_prompt,
                messages,
                max_tokens,
                temperature,
            ),
        )

    def validate_config(self) -> bool:
        if vertexai is None or GenerativeModel is None:
            logger.warning(
                "google-cloud-aiplatform / vertexai パッケージがインストールされていません。"
            )
            return False
        if not self.project_id:
            logger.warning("VERTEX_AI_PROJECT_ID が設定されていません。")
            return False
        return True
