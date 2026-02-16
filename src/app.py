"""アプリケーションオーケストレーター

全サービスの初期化と依存性注入を管理する。
"""

from __future__ import annotations

import logging
from pathlib import Path

from src.utils.config_loader import PROJECT_ROOT, load_env, load_app_settings, load_llm_providers
from src.models.settings import AppSettings
from src.services.history_service import HistoryService
from src.services.llm_service import LLMService
from src.services.preset_service import PresetService
from src.services.attachment_service import AttachmentService
from src.services.debate_service import DebateService
from src.services.search_service import SearchService
from src.services.export_service import ExportService

logger = logging.getLogger(__name__)


class App:
    """アプリケーション全体を管理するクラス。

    全サービスのライフサイクルと依存関係を管理する。
    UIから各サービスにアクセスするための統一的なインターフェースを提供する。
    """

    def __init__(self) -> None:
        # .env 読み込み
        load_env()

        # 設定読み込み
        self._settings: AppSettings = load_app_settings()

        # パスを絶対パスに変換
        self._db_path = str(PROJECT_ROOT / self._settings.db_path)
        self._attachments_dir = str(PROJECT_ROOT / self._settings.attachments_dir)
        self._export_dir = str(PROJECT_ROOT / self._settings.export_dir)

        # サービス初期化
        self._history_service: HistoryService = HistoryService(self._db_path)

        self._llm_service: LLMService = LLMService()
        self._load_llm_providers()

        self._preset_service: PresetService = PresetService(
            history_service=self._history_service,
            presets_json_path=str(PROJECT_ROOT / "config" / "role_presets.json"),
        )

        self._attachment_service: AttachmentService = AttachmentService(self._attachments_dir)

        self._search_service: SearchService = SearchService(
            base_url=self._settings.searxng_base_url,
        )

        self._debate_service: DebateService = DebateService(
            history_service=self._history_service,
            llm_service=self._llm_service,
            preset_service=self._preset_service,
            attachment_service=self._attachment_service,
            search_service=self._search_service,
        )

        self._export_service: ExportService = ExportService(self._export_dir)

        logger.info("アプリケーションの初期化が完了しました。")

    def _load_llm_providers(self) -> None:
        """LLMプロバイダ設定を読み込み、サービスに登録する。"""
        try:
            configs = load_llm_providers()
            self._llm_service.load_providers(configs)
        except Exception as e:
            logger.warning("LLMプロバイダの読み込みに失敗しました: %s", e)

    # --- プロパティ ---

    @property
    def settings(self) -> AppSettings:
        return self._settings

    @property
    def history_service(self) -> HistoryService:
        return self._history_service

    @property
    def llm_service(self) -> LLMService:
        return self._llm_service

    @property
    def preset_service(self) -> PresetService:
        return self._preset_service

    @property
    def attachment_service(self) -> AttachmentService:
        return self._attachment_service

    @property
    def debate_service(self) -> DebateService:
        return self._debate_service

    @property
    def search_service(self) -> SearchService:
        return self._search_service

    @property
    def export_service(self) -> ExportService:
        return self._export_service
