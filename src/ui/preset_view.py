"""ロールプリセット管理画面"""

from __future__ import annotations

from typing import TYPE_CHECKING

import customtkinter as ctk

from src.models.role_preset import RolePreset, TargetRole

if TYPE_CHECKING:
    pass


class _PresetListItem(ctk.CTkFrame):
    """プリセット一覧の個別アイテム。"""

    _TARGET_ROLE_LABELS = {
        TargetRole.PROPOSER: "提案者向け",
        TargetRole.JUDGE: "判定者向け",
        TargetRole.ANY: "どちらでも",
    }

    def __init__(self, master, preset: RolePreset, on_edit, on_delete, **kwargs):
        super().__init__(master, corner_radius=6, **kwargs)
        self._preset = preset
        self.grid_columnconfigure(1, weight=1)

        # 名前
        ctk.CTkLabel(
            self,
            text=preset.name,
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=8, pady=(6, 0))

        # ターゲットロール
        role_label = self._TARGET_ROLE_LABELS.get(preset.target_role, preset.target_role.value)
        ctk.CTkLabel(
            self,
            text=f"[{role_label}]",
            anchor="w",
            text_color="gray",
            font=ctk.CTkFont(size=11),
        ).grid(row=0, column=1, sticky="w", padx=4, pady=(6, 0))

        # ボタン
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.grid(row=0, column=2, rowspan=2, sticky="e", padx=8, pady=4)

        ctk.CTkButton(
            btn_frame,
            text="編集",
            width=60,
            height=28,
            command=lambda: on_edit(preset),
        ).pack(side="left", padx=2)

        ctk.CTkButton(
            btn_frame,
            text="削除",
            width=60,
            height=28,
            fg_color="red",
            hover_color="darkred",
            command=lambda: on_delete(preset),
        ).pack(side="left", padx=2)

        # 説明（2行目）
        if preset.role_description:
            ctk.CTkLabel(
                self,
                text=preset.role_description,
                anchor="w",
                text_color="gray",
                font=ctk.CTkFont(size=11),
                wraplength=300,
            ).grid(row=1, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 6))


