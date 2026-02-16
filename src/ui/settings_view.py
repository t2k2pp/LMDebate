"""LLM設定画面 - プロバイダのCRUD管理"""

from __future__ import annotations

import asyncio
import logging
import re
import threading
from typing import TYPE_CHECKING

import customtkinter as ctk

from src.models.settings import LLMProviderConfig

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# プロバイダタイプの日本語ラベル
_TYPE_LABELS: dict[str, str] = {
    "azure_openai": "Azure OpenAI",
    "anthropic": "Anthropic",
    "vertex_ai": "Google Vertex AI",
    "ollama": "Ollama (ローカル)",
    "lmstudio": "LM Studio (ローカル)",
    "llamacpp": "Llama.cpp (ローカル)",
}

# タイプごとの追加フィールド定義 (フィールド名, ラベル, プレースホルダー)
_TYPE_FIELDS: dict[str, list[tuple[str, str, str]]] = {
    "azure_openai": [
        ("deployment_name", "デプロイメント名", "例: gpt-4o"),
        ("api_version", "APIバージョン", "例: 2024-08-01-preview"),
    ],
    "anthropic": [
        ("model", "モデル名", "例: claude-sonnet-4-20250514"),
    ],
    "vertex_ai": [
        ("model", "モデル名", "例: gemini-2.0-flash"),
    ],
    "ollama": [
        ("base_url", "ベースURL", "例: http://localhost:11434"),
        ("model", "モデル名", "例: llama3"),
    ],
    "lmstudio": [
        ("base_url", "ベースURL", "例: http://localhost:1234/v1"),
        ("model", "モデル名", "例: local-model"),
    ],
    "llamacpp": [
        ("base_url", "ベースURL", "例: http://localhost:8080"),
        ("model", "モデル名", "例: default"),
    ],
}

# 全タイプの選択肢
_TYPE_CHOICES: list[str] = list(_TYPE_LABELS.keys())

# モデル取得に対応するローカルプロバイダタイプ
_MODEL_FETCH_TYPES: set[str] = {"ollama", "lmstudio", "llamacpp"}


class _ProviderListItem(ctk.CTkFrame):
    """プロバイダ一覧の個別アイテム。"""

    def __init__(self, master, config: LLMProviderConfig, on_edit, on_delete,
                 init_error: str | None = None, **kwargs):
        super().__init__(master, corner_radius=6, **kwargs)
        self._config = config
        self.grid_columnconfigure(1, weight=1)

        # 名前
        ctk.CTkLabel(
            self,
            text=config.name,
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=8, pady=(6, 0))

        # タイプ
        type_label = _TYPE_LABELS.get(config.type, config.type)
        ctk.CTkLabel(
            self,
            text=f"[{type_label}]",
            anchor="w",
            text_color="gray",
            font=ctk.CTkFont(size=11),
        ).grid(row=0, column=1, sticky="w", padx=4, pady=(6, 0))

        # ボタン
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=0, column=2, rowspan=2, sticky="e", padx=8, pady=4)

        ctk.CTkButton(
            btn_frame, text="編集", width=60, height=28,
            command=lambda: on_edit(config),
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            btn_frame, text="削除", width=60, height=28,
            fg_color="red", hover_color="darkred",
            command=lambda: on_delete(config),
        ).pack(side="left", padx=2)

        # モデル/URL情報（2行目）
        info_parts: list[str] = []
        if config.model:
            info_parts.append(f"モデル: {config.model}")
        elif config.deployment_name:
            info_parts.append(f"デプロイ: {config.deployment_name}")
        if config.base_url:
            info_parts.append(f"URL: {config.base_url}")
        info_text = "  |  ".join(info_parts) if info_parts else ""

        if info_text:
            ctk.CTkLabel(
                self, text=info_text, anchor="w", text_color="gray",
                font=ctk.CTkFont(size=11), wraplength=300,
            ).grid(row=1, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 2))

        # 初期化エラー表示
        if init_error:
            ctk.CTkLabel(
                self, text=f"初期化エラー: {init_error}", anchor="w",
                text_color="orange", font=ctk.CTkFont(size=11), wraplength=300,
            ).grid(row=2, column=0, columnspan=3, sticky="w", padx=8, pady=(0, 4))


