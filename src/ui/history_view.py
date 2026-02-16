"""履歴閲覧画面"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import customtkinter as ctk

from src.models.debate import Debate, DebateStatus
from src.models.message import Message, MessageType
from src.models.participant import Participant, ParticipantRole, ParticipantType
from src.ui.components.message_bubble import _ROLE_COLORS, _SKIP_COLORS
from src.ui.components.thinking_panel import ThinkingPanel

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# 内部コンポーネント
# ---------------------------------------------------------------------------


class _DebateListItem(ctk.CTkFrame):
    """履歴リストの個別アイテム。"""

    def __init__(self, master, debate: Debate, on_select, **kwargs):
        super().__init__(master, corner_radius=6, cursor="hand2", **kwargs)
        self._debate = debate
        self._on_select = on_select
        self.grid_columnconfigure(0, weight=1)

        # タイトル
        ctk.CTkLabel(
            self,
            text=debate.title,
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=8, pady=(6, 0))

        # 日時 + ステータス
        status_map = {
            DebateStatus.PENDING: "未開始",
            DebateStatus.RUNNING: "進行中",
            DebateStatus.PAUSED: "一時停止",
            DebateStatus.COMPLETED: "完了",
        }
        status_text = status_map.get(debate.status, debate.status.value)
        date_text = debate.created_at.strftime("%Y-%m-%d %H:%M")

        ctk.CTkLabel(
            self,
            text=f"{date_text}  |  {status_text}",
            anchor="w",
            text_color="gray",
            font=ctk.CTkFont(size=11),
        ).grid(row=1, column=0, sticky="w", padx=8, pady=(0, 6))

        # クリックイベント
        self.bind("<Button-1>", lambda e: self._on_select(debate))
        for child in self.winfo_children():
            child.bind("<Button-1>", lambda e: self._on_select(debate))


# ---------------------------------------------------------------------------
# メインビュー
# ---------------------------------------------------------------------------


class HistoryView(ctk.CTkFrame):
    """履歴閲覧画面。

    左: ディベート一覧リスト
    右: 選択したディベートの詳細表示
    """

    def __init__(self, master, app, **kwargs):
        super().__init__(master, **kwargs)
        self._app = app
        self._debates: list[Debate] = []
        self._selected_debate: Debate | None = None
        self._thinking_panels: list[ThinkingPanel] = []
        self._show_thinking = False

        self.grid_columnconfigure(0, minsize=300)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- 左: 一覧リスト ---
        left_frame = ctk.CTkFrame(self)
        left_frame.grid(row=0, column=0, sticky="nsew", padx=(4, 2), pady=4)
        left_frame.grid_columnconfigure(0, weight=1)
        left_frame.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            left_frame,
            text="ディベート履歴",
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=12, pady=(12, 4))

        self._list_scroll = ctk.CTkScrollableFrame(left_frame)
        self._list_scroll.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        self._list_scroll.grid_columnconfigure(0, weight=1)

        # --- 右: 詳細ビュー ---
        right_frame = ctk.CTkFrame(self)
        right_frame.grid(row=0, column=1, sticky="nsew", padx=(2, 4), pady=4)
        right_frame.grid_columnconfigure(0, weight=1)
        right_frame.grid_rowconfigure(2, weight=1)

        # 詳細ヘッダー
        detail_header = ctk.CTkFrame(right_frame, fg_color="transparent")
        detail_header.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 4))
        detail_header.grid_columnconfigure(0, weight=1)

        self._detail_title = ctk.CTkLabel(
            detail_header,
            text="ディベートを選択してください",
            font=ctk.CTkFont(size=16, weight="bold"),
            anchor="w",
        )
        self._detail_title.grid(row=0, column=0, sticky="w")

        # アクションボタン
        btn_frame = ctk.CTkFrame(detail_header, fg_color="transparent")
        btn_frame.grid(row=0, column=1, sticky="e")

        self._export_btn = ctk.CTkButton(
            btn_frame,
            text="Markdownエクスポート",
            width=170,
            command=self._on_export,
            state="disabled",
        )
        self._export_btn.pack(side="left", padx=4)

        self._delete_btn = ctk.CTkButton(
            btn_frame,
            text="削除",
            width=80,
            fg_color="red",
            hover_color="darkred",
            command=self._on_delete,
            state="disabled",
        )
        self._delete_btn.pack(side="left", padx=4)

        # 思考表示チェックボックス
        self._thinking_var = ctk.BooleanVar(value=False)
        self._thinking_cb = ctk.CTkCheckBox(
            right_frame,
            text="思考（thinking）を表示する",
            variable=self._thinking_var,
            command=self._on_thinking_toggle,
        )
        self._thinking_cb.grid(row=1, column=0, sticky="w", padx=12, pady=4)

        # 詳細コンテンツ（スクロール可能）
        self._detail_scroll = ctk.CTkScrollableFrame(right_frame)
        self._detail_scroll.grid(row=2, column=0, sticky="nsew", padx=4, pady=4)
        self._detail_scroll.grid_columnconfigure(0, weight=1)

    # ------------------------------------------------------------------
    # 一覧の読み込み
    # ------------------------------------------------------------------

    def _load_debates(self) -> None:
        """DBからディベート一覧を読み込む。"""
        self._debates = []
        try:
            if self._app and hasattr(self._app, "history_service") and self._app.history_service:
                self._debates = self._app.history_service.list_debates()
        except Exception:
            pass
        self._refresh_list()

    def _refresh_list(self) -> None:
        """一覧リストを再描画する。"""
        for child in self._list_scroll.winfo_children():
            child.destroy()

        if not self._debates:
            ctk.CTkLabel(
                self._list_scroll, text="履歴がありません", text_color="gray"
            ).grid(row=0, column=0, padx=12, pady=20)
            return

        for idx, debate in enumerate(self._debates):
            item = _DebateListItem(
                self._list_scroll,
                debate=debate,
                on_select=self._on_debate_selected,
            )
            item.grid(row=idx, column=0, sticky="ew", padx=4, pady=4)

    # ------------------------------------------------------------------
    # 詳細表示
    # ------------------------------------------------------------------

    def _on_debate_selected(self, debate: Debate) -> None:
        """ディベートが選択された時の処理。"""
        self._selected_debate = debate
        self._export_btn.configure(state="normal")
        self._delete_btn.configure(state="normal")
        self._render_detail(debate)

    def _render_detail(self, debate: Debate) -> None:
        """詳細コンテンツを描画する。"""
        # クリア
        for child in self._detail_scroll.winfo_children():
            child.destroy()
        self._thinking_panels.clear()

        self._detail_title.configure(text=debate.title)

        row = 0

        # メタ情報
        meta_frame = ctk.CTkFrame(self._detail_scroll, corner_radius=6)
        meta_frame.grid(row=row, column=0, sticky="ew", padx=4, pady=4)
        meta_frame.grid_columnconfigure(1, weight=1)

        meta_items = [
            ("テーマ", debate.topic),
            ("案X", debate.proposal_x),
            ("案Y", debate.proposal_y),
            ("日時", debate.created_at.strftime("%Y-%m-%d %H:%M")),
            ("ラウンド", f"{debate.current_round}/{debate.max_rounds}"),
        ]
        if debate.winner:
            meta_items.append(("判定結果", debate.winner))

        for mi, (k, v) in enumerate(meta_items):
            ctk.CTkLabel(
                meta_frame, text=f"{k}:", font=ctk.CTkFont(weight="bold"), anchor="nw"
            ).grid(row=mi, column=0, sticky="nw", padx=(8, 4), pady=2)
            ctk.CTkLabel(
                meta_frame, text=v or "(なし)", anchor="w", wraplength=400
            ).grid(row=mi, column=1, sticky="w", padx=4, pady=2)
        row += 1

        # 参加者情報
        participants: list[Participant] = []
        try:
            if self._app and hasattr(self._app, "history_service") and self._app.history_service:
                participants = self._app.history_service.get_participants(debate.id)
        except Exception:
            pass

        participant_map: dict[str, Participant] = {p.id: p for p in participants}

        if participants:
            p_frame = ctk.CTkFrame(self._detail_scroll, corner_radius=6)
            p_frame.grid(row=row, column=0, sticky="ew", padx=4, pady=4)
            p_frame.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                p_frame,
                text="参加者",
                font=ctk.CTkFont(size=13, weight="bold"),
                anchor="w",
            ).grid(row=0, column=0, sticky="w", padx=8, pady=(6, 2))

            for pi, p in enumerate(participants):
                role_labels = {
                    ParticipantRole.PROPOSER_A: "A（案X推進）",
                    ParticipantRole.PROPOSER_B: "B（案Y推進）",
                    ParticipantRole.JUDGE: "C（判定者）",
                }
                role_text = role_labels.get(p.role, p.role.value)
                type_text = "LLM" if p.type == ParticipantType.LLM else "人間"
                model_text = p.llm_model or "-"

                ctk.CTkLabel(
                    p_frame,
                    text=f"  {role_text}: {p.name} ({type_text}, {model_text})",
                    anchor="w",
                ).grid(row=pi + 1, column=0, sticky="w", padx=8, pady=1)

            row += 1

        # メッセージ一覧
        messages: list[Message] = []
        try:
            if self._app and hasattr(self._app, "history_service") and self._app.history_service:
                messages = self._app.history_service.get_messages(debate.id)
        except Exception:
            pass

        if messages:
            # ラウンド別にグループ化
            rounds: dict[int, list[Message]] = {}
            for msg in messages:
                rounds.setdefault(msg.round_number, []).append(msg)

            for round_num in sorted(rounds.keys()):
                round_label = ctk.CTkLabel(
                    self._detail_scroll,
                    text=f"--- ラウンド {round_num} ---",
                    font=ctk.CTkFont(size=13, weight="bold"),
                    text_color="gray",
                )
                round_label.grid(row=row, column=0, sticky="ew", padx=8, pady=(12, 4))
                row += 1

                # 参加者ごとのメッセージをまとめる
                current_pid = None
                thinking_text = None
                speech_text = None
                msg_type = None

                for msg in rounds[round_num]:
                    if msg.participant_id != current_pid:
                        # 前の参加者のブロックを出力
                        if current_pid is not None:
                            row = self._render_message_block(
                                row, participant_map.get(current_pid),
                                thinking_text, speech_text, msg_type,
                            )
                        current_pid = msg.participant_id
                        thinking_text = None
                        speech_text = None
                        msg_type = None

                    if msg.message_type == MessageType.THINKING:
                        thinking_text = msg.content
                    elif msg.message_type == MessageType.SPEECH:
                        speech_text = msg.content
                        msg_type = MessageType.SPEECH
                    elif msg.message_type == MessageType.SKIP:
                        speech_text = "(スキップ)"
                        msg_type = MessageType.SKIP
                    elif msg.message_type == MessageType.JUDGMENT:
                        speech_text = msg.content
                        msg_type = MessageType.JUDGMENT

                # 最後の参加者のブロック
                if current_pid is not None:
                    row = self._render_message_block(
                        row, participant_map.get(current_pid),
                        thinking_text, speech_text, msg_type,
                    )

        # 最終判定
        judgment_msgs = [m for m in messages if m.message_type == MessageType.JUDGMENT]
        if judgment_msgs or debate.winner:
            verdict_frame = ctk.CTkFrame(
                self._detail_scroll, corner_radius=6, fg_color=("gray85", "gray20")
            )
            verdict_frame.grid(row=row, column=0, sticky="ew", padx=4, pady=8)
            verdict_frame.grid_columnconfigure(0, weight=1)

            ctk.CTkLabel(
                verdict_frame,
                text="=== 最終判定 ===",
                font=ctk.CTkFont(size=14, weight="bold"),
            ).grid(row=0, column=0, padx=8, pady=(8, 2))

            if debate.winner:
                ctk.CTkLabel(
                    verdict_frame, text=f"判定結果: {debate.winner}", anchor="w"
                ).grid(row=1, column=0, sticky="w", padx=8, pady=(0, 4))

            for ji, jm in enumerate(judgment_msgs):
                p = participant_map.get(jm.participant_id)
                name = p.name if p else "不明"
                ctk.CTkLabel(
                    verdict_frame,
                    text=f"{name}: {jm.content}",
                    anchor="w",
                    wraplength=500,
                    justify="left",
                ).grid(row=2 + ji, column=0, sticky="w", padx=8, pady=(0, 6))

            row += 1

    def _render_message_block(
        self,
        row: int,
        participant: Participant | None,
        thinking: str | None,
        speech: str | None,
        msg_type: MessageType | None,
    ) -> int:
        """1参加者分のメッセージブロックを描画する。rowを返す。"""
        if participant is None:
            return row

        # ロール別の色を取得
        role_short = {
            ParticipantRole.PROPOSER_A: "A",
            ParticipantRole.PROPOSER_B: "B",
            ParticipantRole.JUDGE: "C",
        }
        role_key = role_short.get(participant.role, "A")

        is_skip = msg_type == MessageType.SKIP
        if is_skip:
            colors = _SKIP_COLORS
            bg_color = colors.get("bg", "#2b2b2b")
        else:
            colors = _ROLE_COLORS.get(role_key, _ROLE_COLORS["A"])
            bg_color = colors["bg"]

        block = ctk.CTkFrame(self._detail_scroll, corner_radius=10, fg_color=bg_color)
        block.grid(row=row, column=0, sticky="ew", padx=8, pady=2)
        block.grid_columnconfigure(0, weight=1)

        block_row = 0

        # ヘッダー（ディベートビューと同じスタイル）
        header_frame = ctk.CTkFrame(block, fg_color="transparent")
        header_frame.grid(row=block_row, column=0, sticky="ew", padx=10, pady=(8, 2))
        header_frame.grid_columnconfigure(1, weight=1)
        block_row += 1

        if is_skip:
            # スキップ表示
            ctk.CTkLabel(
                header_frame,
                text=f"（{participant.name} はこのラウンドをスキップしました）",
                text_color=_SKIP_COLORS.get("fg", "#888888"),
                font=ctk.CTkFont(size=12, slant="italic"),
                anchor="w",
            ).grid(row=0, column=0, columnspan=2, sticky="w")
        else:
            role_colors = _ROLE_COLORS.get(role_key, _ROLE_COLORS["A"])

            # ロールバッジ
            role_badge = ctk.CTkLabel(
                header_frame,
                text=f" {role_key} ",
                fg_color=role_colors["label_bg"],
                text_color=role_colors["label_fg"],
                corner_radius=4,
                font=ctk.CTkFont(size=12, weight="bold"),
                width=28,
                height=22,
            )
            role_badge.grid(row=0, column=0, sticky="w", padx=(0, 6))

            # 参加者名
            ctk.CTkLabel(
                header_frame,
                text=participant.name,
                text_color=role_colors["name_fg"],
                font=ctk.CTkFont(size=13, weight="bold"),
                anchor="w",
            ).grid(row=0, column=1, sticky="w")

            # メッセージタイプ表示
            if msg_type == MessageType.JUDGMENT:
                ctk.CTkLabel(
                    header_frame,
                    text="[判定]",
                    text_color=role_colors["round_fg"],
                    font=ctk.CTkFont(size=11),
                ).grid(row=0, column=2, sticky="e")

        # 思考パネル
        if thinking and not is_skip:
            p_name = participant.name if participant else ""
            panel = ThinkingPanel(block, thinking_text=thinking, participant_name=p_name)
            panel.grid(row=block_row, column=0, sticky="ew", padx=8, pady=2)
            if not self._show_thinking:
                panel.grid_remove()
            self._thinking_panels.append(panel)
            block_row += 1

        # 発言
        if speech and not is_skip:
            role_colors = _ROLE_COLORS.get(role_key, _ROLE_COLORS["A"])
            ctk.CTkLabel(
                block,
                text=speech,
                text_color=role_colors["content_fg"],
                font=ctk.CTkFont(size=13),
                anchor="nw",
                justify="left",
                wraplength=500,
            ).grid(row=block_row, column=0, sticky="w", padx=14, pady=(4, 10))
            block_row += 1

        return row + 1

    # ------------------------------------------------------------------
    # アクション
    # ------------------------------------------------------------------

    def _on_thinking_toggle(self) -> None:
        """思考表示チェックボックスの切替。"""
        self._show_thinking = self._thinking_var.get()
        for panel in self._thinking_panels:
            if self._show_thinking:
                panel.grid()
            else:
                panel.grid_remove()

    def _on_export(self) -> None:
        """Markdownエクスポートボタン。"""
        if self._selected_debate is None:
            return

        try:
            from src.services.export_service import ExportService

            debate = self._selected_debate
            participants = []
            messages = []
            if self._app and hasattr(self._app, "history_service") and self._app.history_service:
                participants = self._app.history_service.get_participants(debate.id)
                messages = self._app.history_service.get_messages(debate.id)

            export_dir = "./exports"
            if self._app and hasattr(self._app, "settings") and self._app.settings:
                export_dir = self._app.settings.export_dir

            exporter = ExportService(export_dir)
            filepath = exporter.export_debate(
                debate, participants, messages, include_thinking=True
            )

            self._show_info(f"エクスポート完了:\n{filepath}")
        except Exception as e:
            self._show_error(f"エクスポートエラー: {e}")

    def _on_delete(self) -> None:
        """削除ボタン（確認ダイアログ付き）。"""
        if self._selected_debate is None:
            return

        self._show_confirm(
            f"ディベート「{self._selected_debate.title}」を削除しますか？\nこの操作は取り消せません。",
            self._do_delete,
        )

    def _do_delete(self) -> None:
        """実際の削除処理。"""
        if self._selected_debate is None:
            return

        debate_id = self._selected_debate.id

        # DB削除
        try:
            if self._app and hasattr(self._app, "history_service") and self._app.history_service:
                self._app.history_service.delete_debate(debate_id)
        except Exception as e:
            self._show_error(f"削除エラー: {e}")
            return

        # 添付ファイル削除（ベストエフォート）
        try:
            if self._app and hasattr(self._app, "attachment_service") and self._app.attachment_service:
                self._app.attachment_service.delete_debate_files(debate_id)
        except Exception as e:
            import logging

            logging.getLogger(__name__).warning("添付ファイル削除エラー: %s", e)

        self._selected_debate = None

        # 詳細エリアをクリア
        for child in self._detail_scroll.winfo_children():
            child.destroy()
        self._thinking_panels.clear()
        self._detail_title.configure(text="ディベートを選択してください")
        self._export_btn.configure(state="disabled")
        self._delete_btn.configure(state="disabled")

        # リスト再読み込み
        self._load_debates()

    # ------------------------------------------------------------------
    # ダイアログ
    # ------------------------------------------------------------------

    def _show_info(self, msg: str) -> None:
        from src.ui.dialogs import show_info

        show_info(self, "情報", msg)

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
        self._load_debates()
