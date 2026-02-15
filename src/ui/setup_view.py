"""新規ディベート設定画面"""

from __future__ import annotations

import os
from tkinter import filedialog
from typing import TYPE_CHECKING

import customtkinter as ctk

from src.models.debate import Debate
from src.models.participant import Participant, ParticipantRole, ParticipantType
from src.models.role_preset import TargetRole

if TYPE_CHECKING:
    from src.models.role_preset import RolePreset
    from src.models.settings import LLMProviderConfig


class _FileAttachmentWidget(ctk.CTkFrame):
    """添付ファイル選択ウィジェット。"""

    SUPPORTED_EXTENSIONS = [
        ("対応ファイル", "*.pdf *.txt *.md *.csv *.png *.jpg *.jpeg *.gif *.webp"),
        ("すべてのファイル", "*.*"),
    ]

    def __init__(self, master, **kwargs):
        super().__init__(master, **kwargs)
        self._files: list[str] = []  # フルパスリスト

        self.grid_columnconfigure(0, weight=1)

        self._add_btn = ctk.CTkButton(
            self, text="ファイルを選択...", command=self._select_files, width=140
        )
        self._add_btn.grid(row=0, column=0, sticky="w", pady=(0, 4))

        self._file_list_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._file_list_frame.grid(row=1, column=0, sticky="ew")
        self._file_list_frame.grid_columnconfigure(0, weight=1)

    def _select_files(self) -> None:
        paths = filedialog.askopenfilenames(filetypes=self.SUPPORTED_EXTENSIONS)
        if paths:
            for p in paths:
                if p not in self._files:
                    self._files.append(p)
            self._refresh_list()

    def _refresh_list(self) -> None:
        for child in self._file_list_frame.winfo_children():
            child.destroy()
        for idx, fpath in enumerate(self._files):
            fname = os.path.basename(fpath)
            fsize = os.path.getsize(fpath) if os.path.exists(fpath) else 0
            size_label = f"({fsize // 1024}KB)" if fsize > 0 else ""

            row_frame = ctk.CTkFrame(self._file_list_frame, fg_color="transparent")
            row_frame.grid(row=idx, column=0, sticky="ew", pady=1)
            row_frame.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                row_frame, text=f"  {fname} {size_label}", anchor="w"
            ).grid(row=0, column=0, sticky="w")

            ctk.CTkButton(
                row_frame,
                text="x",
                width=28,
                height=24,
                fg_color="gray40",
                hover_color="red",
                command=lambda i=idx: self._remove_file(i),
            ).grid(row=0, column=1, padx=(4, 0))

    def _remove_file(self, idx: int) -> None:
        if 0 <= idx < len(self._files):
            self._files.pop(idx)
            self._refresh_list()

    def get_files(self) -> list[str]:
        return list(self._files)

    def clear(self) -> None:
        self._files.clear()
        self._refresh_list()


