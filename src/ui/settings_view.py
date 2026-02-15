"""LLM設定画面"""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path
from typing import TYPE_CHECKING

import customtkinter as ctk

if TYPE_CHECKING:
    from src.models.settings import LLMProviderConfig


class _ProviderCard(ctk.CTkFrame):
    """LLMプロバイダ情報カード。"""

    _TYPE_LABELS = {
        "azure_openai": "Azure OpenAI",
        "anthropic": "Anthropic",
        "vertex_ai": "Google Vertex AI",
        "ollama": "Ollama (ローカル)",
        "lmstudio": "LM Studio (ローカル)",
        "llamacpp": "Llama.cpp (ローカル)",
    }

    def __init__(
        self,
        master,
        config: LLMProviderConfig,
        app=None,
        **kwargs,
    ):
        super().__init__(master, corner_radius=8, **kwargs)
        self._config = config
        self._app = app

        self.grid_columnconfigure(1, weight=1)

        row = 0

        # 名前
        ctk.CTkLabel(
            self,
            text=config.name,
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        ).grid(row=row, column=0, columnspan=2, sticky="w", padx=12, pady=(8, 2))
        row += 1

        # タイプ
        type_label = self._TYPE_LABELS.get(config.type, config.type)
        ctk.CTkLabel(
            self,
            text=f"タイプ: {type_label}",
            anchor="w",
            text_color="gray",
        ).grid(row=row, column=0, columnspan=2, sticky="w", padx=12, pady=1)
        row += 1

        # モデル / デプロイメント情報
        model_info = ""
        if config.model:
            model_info = f"モデル: {config.model}"
        elif config.deployment_name:
            model_info = f"デプロイメント: {config.deployment_name}"
        if model_info:
            ctk.CTkLabel(
                self, text=model_info, anchor="w", text_color="gray"
            ).grid(row=row, column=0, columnspan=2, sticky="w", padx=12, pady=1)
            row += 1

        # ベースURL（ローカルプロバイダ用）
        if config.base_url:
            ctk.CTkLabel(
                self, text=f"URL: {config.base_url}", anchor="w", text_color="gray"
            ).grid(row=row, column=0, columnspan=2, sticky="w", padx=12, pady=1)
            row += 1

        # デフォルト設定
        ctk.CTkLabel(
            self,
            text=f"最大トークン: {config.default_max_tokens}  |  温度: {config.default_temperature}",
            anchor="w",
            text_color="gray",
            font=ctk.CTkFont(size=11),
        ).grid(row=row, column=0, columnspan=2, sticky="w", padx=12, pady=1)
        row += 1

        # 接続テストボタン + ステータス
        test_frame = ctk.CTkFrame(self, fg_color="transparent")
        test_frame.grid(row=row, column=0, columnspan=2, sticky="w", padx=12, pady=(4, 8))

        self._test_btn = ctk.CTkButton(
            test_frame,
            text="接続テスト",
            width=100,
            height=28,
            command=self._on_test_connection,
        )
        self._test_btn.pack(side="left", padx=(0, 8))

        self._status_label = ctk.CTkLabel(
            test_frame, text="", anchor="w", font=ctk.CTkFont(size=11)
        )
        self._status_label.pack(side="left")

    def _on_test_connection(self) -> None:
        """接続テストを実行する。"""
        self._test_btn.configure(state="disabled")
        self._status_label.configure(text="テスト中...", text_color="gray")

        # ワーカースレッドで実行
        thread = threading.Thread(target=self._run_test, daemon=True)
        thread.start()

    def _run_test(self) -> None:
        """接続テストの実行（ワーカースレッド）。"""
        success = False
        error_msg = ""
        try:
            if self._app and hasattr(self._app, "llm_service") and self._app.llm_service:
                provider = self._app.llm_service.get_provider(self._config.id)
                valid = provider.validate_config()
                if valid:
                    success = True
                else:
                    error_msg = "設定が無効です"
            else:
                error_msg = "LLMサービスが初期化されていません"
        except KeyError:
            error_msg = "プロバイダが登録されていません"
        except Exception as e:
            error_msg = str(e)

        # UIスレッドで結果を反映
        self.after(0, self._show_test_result, success, error_msg)

    def _show_test_result(self, success: bool, error_msg: str) -> None:
        """テスト結果をUIに反映する。"""
        self._test_btn.configure(state="normal")
        if success:
            self._status_label.configure(text="接続OK", text_color="green")
        else:
            self._status_label.configure(
                text=f"接続失敗: {error_msg}", text_color="red"
            )


