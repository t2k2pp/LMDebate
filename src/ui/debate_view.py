"""ディベート実行画面"""

from __future__ import annotations

import threading
from datetime import datetime
from typing import TYPE_CHECKING

import customtkinter as ctk

from src.models.debate import Debate, DebateStatus
from src.models.message import Message, MessageType
from src.models.participant import Participant, ParticipantRole, ParticipantType
from src.ui.components.message_bubble import MessageBubble
from src.ui.components.participant_card import ParticipantCard

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# 内部コンポーネント
# ---------------------------------------------------------------------------


class _LoadingIndicator(ctk.CTkFrame):
    """LLM生成中のローディング表示。"""

    def __init__(self, master, participant_name: str = "", **kwargs):
        super().__init__(master, corner_radius=8, fg_color=("gray80", "gray25"), **kwargs)
        self.grid_columnconfigure(0, weight=1)

        self._label = ctk.CTkLabel(
            self,
            text=f"{participant_name} が発言を生成中...",
            font=ctk.CTkFont(size=12),
        )
        self._label.grid(row=0, column=0, padx=10, pady=8)

        self._progress = ctk.CTkProgressBar(self, mode="indeterminate", width=300)
        self._progress.grid(row=1, column=0, padx=10, pady=(0, 8))
        self._progress.start()

    def stop(self) -> None:
        self._progress.stop()


# ---------------------------------------------------------------------------
# メインビュー
# ---------------------------------------------------------------------------


