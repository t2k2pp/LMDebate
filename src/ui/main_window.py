"""メインウィンドウ - サイドバーナビゲーション付き"""

from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter as ctk

if TYPE_CHECKING:
    pass


class MainWindow(ctk.CTk):
    """アプリケーションのメインウィンドウ。

    左サイドバーにナビゲーションボタンを配置し、
    右コンテンツエリアでビューを切り替える。
    """

    def __init__(self, app) -> None:
        super().__init__()

        self._app = app

        # ウィンドウ設定
        self.title("LMDebate - LLMディベートアプリ")
        self.geometry("1200x800")
        self.minsize(900, 600)

        # テーマ設定
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        # レイアウト: 左サイドバー + 右コンテンツ
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- サイドバー ---
        self._sidebar = ctk.CTkFrame(self, width=200, corner_radius=0)
        self._sidebar.grid(row=0, column=0, sticky="nsew")
        self._sidebar.grid_rowconfigure(10, weight=1)  # スペーサー

        # アプリロゴ/タイトル
        self._logo_label = ctk.CTkLabel(
            self._sidebar,
            text="LMDebate",
            font=ctk.CTkFont(size=20, weight="bold"),
        )
        self._logo_label.grid(row=0, column=0, padx=20, pady=(20, 10))

        self._subtitle_label = ctk.CTkLabel(
            self._sidebar,
            text="LLMディベートアプリ",
            font=ctk.CTkFont(size=12),
            text_color="gray",
        )
        self._subtitle_label.grid(row=1, column=0, padx=20, pady=(0, 20))

        # ナビゲーションボタン
        self._nav_buttons: dict[str, ctk.CTkButton] = {}

        nav_items = [
            ("setup", "新規ディベート", 2),
            ("history", "履歴", 3),
            ("preset", "プリセット管理", 4),
            ("settings", "LLM設定", 5),
        ]

        for view_name, label, row in nav_items:
            btn = ctk.CTkButton(
                self._sidebar,
                text=label,
                command=lambda vn=view_name: self.show_view(vn),
                height=40,
                corner_radius=6,
                fg_color="transparent",
                text_color=("gray10", "gray90"),
                hover_color=("gray70", "gray30"),
                anchor="w",
                font=ctk.CTkFont(size=14),
            )
            btn.grid(row=row, column=0, padx=10, pady=4, sticky="ew")
            self._nav_buttons[view_name] = btn

        # --- コンテンツエリア ---
        self._content_frame = ctk.CTkFrame(self, corner_radius=0, fg_color="transparent")
        self._content_frame.grid(row=0, column=1, sticky="nsew", padx=0, pady=0)
        self._content_frame.grid_columnconfigure(0, weight=1)
        self._content_frame.grid_rowconfigure(0, weight=1)

        # ビューインスタンス管理
        self._views: dict[str, ctk.CTkFrame] = {}
        self._current_view_name: str | None = None

        # 遅延インポートでビューを生成
        self._create_views()

        # 初期表示
        self.show_view("setup")

    def _create_views(self) -> None:
        """各ビューインスタンスを生成する。"""
        from src.ui.setup_view import SetupView
        from src.ui.debate_view import DebateView
        from src.ui.history_view import HistoryView
        from src.ui.preset_view import PresetView
        from src.ui.settings_view import SettingsView

        view_classes = {
            "setup": SetupView,
            "debate": DebateView,
            "history": HistoryView,
            "preset": PresetView,
            "settings": SettingsView,
        }

        for name, cls in view_classes.items():
            try:
                view = cls(self._content_frame, self._app)
                view.grid(row=0, column=0, sticky="nsew")
                self._views[name] = view
            except Exception as e:
                # サービス未初期化等でも起動できるようフォールバック
                fallback = ctk.CTkFrame(self._content_frame)
                error_label = ctk.CTkLabel(
                    fallback,
                    text=f"ビュー '{name}' の初期化に失敗しました:\n{e}",
                    font=ctk.CTkFont(size=14),
                    text_color="red",
                )
                error_label.pack(expand=True)
                fallback.grid(row=0, column=0, sticky="nsew")
                self._views[name] = fallback

    def show_view(self, view_name: str) -> None:
        """指定されたビューをコンテンツエリアに表示する。"""
        if view_name not in self._views:
            return

        # 現在のビューを非表示
        for v in self._views.values():
            v.grid_remove()

        # 指定ビューを表示
        self._views[view_name].grid()
        self._current_view_name = view_name

        # ビュー固有のリフレッシュ処理
        view = self._views[view_name]
        if hasattr(view, "on_show"):
            view.on_show()

        # ナビボタンのハイライト更新
        for name, btn in self._nav_buttons.items():
            if name == view_name:
                btn.configure(fg_color=("gray75", "gray25"))
            else:
                btn.configure(fg_color="transparent")

    @property
    def app(self):
        return self._app