class SettingsView(ctk.CTkFrame):
    """LLMプロバイダ設定表示画面。

    llm_providers.jsonの内容を一覧表示し、
    各プロバイダの接続テストを実行できる。
    実際の設定編集はJSONファイルの手動編集で行う。
    """

    def __init__(self, master, app, **kwargs):
        super().__init__(master, **kwargs)
        self._app = app

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # --- ヘッダー ---
        ctk.CTkLabel(
            self,
            text="LLM設定",
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(16, 4))

        # --- 説明テキスト ---
        info_frame = ctk.CTkFrame(self, corner_radius=8, fg_color=("gray85", "gray20"))
        info_frame.grid(row=1, column=0, sticky="ew", padx=16, pady=(4, 8))
        info_frame.grid_columnconfigure(0, weight=1)

        # llm_providers.jsonのパス
        json_path = self._get_providers_json_path()
        env_path = self._get_env_path()

        info_text = (
            "LLMプロバイダの設定は以下のファイルで管理されています。\n"
            "設定を変更するにはファイルを直接編集してアプリを再起動してください。\n\n"
            f"モデル設定: {json_path}\n"
            f"APIキー設定: {env_path}"
        )

        ctk.CTkLabel(
            info_frame,
            text=info_text,
            anchor="w",
            justify="left",
            wraplength=700,
            font=ctk.CTkFont(size=12),
        ).grid(row=0, column=0, sticky="w", padx=12, pady=10)

        # --- プロバイダ一覧（スクロール可能） ---
        self._scroll = ctk.CTkScrollableFrame(self)
        self._scroll.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
        self._scroll.grid_columnconfigure(0, weight=1)

        # 初期読み込み
        self._load_providers()

    def _load_providers(self) -> None:
        """プロバイダ一覧を読み込んで表示する。"""
        for child in self._scroll.winfo_children():
            child.destroy()

        providers: list[LLMProviderConfig] = []
        try:
            if self._app and hasattr(self._app, "llm_service") and self._app.llm_service:
                providers = self._app.llm_service.list_configs()
        except Exception:
            pass

        if not providers:
            ctk.CTkLabel(
                self._scroll,
                text="LLMプロバイダが設定されていません。\nconfig/llm_providers.json にプロバイダを追加してください。",
                text_color="gray",
                wraplength=400,
            ).grid(row=0, column=0, padx=12, pady=20)
            return

        for idx, config in enumerate(providers):
            card = _ProviderCard(self._scroll, config=config, app=self._app)
            card.grid(row=idx, column=0, sticky="ew", padx=4, pady=4)

    def _get_providers_json_path(self) -> str:
        """llm_providers.jsonのパスを取得する。"""
        try:
            from src.utils.config_loader import PROJECT_ROOT
            return str(PROJECT_ROOT / "config" / "llm_providers.json")
        except Exception:
            return "config/llm_providers.json"

    def _get_env_path(self) -> str:
        """.envファイルのパスを取得する。"""
        try:
            from src.utils.config_loader import PROJECT_ROOT
            return str(PROJECT_ROOT / ".env")
        except Exception:
            return ".env"

    def on_show(self) -> None:
        """ビュー表示時にプロバイダ一覧を再読み込みする。"""
        self._load_providers()
