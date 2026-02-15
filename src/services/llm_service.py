"""LLMサービス - プロバイダのファクトリ・オーケストレーション"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.models.settings import LLMProviderConfig
from src.services.llm_providers.base import BaseLLMProvider, LLMResponse

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# プロバイダ type 文字列 -> (モジュールパス, クラス名) のマッピング
_PROVIDER_REGISTRY: dict[str, tuple[str, str]] = {
    "azure_openai": (
        "src.services.llm_providers.azure_openai",
        "AzureOpenAIProvider",
    ),
    "anthropic": (
        "src.services.llm_providers.anthropic_provider",
        "AnthropicProvider",
    ),
    "vertex_ai": (
        "src.services.llm_providers.vertex_ai",
        "VertexAIProvider",
    ),
    "ollama": (
        "src.services.llm_providers.ollama",
        "OllamaProvider",
    ),
    "lmstudio": (
        "src.services.llm_providers.lmstudio",
        "LMStudioProvider",
    ),
    "llamacpp": (
        "src.services.llm_providers.llamacpp",
        "LlamaCppProvider",
    ),
}


class LLMService:
    """LLMプロバイダのファクトリ・管理サービス"""

    def __init__(self) -> None:
        self._providers: dict[str, BaseLLMProvider] = {}
        self._configs: dict[str, LLMProviderConfig] = {}
        self._init_errors: dict[str, str] = {}

    def load_providers(self, configs: list[LLMProviderConfig]) -> None:
        """設定リストからプロバイダインスタンスを生成・登録する。"""
        for config in configs:
            self._configs[config.id] = config
            try:
                provider = self.create_provider(config)
                self._providers[config.id] = provider
                logger.info("プロバイダ '%s' (%s) を登録しました。", config.id, config.type)
            except Exception as e:
                self._init_errors[config.id] = str(e)
                logger.warning(
                    "プロバイダ '%s' (%s) の初期化に失敗しました。",
                    config.id,
                    config.type,
                    exc_info=True,
                )

    @staticmethod
    def create_provider(config: LLMProviderConfig) -> BaseLLMProvider:
        """LLMProviderConfig からプロバイダインスタンスを生成する。"""
        provider_type = config.type
        if provider_type not in _PROVIDER_REGISTRY:
            raise ValueError(f"未対応のプロバイダタイプです: {provider_type}")

        module_path, class_name = _PROVIDER_REGISTRY[provider_type]

        # 遅延インポートにより、未インストールの SDK があってもエラーにならない
        import importlib

        try:
            module = importlib.import_module(module_path)
        except ImportError as e:
            raise ImportError(
                f"プロバイダ '{provider_type}' に必要なパッケージがインストールされていません: {e}"
            ) from e

        provider_class = getattr(module, class_name)
        return provider_class(config)

    def get_provider(self, provider_id: str) -> BaseLLMProvider:
        """登録済みプロバイダを取得する。"""
        if provider_id not in self._providers:
            raise KeyError(f"プロバイダ '{provider_id}' は登録されていません。")
        return self._providers[provider_id]

    def get_config(self, provider_id: str) -> LLMProviderConfig:
        """登録済みプロバイダの設定を取得する。"""
        if provider_id not in self._configs:
            raise KeyError(f"プロバイダ '{provider_id}' の設定が見つかりません。")
        return self._configs[provider_id]

    def list_provider_ids(self) -> list[str]:
        """登録済みプロバイダIDの一覧を返す。"""
        return list(self._providers.keys())

    def list_configs(self) -> list[LLMProviderConfig]:
        """登録済みプロバイダ設定の一覧を返す。"""
        return list(self._configs.values())

    def get_init_errors(self) -> dict[str, str]:
        """初期化に失敗したプロバイダのエラー情報を返す。"""
        return dict(self._init_errors)

    def add_provider(self, config: LLMProviderConfig) -> None:
        """新しいプロバイダを追加し、JSONに保存する。"""
        if config.id in self._configs:
            raise ValueError(f"プロバイダID '{config.id}' は既に存在します。")
        self._configs[config.id] = config
        try:
            provider = self.create_provider(config)
            self._providers[config.id] = provider
            self._init_errors.pop(config.id, None)
            logger.info("プロバイダ '%s' (%s) を追加しました。", config.id, config.type)
        except Exception as e:
            self._init_errors[config.id] = str(e)
            logger.warning(
                "プロバイダ '%s' (%s) の初期化に失敗しました。設定は保存されます。",
                config.id,
                config.type,
                exc_info=True,
            )
        self._save_to_json()

    def update_provider(self, config: LLMProviderConfig) -> None:
        """既存プロバイダの設定を更新し、JSONに保存する。"""
        if config.id not in self._configs:
            raise KeyError(f"プロバイダ '{config.id}' は存在しません。")
        self._configs[config.id] = config
        try:
            provider = self.create_provider(config)
            self._providers[config.id] = provider
            self._init_errors.pop(config.id, None)
        except Exception as e:
            self._providers.pop(config.id, None)
            self._init_errors[config.id] = str(e)
            logger.warning(
                "プロバイダ '%s' の再初期化に失敗しました。",
                config.id,
                exc_info=True,
            )
        self._save_to_json()

    def delete_provider(self, provider_id: str) -> None:
        """プロバイダを削除し、JSONに保存する。"""
        if provider_id not in self._configs:
            raise KeyError(f"プロバイダ '{provider_id}' は存在しません。")
        self._configs.pop(provider_id, None)
        self._providers.pop(provider_id, None)
        self._init_errors.pop(provider_id, None)
        logger.info("プロバイダ '%s' を削除しました。", provider_id)
        self._save_to_json()

    def _save_to_json(self) -> None:
        """現在のプロバイダ設定をJSONファイルに保存する。"""
        from src.utils.config_loader import save_llm_providers

        save_llm_providers(list(self._configs.values()))

    def fetch_models(self, provider_type: str, base_url: str) -> list[str]:
        """ローカルLLMプロバイダから利用可能なモデル一覧を取得する。

        Parameters
        ----------
        provider_type : プロバイダタイプ ("ollama", "lmstudio", "llamacpp")
        base_url : サーバーのベースURL

        Returns
        -------
        list[str]
            利用可能なモデル名のリスト

        Raises
        ------
        ValueError
            モデル一覧取得に対応していないプロバイダタイプの場合
        """
        if provider_type not in _PROVIDER_REGISTRY:
            raise ValueError(f"未対応のプロバイダタイプです: {provider_type}")

        import importlib

        module_path, class_name = _PROVIDER_REGISTRY[provider_type]
        module = importlib.import_module(module_path)
        provider_class = getattr(module, class_name)

        if not hasattr(provider_class, "list_models"):
            raise ValueError(
                f"プロバイダタイプ '{provider_type}' はモデル一覧取得に対応していません。"
            )

        return provider_class.list_models(base_url)

    async def generate(
        self,
        provider_id: str,
        system_prompt: str,
        messages: list[dict],
        max_tokens: int,
        temperature: float = 0.7,
    ) -> LLMResponse:
        """
        指定プロバイダでLLMリクエストを実行する。

        Args:
            provider_id: 使用するプロバイダのID
            system_prompt: システムプロンプト
            messages: メッセージリスト（role/content の dict）
            max_tokens: 最大生成トークン数
            temperature: 生成温度

        Returns:
            LLMResponse: LLMからのレスポンス
        """
        provider = self.get_provider(provider_id)
        return await provider.generate(
            system_prompt=system_prompt,
            messages=messages,
            max_tokens=max_tokens,
            temperature=temperature,
        )