class PresetView(ctk.CTkFrame):
    """ロールプリセット管理画面。

    左: プリセット一覧
    右: 編集フォーム
    """

    def __init__(self, master, app, **kwargs):
        super().__init__(master, **kwargs)
        self._app = app
        self._presets: list[RolePreset] = []
        self._editing_preset: RolePreset | None = None  # 編集中のプリセット（新規はNone）

        self.grid_columnconfigure(0, minsize=350)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- 左: プリセット一覧 ---
        left_frame = ctk.CTkFrame(self)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(4, 2), pady=4)
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(1, weight=1)

        # ヘッダー + 新規作成ボタン
        left_header = ctk.CTkFrame(left_frame, fg_color="transparent")
        left_header.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        left_header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            left_header,
            text="ロールプリセット管理",
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        self._new_btn = ctk.CTkButton(
            left_header,
            text="新規作成",
            width=100,
            command=self._on_new,
        )
        self._new_btn.grid(row=0, column=1, sticky="e")

        # 一覧（スクロール可能）
        self._list_scroll = ctk.CTkScrollableFrame(left_frame)
        self._list_scroll.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        self._list_scroll.grid_columnconfigure(0, weight=1)

        # --- 右: 編集フォーム ---
        right_frame = ctk.CTkFrame(self)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(2, 4), pady=4)
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(6, weight=1)

        ctk.CTkLabel(
            right_frame,
            text="プリセット編集",
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 8))

        # プリセット名
        ctk.CTkLabel(right_frame, text="プリセット名:", anchor="w").grid(
            row=1, column=0, sticky="w", padx=12, pady=(4, 0)
        )
        self._name_entry = ctk.CTkEntry(
            right_frame, placeholder_text="プリセット名を入力"
        )
        self._name_entry.grid(row=2, column=0, sticky="ew", padx=12, pady=(0, 8))

        # 対象ロール
        role_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        role_frame.grid(row=3, column=0, sticky="w", padx=12, pady=(0, 8))
        ctk.CTkLabel(role_frame, text="対象ロール:").pack(side="left", padx=(0, 8))

        self._target_role_var = ctk.StringVar(value="any")
        ctk.CTkRadioButton(
            role_frame, text="提案者向け", variable=self._target_role_var, value="proposer"
        ).pack(side="left", padx=(0, 8))
        ctk.CTkRadioButton(
            role_frame, text="判定者向け", variable=self._target_role_var, value="judge"
        ).pack(side="left", padx=(0, 8))
        ctk.CTkRadioButton(
            role_frame, text="どちらでも", variable=self._target_role_var, value="any"
        ).pack(side="left")

        # 役割の説明
        ctk.CTkLabel(right_frame, text="役割の説明:", anchor="w").grid(
            row=4, column=0, sticky="w", padx=12, pady=(4, 0)
        )
        self._role_desc_text = ctk.CTkTextbox(right_frame, height=60)
        self._role_desc_text.grid(row=5, column=0, sticky="ew", padx=12, pady=(0, 8))

        # 性格
        ctk.CTkLabel(right_frame, text="性格:", anchor="w").grid(
            row=6, column=0, sticky="w", padx=12, pady=(4, 0)
        )
        self._personality_text = ctk.CTkTextbox(right_frame, height=60)
        self._personality_text.grid(row=7, column=0, sticky="ew", padx=12, pady=(0, 8))

        # 行動指針
        ctk.CTkLabel(right_frame, text="行動指針:", anchor="w").grid(
            row=8, column=0, sticky="w", padx=12, pady=(4, 0)
        )
        self._guidelines_text = ctk.CTkTextbox(right_frame, height=80)
        self._guidelines_text.grid(row=9, column=0, sticky="ew", padx=12, pady=(0, 8))

        # ボタン
        form_btn_frame = ctk.CTkFrame(right_frame, fg_color="transparent")
        form_btn_frame.grid(row=10, column=0, sticky="e", padx=12, pady=(4, 12))

        self._cancel_edit_btn = ctk.CTkButton(
            form_btn_frame,
            text="キャンセル",
            fg_color="gray40",
            hover_color="gray30",
            command=self._on_cancel_edit,
        )
        self._cancel_edit_btn.pack(side="left", padx=4)

        self._save_btn = ctk.CTkButton(
            form_btn_frame,
            text="保存",
            command=self._on_save,
        )
        self._save_btn.pack(side="left", padx=4)

    # ------------------------------------------------------------------
    # 一覧の読み込み
    # ------------------------------------------------------------------

    def _load_presets(self) -> None:
        """サービスからプリセット一覧を読み込む。"""
        self._presets = []
        try:
            if self._app and hasattr(self._app, "preset_service") and self._app.preset_service:
                self._presets = self._app.preset_service.list_presets()
        except Exception:
            pass
        self._refresh_list()

    def _refresh_list(self) -> None:
        """一覧リストを再描画する。"""
        for child in self._list_scroll.winfo_children():
            child.destroy()

        if not self._presets:
            ctk.CTkLabel(
                self._list_scroll, text="プリセットがありません", text_color="gray"
            ).grid(row=0, column=0, padx=12, pady=20)
            return

        for idx, preset in enumerate(self._presets):
            item = _PresetListItem(
                self._list_scroll,
                preset=preset,
                on_edit=self._on_edit,
                on_delete=self._on_delete,
            )
            item.grid(row=idx, column=0, sticky="ew", padx=4, pady=4)

    # ------------------------------------------------------------------
    # フォーム操作
    # ------------------------------------------------------------------

    def _clear_form(self) -> None:
        """編集フォームをクリアする。"""
        self._name_entry.delete(0, "end")
        self._target_role_var.set("any")
        self._role_desc_text.delete("1.0", "end")
        self._personality_text.delete("1.0", "end")
        self._guidelines_text.delete("1.0", "end")
        self._editing_preset = None

    def _fill_form(self, preset: RolePreset) -> None:
        """プリセットデータでフォームを埋める。"""
        self._clear_form()
        self._editing_preset = preset
        self._name_entry.insert(0, preset.name)
        self._target_role_var.set(preset.target_role.value)
        self._role_desc_text.insert("1.0", preset.role_description or "")
        self._personality_text.insert("1.0", preset.personality or "")
        self._guidelines_text.insert("1.0", preset.guidelines or "")

    # ------------------------------------------------------------------
    # イベントハンドラ
    # ------------------------------------------------------------------

    def _on_new(self) -> None:
        """新規作成ボタン。"""
        self._clear_form()

    def _on_edit(self, preset: RolePreset) -> None:
        """編集ボタン。"""
        self._fill_form(preset)

    def _on_delete(self, preset: RolePreset) -> None:
        """削除ボタン（確認ダイアログ付き）。"""
        self._show_confirm(
            f"プリセット「{preset.name}」を削除しますか？",
            lambda: self._do_delete(preset),
        )

    def _do_delete(self, preset: RolePreset) -> None:
        """実際の削除処理。"""
        try:
            if self._app and hasattr(self._app, "preset_service") and self._app.preset_service:
                self._app.preset_service.delete_preset(preset.id)

            if self._editing_preset and self._editing_preset.id == preset.id:
                self._clear_form()

            self._load_presets()
        except Exception as e:
            self._show_error(f"削除エラー: {e}")

    def _on_save(self) -> None:
        """保存ボタン。"""
        name = self._name_entry.get().strip()
        if not name:
            self._show_error("プリセット名を入力してください。")
            return

        target_role = TargetRole(self._target_role_var.get())
        role_description = self._role_desc_text.get("1.0", "end-1c").strip()
        personality = self._personality_text.get("1.0", "end-1c").strip()
        guidelines = self._guidelines_text.get("1.0", "end-1c").strip()

        try:
            if self._app and hasattr(self._app, "preset_service") and self._app.preset_service:
                if self._editing_preset:
                    # 更新
                    self._editing_preset.name = name
                    self._editing_preset.target_role = target_role
                    self._editing_preset.role_description = role_description
                    self._editing_preset.personality = personality
                    self._editing_preset.guidelines = guidelines
                    self._app.preset_service.update_preset(self._editing_preset)
                else:
                    # 新規作成
                    preset = RolePreset(
                        name=name,
                        role_description=role_description,
                        personality=personality,
                        guidelines=guidelines,
                        target_role=target_role,
                    )
                    self._app.preset_service.create_preset(preset)

                self._clear_form()
                self._load_presets()
        except Exception as e:
            self._show_error(f"保存エラー: {e}")

    def _on_cancel_edit(self) -> None:
        """キャンセルボタン。"""
        self._clear_form()

    # ------------------------------------------------------------------
    # ダイアログ
    # ------------------------------------------------------------------

    def _show_error(self, msg: str) -> None:
        from src.ui.dialogs import show_error

        show_error(self, msg)

    def _show_confirm(self, msg: str, on_confirm) -> None:
        from src.ui.dialogs import show_confirm

        show_confirm(self, msg, on_confirm, confirm_text="削除")

    # ------------------------------------------------------------------
    # ライフサイクル
    # ------------------------------------------------------------------

    def on_show(self) -> None:
        """ビュー表示時にデータを再読み込みする。"""
        self._load_presets()