class _ParticipantSection(ctk.CTkFrame):
    """参加者設定セクション（A/B/C共通）。"""

    def __init__(
        self,
        master,
        label: str,
        role: ParticipantRole,
        target_role_filter: TargetRole,
        default_name: str,
        proposal_label: str,
        show_skip_timeout: bool = False,
        app=None,
        **kwargs,
    ):
        super().__init__(master, **kwargs)
        self._app = app
        self._role = role
        self._target_role_filter = target_role_filter
        self._show_skip_timeout = show_skip_timeout
        self._is_custom_mode = False
        self._presets: list[RolePreset] = []
        self._providers: list[LLMProviderConfig] = []

        self.grid_columnconfigure(1, weight=1)

        row = 0

        # --- ヘッダー ---
        ctk.CTkLabel(
            self, text=label, font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=row, column=0, columnspan=3, sticky="w", padx=8, pady=(8, 4))
        row += 1

        # --- 担当タイプ ---
        type_frame = ctk.CTkFrame(self, fg_color="transparent")
        type_frame.grid(row=row, column=0, columnspan=3, sticky="w", padx=8, pady=2)
        ctk.CTkLabel(type_frame, text="担当:").pack(side="left", padx=(0, 8))
        self._type_var = ctk.StringVar(value="llm")
        self._radio_llm = ctk.CTkRadioButton(
            type_frame, text="LLM", variable=self._type_var, value="llm",
            command=self._on_type_changed,
        )
        self._radio_llm.pack(side="left", padx=(0, 12))
        self._radio_human = ctk.CTkRadioButton(
            type_frame, text="人間", variable=self._type_var, value="human",
            command=self._on_type_changed,
        )
        self._radio_human.pack(side="left")
        row += 1

        # --- 名前 ---
        ctk.CTkLabel(self, text="名前:").grid(
            row=row, column=0, sticky="w", padx=8, pady=2
        )
        self._name_entry = ctk.CTkEntry(self, placeholder_text=default_name, width=200)
        self._name_entry.grid(row=row, column=1, sticky="w", padx=4, pady=2)
        self._name_entry.insert(0, default_name)
        row += 1

        # --- ロールプリセット ---
        role_frame = ctk.CTkFrame(self, fg_color="transparent")
        role_frame.grid(row=row, column=0, columnspan=3, sticky="ew", padx=8, pady=2)
        role_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(role_frame, text="ロール:").grid(row=0, column=0, sticky="w")
        self._preset_combo = ctk.CTkComboBox(
            role_frame,
            values=["(カスタム)"],
            command=self._on_preset_selected,
            width=250,
        )
        self._preset_combo.grid(row=0, column=1, sticky="w", padx=4)
        self._custom_toggle_btn = ctk.CTkButton(
            role_frame,
            text="カスタム入力に切替",
            width=150,
            command=self._toggle_custom_mode,
        )
        self._custom_toggle_btn.grid(row=0, column=2, padx=4)
        row += 1

        # --- プリセット読み取り専用表示 ---
        self._preset_display_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._preset_display_frame.grid(
            row=row, column=0, columnspan=3, sticky="ew", padx=12, pady=2
        )
        self._preset_display_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self._preset_display_frame, text="性格:", text_color="gray").grid(
            row=0, column=0, sticky="nw", padx=(0, 4)
        )
        self._preset_personality_label = ctk.CTkLabel(
            self._preset_display_frame, text="(未選択)", anchor="w", wraplength=500
        )
        self._preset_personality_label.grid(row=0, column=1, sticky="w")

        ctk.CTkLabel(
            self._preset_display_frame, text="行動指針:", text_color="gray"
        ).grid(row=1, column=0, sticky="nw", padx=(0, 4))
        self._preset_guidelines_label = ctk.CTkLabel(
            self._preset_display_frame, text="(未選択)", anchor="w", wraplength=500
        )
        self._preset_guidelines_label.grid(row=1, column=1, sticky="w")
        row += 1

        # --- カスタム入力エリア（初期非表示）---
        self._custom_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._custom_frame.grid(
            row=row, column=0, columnspan=3, sticky="ew", padx=12, pady=2
        )
        self._custom_frame.grid_columnconfigure(1, weight=1)

        ctk.CTkLabel(self._custom_frame, text="役割説明:").grid(
            row=0, column=0, sticky="nw", padx=(0, 4), pady=2
        )
        self._custom_role_desc = ctk.CTkTextbox(self._custom_frame, height=40)
        self._custom_role_desc.grid(row=0, column=1, sticky="ew", pady=2)

        ctk.CTkLabel(self._custom_frame, text="性格:").grid(
            row=1, column=0, sticky="nw", padx=(0, 4), pady=2
        )
        self._custom_personality = ctk.CTkTextbox(self._custom_frame, height=40)
        self._custom_personality.grid(row=1, column=1, sticky="ew", pady=2)

        ctk.CTkLabel(self._custom_frame, text="行動指針:").grid(
            row=2, column=0, sticky="nw", padx=(0, 4), pady=2
        )
        self._custom_guidelines = ctk.CTkTextbox(self._custom_frame, height=40)
        self._custom_guidelines.grid(row=2, column=1, sticky="ew", pady=2)

        self._custom_frame.grid_remove()  # 初期非表示
        row += 1

        # --- 主張 / 判定の観点テキストエリア ---
        ctk.CTkLabel(self, text=f"{proposal_label}:").grid(
            row=row, column=0, sticky="nw", padx=8, pady=2
        )
        self._proposal_text = ctk.CTkTextbox(self, height=80)
        self._proposal_text.grid(
            row=row, column=1, columnspan=2, sticky="ew", padx=4, pady=2
        )
        row += 1

        # --- 添付ファイル ---
        ctk.CTkLabel(self, text="添付ファイル:").grid(
            row=row, column=0, sticky="nw", padx=8, pady=2
        )
        self._attachment_widget = _FileAttachmentWidget(self)
        self._attachment_widget.grid(
            row=row, column=1, columnspan=2, sticky="ew", padx=4, pady=2
        )
        row += 1

        # --- LLM選択 ---
        llm_frame = ctk.CTkFrame(self, fg_color="transparent")
        llm_frame.grid(row=row, column=0, columnspan=3, sticky="ew", padx=8, pady=2)

        ctk.CTkLabel(llm_frame, text="LLM:").pack(side="left", padx=(0, 4))
        self._llm_combo = ctk.CTkComboBox(llm_frame, values=["(なし)"], width=250)
        self._llm_combo.pack(side="left", padx=4)
        row += 1

        # --- 最大トークン ---
        token_frame = ctk.CTkFrame(self, fg_color="transparent")
        token_frame.grid(row=row, column=0, columnspan=3, sticky="w", padx=8, pady=2)

        ctk.CTkLabel(token_frame, text="最大トークン/回:").pack(side="left", padx=(0, 4))
        self._max_tokens_entry = ctk.CTkEntry(token_frame, width=80)
        self._max_tokens_entry.pack(side="left", padx=4)
        self._max_tokens_entry.insert(0, "500")
        row += 1

        # --- 思考コンテキスト含有チェックボックス ---
        self._include_thinking_var = ctk.BooleanVar(value=True)
        self._include_thinking_cb = ctk.CTkCheckBox(
            self,
            text="自身の過去の思考をコンテキストに含める",
            variable=self._include_thinking_var,
        )
        self._include_thinking_cb.grid(
            row=row, column=0, columnspan=3, sticky="w", padx=8, pady=2
        )
        row += 1

        # --- スキップタイムアウト（Cのみ） ---
        if self._show_skip_timeout:
            timeout_frame = ctk.CTkFrame(self, fg_color="transparent")
            timeout_frame.grid(
                row=row, column=0, columnspan=3, sticky="w", padx=8, pady=2
            )
            ctk.CTkLabel(timeout_frame, text="スキップタイムアウト:").pack(
                side="left", padx=(0, 4)
            )
            self._skip_timeout_entry = ctk.CTkEntry(timeout_frame, width=60)
            self._skip_timeout_entry.pack(side="left", padx=4)
            self._skip_timeout_entry.insert(0, "5")
            ctk.CTkLabel(timeout_frame, text="秒").pack(side="left")
            row += 1
        else:
            self._skip_timeout_entry = None

        # プリセット・プロバイダの初期読み込み
        self._load_presets()
        self._load_providers()

    # ---- プリセット/プロバイダ読み込み ----

    def _load_presets(self) -> None:
        """プリセット一覧をドロップダウンに読み込む。"""
        self._presets = []
        try:
            if self._app and hasattr(self._app, "preset_service") and self._app.preset_service:
                self._presets = self._app.preset_service.list_presets(
                    self._target_role_filter
                )
        except Exception:
            pass

        names = ["(カスタム)"] + [p.name for p in self._presets]
        self._preset_combo.configure(values=names)
        self._preset_combo.set("(カスタム)")

    def _load_providers(self) -> None:
        """LLMプロバイダ一覧をドロップダウンに読み込む。"""
        self._providers = []
        try:
            if self._app and hasattr(self._app, "llm_service") and self._app.llm_service:
                self._providers = self._app.llm_service.list_configs()
        except Exception:
            pass

        names = [p.name for p in self._providers]
        if not names:
            names = ["(未設定)"]
        self._llm_combo.configure(values=names)
        self._llm_combo.set(names[0])

    # ---- コールバック ----

    def _on_type_changed(self) -> None:
        """担当タイプ切替時にLLM関連コントロールの有効/無効を制御する。"""
        is_human = self._type_var.get() == "human"

        if is_human:
            # 人間の場合: LLM関連コントロールを全て無効化
            self._llm_combo.configure(state="disabled")
            self._preset_combo.configure(state="disabled")
            self._custom_toggle_btn.configure(state="disabled")
            self._max_tokens_entry.configure(state="disabled")
            self._include_thinking_cb.configure(state="disabled")
            self._custom_role_desc.configure(state="disabled")
            self._custom_personality.configure(state="disabled")
            self._custom_guidelines.configure(state="disabled")
        else:
            # LLM の場合: コントロールを有効化（カスタムモードに応じて復元）
            self._llm_combo.configure(state="normal")
            self._max_tokens_entry.configure(state="normal")
            self._include_thinking_cb.configure(state="normal")
            self._custom_toggle_btn.configure(state="normal")
            if self._is_custom_mode:
                self._preset_combo.configure(state="disabled")
                self._custom_role_desc.configure(state="normal")
                self._custom_personality.configure(state="normal")
                self._custom_guidelines.configure(state="normal")
            else:
                self._preset_combo.configure(state="normal")
                self._custom_role_desc.configure(state="disabled")
                self._custom_personality.configure(state="disabled")
                self._custom_guidelines.configure(state="disabled")

    def _on_preset_selected(self, choice: str) -> None:
        """プリセット選択時に読み取り専用表示を更新する。"""
        if choice == "(カスタム)":
            self._preset_personality_label.configure(text="(カスタム入力を使用)")
            self._preset_guidelines_label.configure(text="(カスタム入力を使用)")
            return

        preset = self._find_preset_by_name(choice)
        if preset:
            self._preset_personality_label.configure(text=preset.personality or "(未設定)")
            self._preset_guidelines_label.configure(text=preset.guidelines or "(未設定)")

    def _toggle_custom_mode(self) -> None:
        """プリセット表示とカスタム入力を切り替える。"""
        self._is_custom_mode = not self._is_custom_mode
        if self._is_custom_mode:
            self._preset_display_frame.grid_remove()
            self._custom_frame.grid()
            self._preset_combo.configure(state="disabled")
            self._custom_toggle_btn.configure(text="プリセット選択に切替")
        else:
            self._custom_frame.grid_remove()
            self._preset_display_frame.grid()
            self._preset_combo.configure(state="normal")
            self._custom_toggle_btn.configure(text="カスタム入力に切替")

    def _find_preset_by_name(self, name: str):
        for p in self._presets:
            if p.name == name:
                return p
        return None

    # ---- データ取得 ----

    def get_participant_data(self, debate_id: str) -> Participant:
        """入力内容からParticipantインスタンスを生成する。"""
        ptype = ParticipantType.LLM if self._type_var.get() == "llm" else ParticipantType.HUMAN
        name = self._name_entry.get().strip() or self._role.value

        # LLMプロバイダ
        llm_provider = None
        llm_model = None
        if ptype == ParticipantType.LLM:
            selected_name = self._llm_combo.get()
            for prov in self._providers:
                if prov.name == selected_name:
                    llm_provider = prov.id
                    llm_model = prov.model or prov.deployment_name or prov.name
                    break

        # プリセット or カスタム
        preset_id = None
        custom_role_desc = None
        custom_personality = None
        custom_guidelines = None

        if self._is_custom_mode:
            custom_role_desc = self._custom_role_desc.get("1.0", "end-1c").strip()
            custom_personality = self._custom_personality.get("1.0", "end-1c").strip()
            custom_guidelines = self._custom_guidelines.get("1.0", "end-1c").strip()
        else:
            selected_preset_name = self._preset_combo.get()
            preset = self._find_preset_by_name(selected_preset_name)
            if preset:
                preset_id = preset.id

        # 最大トークン
        try:
            max_tokens = int(self._max_tokens_entry.get())
        except ValueError:
            max_tokens = 500

        return Participant(
            debate_id=debate_id,
            role=self._role,
            name=name,
            type=ptype,
            llm_provider=llm_provider,
            llm_model=llm_model,
            preset_id=preset_id,
            custom_role_desc=custom_role_desc,
            custom_personality=custom_personality,
            custom_guidelines=custom_guidelines,
            max_tokens_per_turn=max_tokens,
            include_own_thinking=self._include_thinking_var.get(),
        )

    def get_proposal_text(self) -> str:
        return self._proposal_text.get("1.0", "end-1c").strip()

    def get_attachment_files(self) -> list[str]:
        return self._attachment_widget.get_files()

    def get_skip_timeout(self) -> int:
        if self._skip_timeout_entry is None:
            return 5
        try:
            return int(self._skip_timeout_entry.get())
        except ValueError:
            return 5

    def on_show(self) -> None:
        """ビュー表示時にプリセット/プロバイダを再読み込みする。"""
        self._load_presets()
        self._load_providers()