class DebateView(ctk.CTkFrame):
    """ディベート実行画面。

    左: スクロール可能なチャットエリア
    右: 参加者カード + 進行情報
    下: 人間入力エリア
    """

    def __init__(self, master, app, **kwargs):
        super().__init__(master, **kwargs)
        self._app = app
        self._debate: Debate | None = None
        self._participants: dict[str, Participant] = {}
        self._role_to_participant: dict[ParticipantRole, Participant] = {}
        self._participant_cards: dict[str, ParticipantCard] = {}
        self._loading_indicator: _LoadingIndicator | None = None
        self._timer_id: str | None = None
        self._timer_remaining: int = 0
        self._waiting_for_human = False
        self._current_human_participant: Participant | None = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # --- ヘッダー ---
        self._header = ctk.CTkFrame(self, height=48, corner_radius=0)
        self._header.grid(row=0, column=0, sticky="ew")
        self._header.grid_columnconfigure(1, weight=1)

        self._title_label = ctk.CTkLabel(
            self._header,
            text="テーマ: (未開始)",
            font=ctk.CTkFont(size=14, weight="bold"),
            anchor="w",
        )
        self._title_label.grid(row=0, column=0, sticky="w", padx=12, pady=8)

        self._round_label = ctk.CTkLabel(
            self._header, text="ラウンド: -/-", anchor="w"
        )
        self._round_label.grid(row=0, column=1, sticky="w", padx=12, pady=8)

        btn_frame = ctk.CTkFrame(self._header, fg_color="transparent")
        btn_frame.grid(row=0, column=2, sticky="e", padx=12, pady=8)

        self._pause_btn = ctk.CTkButton(
            btn_frame, text="一時停止", width=100, command=self._on_pause_resume
        )
        self._pause_btn.pack(side="left", padx=4)

        self._stop_btn = ctk.CTkButton(
            btn_frame,
            text="終了",
            width=80,
            fg_color="red",
            hover_color="darkred",
            command=self._on_stop,
        )
        self._stop_btn.pack(side="left", padx=4)

        # TTS トグル
        self._tts_var = ctk.BooleanVar(value=False)
        self._tts_cb = ctk.CTkCheckBox(
            btn_frame,
            text="🔊 読み上げ",
            variable=self._tts_var,
            command=self._on_tts_toggle,
            width=100,
        )
        # TTS利用可能な場合のみ表示
        tts_available = (self._app and hasattr(self._app, "tts_service")
                         and self._app.tts_service and self._app.tts_service.is_available)
        if tts_available:
            self._tts_cb.pack(side="left", padx=(12, 4))

        # --- メインエリア ---
        main_area = ctk.CTkFrame(self, fg_color="transparent")
        main_area.grid(row=1, column=0, sticky="nsew", padx=4, pady=4)
        main_area.grid_columnconfigure(0, weight=1)
        main_area.grid_rowconfigure(0, weight=1)

        # 左: チャットエリア
        self._chat_scroll = ctk.CTkScrollableFrame(main_area)
        self._chat_scroll.grid(row=0, column=0, sticky="nsew", padx=(4, 2), pady=4)
        self._chat_scroll.grid_columnconfigure(0, weight=1)
        self._chat_msg_count = 0

        # 右: サイドバー
        self._sidebar = ctk.CTkFrame(main_area, width=220)
        self._sidebar.grid(row=0, column=1, sticky="nsew", padx=(2, 4), pady=4)
        self._sidebar.grid_columnconfigure(0, weight=1)
        self._sidebar.grid_propagate(False)

        sidebar_title = ctk.CTkLabel(
            self._sidebar,
            text="参加者情報",
            font=ctk.CTkFont(size=13, weight="bold"),
        )
        sidebar_title.grid(row=0, column=0, padx=8, pady=(8, 4))

        self._cards_frame = ctk.CTkFrame(self._sidebar, fg_color="transparent")
        self._cards_frame.grid(row=1, column=0, sticky="ew", padx=4, pady=4)
        self._cards_frame.grid_columnconfigure(0, weight=1)

        # 進行情報
        self._progress_frame = ctk.CTkFrame(self._sidebar)
        self._progress_frame.grid(row=2, column=0, sticky="ew", padx=8, pady=8)
        self._progress_frame.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            self._progress_frame,
            text="進行状況",
            font=ctk.CTkFont(size=12, weight="bold"),
        ).grid(row=0, column=0, sticky="w", padx=8, pady=(6, 2))

        self._progress_bar = ctk.CTkProgressBar(self._progress_frame)
        self._progress_bar.grid(row=1, column=0, sticky="ew", padx=8, pady=2)
        self._progress_bar.set(0)

        self._remaining_label = ctk.CTkLabel(
            self._progress_frame, text="残りラウンド: -", anchor="w"
        )
        self._remaining_label.grid(row=2, column=0, sticky="w", padx=8, pady=(2, 6))

        # --- 入力エリア ---
        self._input_frame = ctk.CTkFrame(self, height=80)
        self._input_frame.grid(row=2, column=0, sticky="ew", padx=4, pady=(0, 4))
        self._input_frame.grid_columnconfigure(0, weight=1)

        input_header = ctk.CTkLabel(
            self._input_frame,
            text="あなたの発言（人間ターン時のみアクティブ）",
            font=ctk.CTkFont(size=11),
            text_color="gray",
            anchor="w",
        )
        input_header.grid(row=0, column=0, columnspan=3, sticky="w", padx=8, pady=(4, 0))

        self._input_entry = ctk.CTkEntry(
            self._input_frame, placeholder_text="発言を入力..."
        )
        self._input_entry.grid(row=1, column=0, sticky="ew", padx=(8, 4), pady=4)
        self._input_entry.configure(state="disabled")
        self._input_entry.bind("<Return>", lambda e: self._on_send())

        self._send_btn = ctk.CTkButton(
            self._input_frame, text="送信", width=80, command=self._on_send, state="disabled"
        )
        self._send_btn.grid(row=1, column=1, padx=4, pady=4)

        self._skip_btn = ctk.CTkButton(
            self._input_frame,
            text="スキップ",
            width=80,
            fg_color="gray40",
            hover_color="gray30",
            command=self._on_skip,
            state="disabled",
        )
        self._skip_btn.grid(row=1, column=2, padx=(4, 8), pady=4)

        self._timer_label = ctk.CTkLabel(
            self._input_frame, text="", text_color="gray", anchor="w"
        )
        self._timer_label.grid(row=2, column=0, columnspan=3, sticky="w", padx=8, pady=(0, 4))

    # ------------------------------------------------------------------
    # ディベート制御
    # ------------------------------------------------------------------

    def start_debate(self, debate: Debate, participants: list[Participant]) -> None:
        """ディベートを開始する（setup_viewから呼ばれる）。"""
        self._debate = debate
        self._participants = {p.id: p for p in participants}
        self._role_to_participant = {p.role: p for p in participants}

        # UI初期化
        self._title_label.configure(text=f"テーマ: {debate.topic}")
        self._update_round_display()
        self._clear_chat()
        self._build_participant_cards(participants)

        # DebateServiceのコールバック設定
        if self._app and hasattr(self._app, "debate_service") and self._app.debate_service:
            ds = self._app.debate_service
            ds.set_callbacks(
                on_message=self._cb_on_message,
                on_turn_start=self._cb_on_turn_start,
                on_debate_end=self._cb_on_debate_end,
                on_error=self._cb_on_error,
                on_waiting_human=self._cb_on_waiting_human,
            )
            ds.start_debate(debate, participants)

    def _build_participant_cards(self, participants: list[Participant]) -> None:
        """サイドバーの参加者カードを生成する。"""
        for child in self._cards_frame.winfo_children():
            child.destroy()
        self._participant_cards.clear()

        for idx, p in enumerate(participants):
            card = ParticipantCard(
                self._cards_frame,
                name=p.name,
                role=p.role.value,
                participant_type=p.type.value,
                model_name=p.llm_model,
            )
            card.grid(row=idx, column=0, sticky="ew", pady=4)
            self._participant_cards[p.id] = card

    def _clear_chat(self) -> None:
        """チャットエリアをクリアする。"""
        for child in self._chat_scroll.winfo_children():
            child.destroy()
        self._chat_msg_count = 0

    # ------------------------------------------------------------------
    # DebateService コールバック（ワーカースレッドから呼ばれる）
    # ------------------------------------------------------------------

    def _cb_on_message(self, message: Message, participant: Participant) -> None:
        """メッセージ受信コールバック。after()でUIスレッドに転送する。"""
        self.after(0, self._ui_add_message, message, participant)

    def _cb_on_turn_start(self, participant: Participant) -> None:
        """ターン開始コールバック。"""
        self.after(0, self._ui_on_turn_start, participant)

    def _cb_on_debate_end(self, debate: Debate) -> None:
        """ディベート終了コールバック。"""
        self.after(0, self._ui_on_debate_end, debate)

    def _cb_on_error(self, error_msg: str) -> None:
        """エラーコールバック。"""
        self.after(0, self._ui_on_error, error_msg)

    def _cb_on_waiting_human(self, participant: Participant) -> None:
        """人間入力待ちコールバック。"""
        self.after(0, self._ui_on_waiting_human, participant)

    # ------------------------------------------------------------------
    # UIスレッドでの更新メソッド
    # ------------------------------------------------------------------

    def _ui_add_message(self, message: Message, participant: Participant) -> None:
        """チャットエリアにメッセージを追加する。"""
        # ローディングインジケータを削除
        self._remove_loading_indicator()

        # thinkingメッセージはチャットに表示しない（履歴でのみ表示）
        if message.message_type == MessageType.THINKING:
            return

        _role_label_map = {
            ParticipantRole.PROPOSER_A: "A",
            ParticipantRole.PROPOSER_B: "B",
            ParticipantRole.JUDGE: "C",
        }
        _msg_type_map = {
            MessageType.SPEECH: "speech",
            MessageType.THINKING: "thinking",
            MessageType.SKIP: "skip",
            MessageType.JUDGMENT: "judgment",
        }
        bubble = MessageBubble(
            self._chat_scroll,
            participant_name=participant.name,
            role_label=_role_label_map.get(participant.role, "A"),
            round_number=message.round_number,
            content=message.content if message.message_type != MessageType.SKIP else "(スキップ)",
            message_type=_msg_type_map.get(message.message_type, "speech"),
        )
        bubble.grid(
            row=self._chat_msg_count, column=0, sticky="ew", padx=8, pady=4
        )
        self._chat_msg_count += 1

        # スクロールを最下部に
        self._chat_scroll.after(50, self._scroll_to_bottom)

        # ラウンド表示更新
        self._update_round_display()

        # カードのステータス更新 + 心情絵文字
        card = self._participant_cards.get(participant.id)
        if card:
            card.update_status("待機中")
            if message.message_type != MessageType.SKIP:
                from src.utils.sentiment import analyze_sentiment

                emoji = analyze_sentiment(message.content)
                card.set_emoji(emoji)

        # TTS 読み上げ（speech / judgment のみ）
        if message.message_type in (MessageType.SPEECH, MessageType.JUDGMENT):
            if self._app and hasattr(self._app, "tts_service") and self._app.tts_service:
                self._app.tts_service.speak(message.content, participant.name)

    def _ui_on_turn_start(self, participant: Participant) -> None:
        """ターン開始時のUI更新。"""
        # 全カードを待機中に
        for card in self._participant_cards.values():
            card.update_status("待機中")

        # 現在のカードを発言中に
        card = self._participant_cards.get(participant.id)
        if card:
            if participant.type == ParticipantType.LLM:
                card.update_status("発言中...")
                self._show_loading_indicator(participant.name)
            else:
                card.update_status("入力待ち")

        self._update_round_display()

    def _ui_on_waiting_human(self, participant: Participant) -> None:
        """人間入力待ちUI。入力欄をアクティブ化する。"""
        self._waiting_for_human = True
        self._current_human_participant = participant

        self._remove_loading_indicator()

        self._input_entry.configure(state="normal")
        self._input_entry.delete(0, "end")
        self._send_btn.configure(state="normal")
        self._skip_btn.configure(state="normal")

        card = self._participant_cards.get(participant.id)
        if card:
            card.update_status("入力待ち")

        # Cの場合タイマー開始
        if participant.role == ParticipantRole.JUDGE:
            timeout = 5
            # setup_viewからスキップタイムアウトを取得する方法がここでは限定的なので、
            # デフォルト値を使用する。app.settingsがあればそこから取得。
            try:
                if self._app and hasattr(self._app, "settings") and self._app.settings:
                    timeout = self._app.settings.default_c_skip_timeout_sec
            except Exception:
                pass
            self._start_timer(timeout)

    def _ui_on_debate_end(self, debate: Debate) -> None:
        """ディベート終了時のUI更新。"""
        self._debate = debate
        self._disable_input()
        self._remove_loading_indicator()

        # TTS停止
        if self._app and hasattr(self._app, "tts_service") and self._app.tts_service:
            self._app.tts_service.stop()

        for card in self._participant_cards.values():
            card.update_status("完了")

        self._pause_btn.configure(state="disabled")
        self._stop_btn.configure(state="disabled")

        self._update_round_display()

        # 終了メッセージ
        end_label = ctk.CTkLabel(
            self._chat_scroll,
            text="--- ディベート終了 ---",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="gray",
        )
        end_label.grid(
            row=self._chat_msg_count, column=0, sticky="ew", padx=8, pady=12
        )
        self._chat_msg_count += 1

        if debate.winner:
            winner_label = ctk.CTkLabel(
                self._chat_scroll,
                text=f"判定結果: {debate.winner}",
                font=ctk.CTkFont(size=14, weight="bold"),
            )
            winner_label.grid(
                row=self._chat_msg_count, column=0, sticky="ew", padx=8, pady=4
            )
            self._chat_msg_count += 1

        self._chat_scroll.after(50, self._scroll_to_bottom)

    def _ui_on_error(self, error_msg: str) -> None:
        """エラー時のUI更新。"""
        self._remove_loading_indicator()

        error_label = ctk.CTkLabel(
            self._chat_scroll,
            text=f"[エラー] {error_msg}",
            text_color="red",
            anchor="w",
            wraplength=500,
        )
        error_label.grid(
            row=self._chat_msg_count, column=0, sticky="ew", padx=8, pady=4
        )
        self._chat_msg_count += 1
        self._chat_scroll.after(50, self._scroll_to_bottom)

    # ------------------------------------------------------------------
    # ローディングインジケータ
    # ------------------------------------------------------------------

    def _show_loading_indicator(self, participant_name: str) -> None:
        self._remove_loading_indicator()
        self._loading_indicator = _LoadingIndicator(
            self._chat_scroll, participant_name=participant_name
        )
        self._loading_indicator.grid(
            row=self._chat_msg_count, column=0, sticky="ew", padx=8, pady=4
        )
        self._chat_msg_count += 1
        self._chat_scroll.after(50, self._scroll_to_bottom)

    def _remove_loading_indicator(self) -> None:
        if self._loading_indicator is not None:
            self._loading_indicator.stop()
            self._loading_indicator.destroy()
            self._loading_indicator = None
            if self._chat_msg_count > 0:
                self._chat_msg_count -= 1

    # ------------------------------------------------------------------
    # タイマー（Cの人間入力タイムアウト）
    # ------------------------------------------------------------------

    def _start_timer(self, seconds: int) -> None:
        self._cancel_timer()
        self._timer_remaining = seconds
        self._tick_timer()

    def _tick_timer(self) -> None:
        if not self._waiting_for_human:
            self._timer_label.configure(text="")
            return

        if self._timer_remaining <= 0:
            self._timer_label.configure(text="タイムアウト: スキップされます")
            self._on_skip()
            return

        self._timer_label.configure(
            text=f"タイムアウト: 残り {self._timer_remaining} 秒"
        )
        self._timer_remaining -= 1
        self._timer_id = self.after(1000, self._tick_timer)

    def _cancel_timer(self) -> None:
        if self._timer_id is not None:
            self.after_cancel(self._timer_id)
            self._timer_id = None
        self._timer_label.configure(text="")

    # ------------------------------------------------------------------
    # ユーザー操作
    # ------------------------------------------------------------------

    def _on_send(self) -> None:
        """送信ボタンまたはEnter。"""
        if not self._waiting_for_human:
            return

        text = self._input_entry.get().strip()
        if not text:
            return

        self._waiting_for_human = False
        self._cancel_timer()
        self._disable_input()

        if self._app and hasattr(self._app, "debate_service") and self._app.debate_service:
            self._app.debate_service.submit_human_input(text)

    def _on_skip(self) -> None:
        """スキップボタン。"""
        if not self._waiting_for_human:
            return

        self._waiting_for_human = False
        self._cancel_timer()
        self._disable_input()

        if self._app and hasattr(self._app, "debate_service") and self._app.debate_service:
            self._app.debate_service.submit_human_skip()

    def _on_pause_resume(self) -> None:
        """一時停止 / 再開ボタン。"""
        if not self._app or not hasattr(self._app, "debate_service") or not self._app.debate_service:
            return

        ds = self._app.debate_service
        if ds.is_paused:
            ds.resume_debate()
            self._pause_btn.configure(text="一時停止")
        else:
            ds.pause_debate()
            self._pause_btn.configure(text="再開")

    def _on_stop(self) -> None:
        """終了ボタン（確認ダイアログ付き）。"""
        from src.ui.dialogs import show_confirm

        show_confirm(
            self,
            "ディベートを終了しますか？\nこの操作は取り消せません。",
            self._do_stop,
            confirm_text="終了",
        )

    def _do_stop(self) -> None:
        """実際のディベート終了処理。"""
        if self._app and hasattr(self._app, "debate_service") and self._app.debate_service:
            self._app.debate_service.stop_debate()

    def _on_tts_toggle(self) -> None:
        """TTS読み上げチェックボックスの切替。"""
        enabled = self._tts_var.get()
        if self._app and hasattr(self._app, "tts_service") and self._app.tts_service:
            self._app.tts_service.set_enabled(enabled)

    def _disable_input(self) -> None:
        """入力欄を無効化する。"""
        self._input_entry.configure(state="disabled")
        self._send_btn.configure(state="disabled")
        self._skip_btn.configure(state="disabled")

    # ------------------------------------------------------------------
    # ユーティリティ
    # ------------------------------------------------------------------

    def _update_round_display(self) -> None:
        """ラウンド数と進行バーを更新する。"""
        if self._debate is None:
            return

        current = self._debate.current_round
        maximum = self._debate.max_rounds
        self._round_label.configure(text=f"ラウンド: {current}/{maximum}")

        progress = current / maximum if maximum > 0 else 0
        self._progress_bar.set(progress)

        remaining = maximum - current
        self._remaining_label.configure(text=f"残りラウンド: {remaining}")

    def _scroll_to_bottom(self) -> None:
        """チャットスクロールを最下部に移動する。"""
        try:
            self._chat_scroll._parent_canvas.yview_moveto(1.0)
        except Exception:
            pass

    def on_show(self) -> None:
        """ビュー表示時の処理。"""
        pass