class SettingsView(ctk.CTkFrame):
    """LLMプロバイダ設定画面。

    左: プロバイダ一覧（追加・編集・削除）
    右: 編集フォーム（タイプ別動的フィールド）
    """

    def __init__(self, master, app, **kwargs):
        super().__init__(master, **kwargs)
        self._app = app
        self._editing_config: LLMProviderConfig | None = None  # 編集中の設定（新規はNone）
        self._dynamic_field_widgets: dict[str, ctk.CTkEntry | ctk.CTkComboBox] = {}
        self._dynamic_field_labels: dict[str, ctk.CTkLabel] = {}
        self._fetch_models_btn: ctk.CTkButton | None = None
        self._fetch_status_label: ctk.CTkLabel | None = None
        self._current_provider_type: str | None = None  # 現在のフォームのプロバイダタイプ

        self.grid_columnconfigure(0, minsize=380)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ======================
        # 左パネル: プロバイダ一覧
        # ======================
        left_frame = ctk.CTkFrame(self)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(4, 2), pady=4)
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(1, weight=1)

        # ヘッダー + 新規追加ボタン
        left_header = ctk.CTkFrame(left_frame, fg_color="transparent")
        left_header.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        left_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            left_header, text="LLMプロバイダ管理",
            font=ctk.CTkFont(size=16, weight="bold"), anchor="w",
        ).grid(row=0, column=0, sticky="w")

        self._new_btn = ctk.CTkButton(
            left_header, text="新規追加", width=100, command=self._on_new,
        )
        self._new_btn.grid(row=0, column=1, sticky="e")

        # 一覧（スクロール可能）
        self._list_scroll = ctk.CTkScrollableFrame(left_frame)
        self._list_scroll.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        self._list_scroll.grid_columnconfigure(0, weight=1)

        # --- SearXNG URL設定 ---
        searxng_frame = ctk.CTkFrame(left_frame)
        searxng_frame.grid(row=2, column=0, sticky="ew", padx=4, pady=(4, 8))
        searxng_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            searxng_frame, text="ウェブ検索 (SearXNG)",
            font=ctk.CTkFont(size=13, weight="bold"), anchor="w",
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(8, 4))

        ctk.CTkLabel(
            searxng_frame, text="ベースURL:", anchor="w",
        ).grid(row=1, column=0, sticky="w", padx=8, pady=(0, 2))

        self._searxng_url_entry = ctk.CTkEntry(
            searxng_frame, placeholder_text="例: http://localhost:8888",
        )
        self._searxng_url_entry.grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 4))

        searxng_btn_frame = ctk.CTkFrame(searxng_frame, fg_color="transparent")
        searxng_btn_frame.grid(row=2, column=1, sticky="e", padx=(4, 8), pady=(0, 4))

        self._searxng_test_btn = ctk.CTkButton(
            searxng_btn_frame, text="接続確認", width=80,
            fg_color="gray40", hover_color="gray30",
            command=self._on_test_searxng,
        )
        self._searxng_test_btn.pack(side="left", padx=(0, 4))

        self._searxng_save_btn = ctk.CTkButton(
            searxng_btn_frame, text="保存", width=80, command=self._on_save_searxng,
        )
        self._searxng_save_btn.pack(side="left")

        self._searxng_status_label = ctk.CTkLabel(
            searxng_frame, text="", anchor="w",
            font=ctk.CTkFont(size=11), text_color="gray",
        )
        self._searxng_status_label.grid(row=3, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 8))

        # ======================
        # 右パネル: 編集フォーム
        # ======================
        right_frame = ctk.CTkFrame(self)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(2, 4), pady=4)
        right_frame.grid_columnconfigure(0, weight=1)
        self._right_frame = right_frame

        ctk.CTkLabel(
            right_frame, text="プロバイダ設定",
            font=ctk.CTkFont(size=16, weight="bold"), anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 8))

        # -- プロバイダ名 --
        ctk.CTkLabel(right_frame, text="プロバイダ名:", anchor="w").grid(
            row=1, column=0, sticky="w", padx=12, pady=(4, 0)
        )
        self._name_entry = ctk.CTkEntry(
            right_frame, placeholder_text="表示名を入力（例: Ollama Qwen）"
        )
        self._name_entry.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 8))

        # -- プロバイダID（読み取り専用表示） --
        self._id_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        self._id_frame.grid(row=3, column=0, sticky="ew", padx=12, pady=(0, 8))

        ctk.CTkLabel(self._id_frame, text="ID:", anchor="w").pack(
            side="left", padx=(0, 4)
        )
        self._id_label = ctk.CTkLabel(
            self._id_frame, text="（自動生成）", anchor="w", text_color="gray",
        )
        self._id_label.pack(side="left")

        # -- タイプ選択 --
        ctk.CTkLabel(right_frame, text="プロバイダタイプ:", anchor="w").grid(
            row=4, column=0, sticky="w", padx=12, pady=(4, 0)
        )
        self._type_combo = ctk.CTkComboBox(
            right_frame,
            values=[_TYPE_LABELS.get(t, t) for t in _TYPE_CHOICES],
            command=self._on_type_selected,
            state="readonly",
        )
        self._type_combo.grid(row=5, column=0, sticky="ew", padx=12, pady=(0, 8))
        self._type_combo.set("")

        # -- 動的フィールドエリア --
        self._dynamic_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        self._dynamic_frame.grid(row=6, column=0, sticky="ew", padx=12, pady=(0, 4))
        self._dynamic_frame.grid_columnconfigure(0, weight=1)

        # -- 共通設定 --
        common_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        common_frame.grid(row=7, column=0, sticky="ew", padx=12, pady=(4, 0))
        common_frame.grid_columnconfigure(1, weight=1)
        common_frame.grid_columnconfigure(3, weight=1)

        ctk.CTkLabel(common_frame, text="最大トークン:").grid(
            row=0, column=0, sticky="w", padx=(0, 4), pady=4
        )
        self._max_tokens_entry = ctk.CTkEntry(common_frame, width=100)
        self._max_tokens_entry.grid(row=0, column=1, sticky="w", pady=4)
        self._max_tokens_entry.insert(0, "500")

        ctk.CTkLabel(common_frame, text="温度:").grid(
            row=0, column=2, sticky="w", padx=(16, 4), pady=4
        )
        self._temperature_entry = ctk.CTkEntry(common_frame, width=80)
        self._temperature_entry.grid(row=0, column=3, sticky="w", pady=4)
        self._temperature_entry.insert(0, "0.7")

        # -- 接続テスト --
        test_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        test_frame.grid(row=8, column=0, sticky="w", padx=12, pady=(8, 4))

        self._test_btn = ctk.CTkButton(
            test_frame, text="接続テスト", width=120, command=self._on_test_connection,
        )
        self._test_btn.pack(side="left", padx=(0, 8))

        self._test_status_label = ctk.CTkLabel(
            test_frame, text="", anchor="w", font=ctk.CTkFont(size=11),
        )
        self._test_status_label.pack(side="left")

        # -- 保存 / キャンセル ボタン --
        form_btn_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        form_btn_frame.grid(row=9, column=0, sticky="e", padx=12, pady=(8, 12))

        self._cancel_btn = ctk.CTkButton(
            form_btn_frame, text="キャンセル",
            fg_color="gray40", hover_color="gray30",
            command=self._on_cancel,
        )
        self._cancel_btn.pack(side="left", padx=4)

        self._save_btn = ctk.CTkButton(
            form_btn_frame, text="保存", command=self._on_save,
        )
        self._save_btn.pack(side="left", padx=4)

    # ==================================================================
    # 一覧の読み込み
    # ==================================================================

    def _load_providers(self) -> None:
        """プロバイダ一覧を読み込んで表示する。"""
        for child in self._list_scroll.winfo_children():
            child.destroy()

        configs: list[LLMProviderConfig] = []
        init_errors: dict[str, str] = {}
        try:
            if self._app and hasattr(self._app, "llm_service") and self._app.llm_service:
                configs = self._app.llm_service.list_configs()
                init_errors = self._app.llm_service.get_init_errors()
        except Exception:
            pass

        if not configs:
            ctk.CTkLabel(
                self._list_scroll,
                text="LLMプロバイダが設定されていません。\n「新規追加」ボタンからプロバイダを追加してください。",
                text_color="gray", wraplength=340,
            ).grid(row=0, column=0, padx=12, pady=20)
            return

        for idx, config in enumerate(configs):
            item = _ProviderListItem(
                self._list_scroll,
                config=config,
                on_edit=self._on_edit,
                on_delete=self._on_delete,
                init_error=init_errors.get(config.id),
            )
            item.grid(row=idx, column=0, sticky="ew", padx=4, pady=4)

    # ==================================================================
    # フォーム操作
    # ==================================================================

    def _clear_form(self) -> None:
        """編集フォームをクリアする。"""
        self._editing_config = None
        self._name_entry.delete(0, "end")
        self._id_label.configure(text="（自動生成）")
        self._type_combo.set("")
        self._max_tokens_entry.delete(0, "end")
        self._max_tokens_entry.insert(0, "500")
        self._temperature_entry.delete(0, "end")
        self._temperature_entry.insert(0, "0.7")
        self._test_status_label.configure(text="")
        self._clear_dynamic_fields()

    def _clear_dynamic_fields(self) -> None:
        """動的フィールドをクリアする。"""
        for child in self._dynamic_frame.winfo_children():
            child.destroy()
        self._dynamic_field_widgets.clear()
        self._dynamic_field_labels.clear()
        self._fetch_models_btn = None
        self._fetch_status_label = None
        self._current_provider_type = None

    def _build_dynamic_fields(self, provider_type: str) -> None:
        """タイプに応じた動的フィールドを構築する。

        ローカルプロバイダのモデルフィールドは ComboBox + 取得ボタンで構成する。
        """
        self._clear_dynamic_fields()
        self._current_provider_type = provider_type
        self._fetch_models_btn = None
        self._fetch_status_label = None

        is_local = provider_type in _MODEL_FETCH_TYPES
        fields = _TYPE_FIELDS.get(provider_type, [])
        grid_row = 0

        for field_name, label_text, placeholder in fields:
            lbl = ctk.CTkLabel(self._dynamic_frame, text=f"{label_text}:", anchor="w")
            lbl.grid(row=grid_row, column=0, sticky="w", pady=(4, 0))
            self._dynamic_field_labels[field_name] = lbl
            grid_row += 1

            if field_name == "model" and is_local:
                # ローカルプロバイダのモデルフィールド: ComboBox + 取得ボタン
                model_row = ctk.CTkFrame(self._dynamic_frame, fg_color="transparent")
                model_row.grid(row=grid_row, column=0, sticky="ew", pady=(0, 4))
                model_row.grid_columnconfigure(0, weight=1)

                combo = ctk.CTkComboBox(
                    model_row,
                    values=[],
                    state="normal",  # 手動入力も可能
                )
                combo.grid(row=0, column=0, sticky="ew", padx=(0, 4))
                combo.set("")
                self._dynamic_field_widgets[field_name] = combo

                self._fetch_models_btn = ctk.CTkButton(
                    model_row,
                    text="モデル取得",
                    width=100,
                    height=28,
                    command=self._on_fetch_models,
                )
                self._fetch_models_btn.grid(row=0, column=1, sticky="e")

                # 取得状態ラベル
                self._fetch_status_label = ctk.CTkLabel(
                    self._dynamic_frame,
                    text="",
                    anchor="w",
                    font=ctk.CTkFont(size=11),
                    text_color="gray",
                )
                self._fetch_status_label.grid(row=grid_row + 1, column=0, sticky="w", pady=(0, 2))
                grid_row += 2
            else:
                # 通常のテキスト入力フィールド
                entry = ctk.CTkEntry(self._dynamic_frame, placeholder_text=placeholder)
                entry.grid(row=grid_row, column=0, sticky="ew", pady=(0, 4))
                self._dynamic_field_widgets[field_name] = entry
                grid_row += 1

    def _fill_form(self, config: LLMProviderConfig) -> None:
        """設定データでフォームを埋める。"""
        self._clear_form()
        self._editing_config = config

        self._name_entry.insert(0, config.name)
        self._id_label.configure(text=config.id)

        # タイプを選択
        type_label = _TYPE_LABELS.get(config.type, config.type)
        self._type_combo.set(type_label)

        # 動的フィールドを構築して値を入力
        self._build_dynamic_fields(config.type)
        for field_name, widget in self._dynamic_field_widgets.items():
            value = getattr(config, field_name, None)
            if value:
                if isinstance(widget, ctk.CTkComboBox):
                    widget.set(str(value))
                else:
                    widget.insert(0, str(value))

        # 共通設定
        self._max_tokens_entry.delete(0, "end")
        self._max_tokens_entry.insert(0, str(config.default_max_tokens))
        self._temperature_entry.delete(0, "end")
        self._temperature_entry.insert(0, str(config.default_temperature))

    def _get_selected_type_key(self) -> str | None:
        """コンボボックスから選択されたタイプのキー文字列を取得する。"""
        selected_label = self._type_combo.get()
        if not selected_label:
            return None
        for key, label in _TYPE_LABELS.items():
            if label == selected_label:
                return key
        return None

    def _generate_id(self, type_key: str, name: str) -> str:
        """プロバイダIDを自動生成する。"""
        # 名前からスラッグを作成
        slug = re.sub(r"[^a-zA-Z0-9\u3040-\u9fff]+", "-", name.lower()).strip("-")
        if not slug:
            import uuid
            slug = uuid.uuid4().hex[:8]
        provider_id = f"{type_key}-{slug}"
        return provider_id

    # ==================================================================
    # イベントハンドラ
    # ==================================================================

    def _on_type_selected(self, choice: str) -> None:
        """タイプ変更時に動的フィールドを更新する。"""
        type_key = self._get_selected_type_key()
        if type_key:
            self._build_dynamic_fields(type_key)

    def _on_fetch_models(self) -> None:
        """モデル取得ボタン — ローカルサーバーからモデル一覧を取得する。"""
        type_key = self._current_provider_type
        if not type_key or type_key not in _MODEL_FETCH_TYPES:
            return

        # base_url フィールドから値を取得
        base_url_widget = self._dynamic_field_widgets.get("base_url")
        if base_url_widget is None:
            self._show_error("ベースURLフィールドが見つかりません。")
            return

        base_url = base_url_widget.get().strip()
        if not base_url:
            self._show_error("先にベースURLを入力してください。")
            return

        # UI更新: ボタン無効化 + ステータス表示
        if self._fetch_models_btn:
            self._fetch_models_btn.configure(state="disabled")
        if self._fetch_status_label:
            self._fetch_status_label.configure(text="取得中...", text_color="gray")

        # ワーカースレッドで取得
        thread = threading.Thread(
            target=self._run_fetch_models,
            args=(type_key, base_url),
            daemon=True,
        )
        thread.start()

    def _run_fetch_models(self, type_key: str, base_url: str) -> None:
        """モデル一覧取得の実行（ワーカースレッド）。"""
        models: list[str] = []
        error_msg = ""
        try:
            if self._app and hasattr(self._app, "llm_service") and self._app.llm_service:
                models = self._app.llm_service.fetch_models(type_key, base_url)
            else:
                error_msg = "LLMサービスが初期化されていません"
        except Exception as e:
            error_msg = str(e)

        self.after(0, self._show_fetch_result, models, error_msg)

    def _show_fetch_result(self, models: list[str], error_msg: str) -> None:
        """モデル取得結果をUIに反映する。"""
        # ボタンを再有効化
        if self._fetch_models_btn:
            self._fetch_models_btn.configure(state="normal")

        model_widget = self._dynamic_field_widgets.get("model")
        if not isinstance(model_widget, ctk.CTkComboBox):
            return

        if error_msg:
            if self._fetch_status_label:
                self._fetch_status_label.configure(
                    text=f"取得失敗: {error_msg}", text_color="red"
                )
            return

        if not models:
            if self._fetch_status_label:
                self._fetch_status_label.configure(
                    text="モデルが見つかりませんでした", text_color="orange"
                )
            return

        # ComboBox にモデル一覧を設定
        model_widget.configure(values=models)
        # 現在値が空なら最初のモデルを選択
        current = model_widget.get().strip()
        if not current:
            model_widget.set(models[0])

        if self._fetch_status_label:
            self._fetch_status_label.configure(
                text=f"{len(models)}個のモデルを取得しました", text_color="green"
            )

    def _on_new(self) -> None:
        """新規追加ボタン。"""
        self._clear_form()

    def _on_edit(self, config: LLMProviderConfig) -> None:
        """編集ボタン。"""
        self._fill_form(config)

    def _on_delete(self, config: LLMProviderConfig) -> None:
        """削除ボタン（確認ダイアログ付き）。"""
        self._show_confirm(
            f"プロバイダ「{config.name}」を削除しますか？",
            lambda: self._do_delete(config),
        )

    def _do_delete(self, config: LLMProviderConfig) -> None:
        """実際の削除処理。"""
        try:
            if self._app and hasattr(self._app, "llm_service") and self._app.llm_service:
                self._app.llm_service.delete_provider(config.id)

            if self._editing_config and self._editing_config.id == config.id:
                self._clear_form()

            self._load_providers()
        except Exception as e:
            self._show_error(f"削除エラー: {e}")

    def _on_cancel(self) -> None:
        """キャンセルボタン。"""
        self._clear_form()

    def _on_save(self) -> None:
        """保存ボタン。"""
        name = self._name_entry.get().strip()
        if not name:
            self._show_error("プロバイダ名を入力してください。")
            return

        type_key = self._get_selected_type_key()
        if not type_key:
            self._show_error("プロバイダタイプを選択してください。")
            return

        # 最大トークン
        try:
            max_tokens = int(self._max_tokens_entry.get().strip())
            if max_tokens <= 0:
                self._show_error("最大トークンは正の整数で入力してください。")
                return
            if max_tokens > 100000:
                self._show_error("最大トークンが大きすぎます（上限: 100000）。")
                return
        except ValueError:
            self._show_error("最大トークンは整数で入力してください。")
            return

        # 温度
        try:
            temperature = float(self._temperature_entry.get().strip())
            if temperature < 0.0 or temperature > 2.0:
                self._show_error("温度は0.0〜2.0の範囲で入力してください。")
                return
        except ValueError:
            self._show_error("温度は数値で入力してください。")
            return

        # 動的フィールドの値を収集
        extra_fields: dict[str, str | None] = {}
        for field_name, widget in self._dynamic_field_widgets.items():
            val = widget.get().strip()
            extra_fields[field_name] = val if val else None

        # タイプ別の必須フィールドチェック
        required_check = self._validate_type_fields(type_key, extra_fields)
        if required_check:
            self._show_error(required_check)
            return

        try:
            if self._app and hasattr(self._app, "llm_service") and self._app.llm_service:
                if self._editing_config:
                    # 更新
                    config = LLMProviderConfig(
                        id=self._editing_config.id,
                        name=name,
                        type=type_key,
                        default_max_tokens=max_tokens,
                        default_temperature=temperature,
                        deployment_name=extra_fields.get("deployment_name"),
                        api_version=extra_fields.get("api_version"),
                        model=extra_fields.get("model"),
                        base_url=extra_fields.get("base_url"),
                    )
                    self._app.llm_service.update_provider(config)
                else:
                    # 新規作成
                    provider_id = self._generate_id(type_key, name)
                    config = LLMProviderConfig(
                        id=provider_id,
                        name=name,
                        type=type_key,
                        default_max_tokens=max_tokens,
                        default_temperature=temperature,
                        deployment_name=extra_fields.get("deployment_name"),
                        api_version=extra_fields.get("api_version"),
                        model=extra_fields.get("model"),
                        base_url=extra_fields.get("base_url"),
                    )
                    self._app.llm_service.add_provider(config)

                self._clear_form()
                self._load_providers()
        except Exception as e:
            self._show_error(f"保存エラー: {e}")

    def _validate_type_fields(
        self, type_key: str, fields: dict[str, str | None]
    ) -> str | None:
        """タイプ別の必須フィールドを検証する。エラーメッセージを返す（問題なければNone）。"""
        if type_key == "azure_openai":
            if not fields.get("deployment_name"):
                return "Azure OpenAIにはデプロイメント名が必要です。"
        elif type_key in ("anthropic", "vertex_ai", "ollama"):
            if not fields.get("model"):
                return f"{_TYPE_LABELS.get(type_key, type_key)}にはモデル名が必要です。"
        return None

    # ==================================================================
    # 接続テスト
    # ==================================================================

    def _on_test_connection(self) -> None:
        """接続テストを実行する。"""
        if not self._editing_config:
            self._test_status_label.configure(
                text="先に既存プロバイダを編集してください", text_color="gray"
            )
            return

        self._test_btn.configure(state="disabled")
        self._test_status_label.configure(text="テスト中...", text_color="gray")

        config_id = self._editing_config.id
        thread = threading.Thread(
            target=self._run_test, args=(config_id,), daemon=True
        )
        thread.start()

    def _run_test(self, config_id: str) -> None:
        """接続テストの実行（ワーカースレッド）。"""
        success = False
        error_msg = ""
        try:
            if self._app and hasattr(self._app, "llm_service") and self._app.llm_service:
                provider = self._app.llm_service.get_provider(config_id)
                valid = provider.validate_config()
                if valid:
                    success = True
                else:
                    error_msg = "設定が無効です"
            else:
                error_msg = "LLMサービスが初期化されていません"
        except KeyError:
            error_msg = "プロバイダが初期化されていません（SDKが未インストールの可能性）"
        except Exception as e:
            error_msg = str(e)

        self.after(0, self._show_test_result, success, error_msg)

    def _show_test_result(self, success: bool, error_msg: str) -> None:
        """テスト結果をUIに反映する。"""
        self._test_btn.configure(state="normal")
        if success:
            self._test_status_label.configure(text="接続OK", text_color="green")
        else:
            self._test_status_label.configure(
                text=f"接続失敗: {error_msg}", text_color="red"
            )

    # ==================================================================
    # ダイアログ
    # ==================================================================

    def _show_error(self, msg: str) -> None:
        """エラーダイアログを表示する。"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("エラー")
        dialog.geometry("450x150")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        ctk.CTkLabel(dialog, text=msg, wraplength=400, text_color="red").pack(
            expand=True, padx=20, pady=20
        )
        ctk.CTkButton(dialog, text="OK", command=dialog.destroy).pack(pady=(0, 16))

    def _show_confirm(self, msg: str, on_confirm) -> None:
        """確認ダイアログを表示する。"""
        dialog = ctk.CTkToplevel(self)
        dialog.title("確認")
        dialog.geometry("450x170")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()

        ctk.CTkLabel(dialog, text=msg, wraplength=400).pack(
            expand=True, padx=20, pady=20
        )

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack(pady=(0, 16))

        ctk.CTkButton(
            btn_frame, text="キャンセル", fg_color="gray40", command=dialog.destroy,
        ).pack(side="left", padx=8)

        def confirm():
            dialog.destroy()
            on_confirm()

        ctk.CTkButton(
            btn_frame, text="削除", fg_color="red", hover_color="darkred",
            command=confirm,
        ).pack(side="left", padx=8)

    # ==================================================================
    # ライフサイクル
    # ==================================================================

    def _on_test_searxng(self) -> None:
        """SearXNG 接続確認ボタン。"""
        url = self._searxng_url_entry.get().strip()
        if not url:
            self._searxng_status_label.configure(
                text="ベースURLを入力してください", text_color="orange"
            )
            return

        self._searxng_test_btn.configure(state="disabled")
        self._searxng_status_label.configure(text="接続確認中...", text_color="gray")

        # ワーカースレッドで実行
        thread = threading.Thread(
            target=self._run_test_searxng, args=(url,), daemon=True
        )
        thread.start()

    def _run_test_searxng(self, url: str) -> None:
        """SearXNG 接続テストの実行（ワーカースレッド）。"""
        success = False
        error_msg = ""
        try:
            import httpx
            with httpx.Client(timeout=10.0) as client:
                response = client.get(
                    f"{url.rstrip('/')}/search",
                    params={"q": "test", "format": "json"},
                )
                response.raise_for_status()
                data = response.json()
                # レスポンスに results キーがあれば成功
                if "results" in data:
                    success = True
                else:
                    error_msg = "予期しないレスポンス形式"
        except ImportError:
            error_msg = "httpx パッケージが未インストール"
        except Exception as e:
            error_msg = str(e)

        self.after(0, self._show_test_searxng_result, success, error_msg)

    def _show_test_searxng_result(self, success: bool, error_msg: str) -> None:
        """SearXNG 接続テスト結果をUIに反映する。"""
        self._searxng_test_btn.configure(state="normal")
        if success:
            self._searxng_status_label.configure(text="接続OK", text_color="green")
        else:
            self._searxng_status_label.configure(
                text=f"接続失敗: {error_msg}", text_color="red"
            )

    def _on_save_searxng(self) -> None:
        """SearXNG URL保存ボタン。"""
        url = self._searxng_url_entry.get().strip()
        try:
            if self._app and hasattr(self._app, "settings"):
                self._app.settings.searxng_base_url = url
                # SearchServiceも更新
                if hasattr(self._app, "search_service") and self._app.search_service:
                    self._app.search_service.update_base_url(url)
                # JSONに保存
                from src.utils.config_loader import save_app_settings
                save_app_settings(self._app.settings)
                self._searxng_status_label.configure(text="保存しました", text_color="green")
        except Exception as e:
            self._searxng_status_label.configure(
                text=f"保存失敗: {e}", text_color="red"
            )

    def on_show(self) -> None:
        """ビュー表示時にプロバイダ一覧を再読み込みする。"""
        self._load_providers()
        # SearXNG URL読み込み
        try:
            if self._app and hasattr(self._app, "settings"):
                current_url = self._app.settings.searxng_base_url or ""
                self._searxng_url_entry.delete(0, "end")
                self._searxng_url_entry.insert(0, current_url)
                self._searxng_status_label.configure(text="")
        except Exception:
            pass