class SetupView(ctk.CTkFrame):
    """新規ディベート設定画面。"""

    def __init__(self, master, app, **kwargs):
        super().__init__(master, **kwargs)
        self._app = app

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # --- ヘッダー ---
        header = ctk.CTkLabel(
            self,
            text="新規ディベート設定",
            font=ctk.CTkFont(size=18, weight="bold"),
            anchor="w",
        )
        header.grid(row=0, column=0, sticky="w", padx=20, pady=(16, 8))

        # --- スクロール可能なコンテンツ ---
        self._scroll = ctk.CTkScrollableFrame(self)
        self._scroll.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 8))
        self._scroll.grid_columnconfigure(0, weight=1)

        content_row = 0

        # テーマ入力
        ctk.CTkLabel(
            self._scroll, text="テーマ:", font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=content_row, column=0, sticky="w", padx=8, pady=(8, 2))
        content_row += 1

        self._topic_entry = ctk.CTkEntry(
            self._scroll, placeholder_text="議論のテーマを入力してください"
        )
        self._topic_entry.grid(row=content_row, column=0, sticky="ew", padx=8, pady=(0, 8))
        content_row += 1

        # 参加者A
        self._section_a = _ParticipantSection(
            self._scroll,
            label="参加者A（案X推進）",
            role=ParticipantRole.PROPOSER_A,
            target_role_filter=TargetRole.PROPOSER,
            default_name="参加者A",
            proposal_label="主張（案X）",
            app=app,
            corner_radius=8,
        )
        self._section_a.grid(row=content_row, column=0, sticky="ew", padx=8, pady=4)
        content_row += 1

        # 参加者B
        self._section_b = _ParticipantSection(
            self._scroll,
            label="参加者B（案Y推進）",
            role=ParticipantRole.PROPOSER_B,
            target_role_filter=TargetRole.PROPOSER,
            default_name="参加者B",
            proposal_label="主張（案Y）",
            app=app,
            corner_radius=8,
        )
        self._section_b.grid(row=content_row, column=0, sticky="ew", padx=8, pady=4)
        content_row += 1

        # 参加者C
        self._section_c = _ParticipantSection(
            self._scroll,
            label="参加者C（判定者）",
            role=ParticipantRole.JUDGE,
            target_role_filter=TargetRole.JUDGE,
            default_name="判定者C",
            proposal_label="判定の観点・指示",
            show_skip_timeout=True,
            app=app,
            corner_radius=8,
        )
        self._section_c.grid(row=content_row, column=0, sticky="ew", padx=8, pady=4)
        content_row += 1

        # 進行設定
        round_frame = ctk.CTkFrame(self._scroll, corner_radius=8)
        round_frame.grid(row=content_row, column=0, sticky="ew", padx=8, pady=4)
        round_frame.grid_columnconfigure(1, weight=1)
        ctk.CTkLabel(
            round_frame, text="進行設定", font=ctk.CTkFont(size=14, weight="bold")
        ).grid(row=0, column=0, columnspan=2, sticky="w", padx=8, pady=(8, 4))
        ctk.CTkLabel(round_frame, text="最大ラウンド数:").grid(
            row=1, column=0, sticky="w", padx=8, pady=(0, 8)
        )
        self._max_rounds_entry = ctk.CTkEntry(round_frame, width=80)
        self._max_rounds_entry.grid(row=1, column=1, sticky="w", padx=4, pady=(0, 8))
        self._max_rounds_entry.insert(0, "5")
        content_row += 1

        # --- フッター（ボタン） ---
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=20, pady=(4, 16))

        self._cancel_btn = ctk.CTkButton(
            footer, text="キャンセル", fg_color="gray40", hover_color="gray30",
            command=self._on_cancel,
        )
        self._cancel_btn.pack(side="right", padx=(8, 0))

        self._start_btn = ctk.CTkButton(
            footer, text="ディベート開始", command=self._on_start
        )
        self._start_btn.pack(side="right")

    def _on_cancel(self) -> None:
        """キャンセルボタン: メインビューに戻る。"""
        main_window = self._get_main_window()
        if main_window:
            main_window.show_view("history")

    def _on_start(self) -> None:
        """ディベート開始ボタン。"""
        topic = self._topic_entry.get().strip()
        if not topic:
            self._show_error("テーマを入力してください。")
            return

        proposal_x = self._section_a.get_proposal_text()
        proposal_y = self._section_b.get_proposal_text()
        judge_instruction = self._section_c.get_proposal_text()

        try:
            max_rounds = int(self._max_rounds_entry.get())
        except ValueError:
            max_rounds = 5

        # Debateオブジェクト作成
        debate = Debate(
            title=topic,
            topic=topic,
            proposal_x=proposal_x,
            proposal_y=proposal_y,
            judge_instruction=judge_instruction,
            max_rounds=max_rounds,
        )

        # Participantオブジェクト作成
        participant_a = self._section_a.get_participant_data(debate.id)
        participant_b = self._section_b.get_participant_data(debate.id)
        participant_c = self._section_c.get_participant_data(debate.id)
        participants = [participant_a, participant_b, participant_c]

        # DB保存
        try:
            if self._app and hasattr(self._app, "history_service") and self._app.history_service:
                self._app.history_service.save_debate(debate)
                for p in participants:
                    self._app.history_service.save_participant(p)

                # 添付ファイル保存
                self._save_attachments(debate.id, participant_a.role.value, self._section_a)
                self._save_attachments(debate.id, participant_b.role.value, self._section_b)
                self._save_attachments(debate.id, participant_c.role.value, self._section_c)
        except Exception as e:
            self._show_error(f"保存エラー: {e}")
            return

        # ディベート画面に遷移してディベート開始
        main_window = self._get_main_window()
        if main_window:
            debate_view = main_window._views.get("debate")
            if debate_view and hasattr(debate_view, "start_debate"):
                debate_view.start_debate(debate, participants)
            main_window.show_view("debate")

    def _save_attachments(
        self, debate_id: str, participant_role: str, section: _ParticipantSection
    ) -> None:
        """添付ファイルをコピー保存しDBに登録する。"""
        files = section.get_attachment_files()
        if not files:
            return
        try:
            if self._app and hasattr(self._app, "attachment_service") and self._app.attachment_service:
                for fpath in files:
                    attachment = self._app.attachment_service.save_file(
                        debate_id, participant_role, fpath
                    )
                    if hasattr(self._app, "history_service") and self._app.history_service:
                        self._app.history_service.save_attachment(attachment)
        except Exception:
            pass  # 添付失敗は致命的ではない

    def _get_main_window(self):
        widget = self.master
        while widget is not None:
            if isinstance(widget, ctk.CTk):
                return widget
            widget = getattr(widget, "master", None)
        return None

    def _show_error(self, msg: str) -> None:
        """エラーダイアログ。"""
        from src.ui.dialogs import show_error

        show_error(self, msg)

    def on_show(self) -> None:
        """ビュー表示時にサブセクションのプリセット等を再読み込みする。"""
        self._section_a.on_show()
        self._section_b.on_show()
        self._section_c.on_show()
