"""ディベート進行管理サービス"""

import asyncio
import re
import threading
from datetime import datetime
from typing import Callable

from src.models.debate import Debate, DebateStatus
from src.models.participant import Participant, ParticipantRole, ParticipantType
from src.models.message import Message, MessageType
from src.models.attachment import Attachment
from src.utils.prompt_builder import (
    build_system_prompt,
    build_conversation_history,
    parse_llm_response,
)
from src.utils.token_counter import count_tokens


class DebateService:
    """ディベートの進行を管理するサービス。

    LLM APIの呼び出しはワーカースレッドで実行し、
    結果はコールバックでUIスレッドに返す。
    """

    # ターン順序
    TURN_ORDER = [
        ParticipantRole.PROPOSER_A,
        ParticipantRole.PROPOSER_B,
        ParticipantRole.JUDGE,
    ]

    def __init__(self, history_service, llm_service, preset_service, attachment_service):
        self._history = history_service
        self._llm = llm_service
        self._preset = preset_service
        self._attachment = attachment_service

        self._debate: Debate | None = None
        self._participants: dict[str, Participant] = {}
        self._role_to_participant: dict[ParticipantRole, Participant] = {}
        self._messages: list[Message] = []
        self._attachments: dict[str, list[Attachment]] = {}  # role.value -> [Attachment]

        self._running = False
        self._paused = False
        self._worker_thread: threading.Thread | None = None

        # UIコールバック
        self._on_message: Callable[[Message, Participant], None] | None = None
        self._on_turn_start: Callable[[Participant], None] | None = None
        self._on_debate_end: Callable[[Debate], None] | None = None
        self._on_error: Callable[[str], None] | None = None
        self._on_waiting_human: Callable[[Participant], None] | None = None

        # 人間入力用
        self._human_input_event = threading.Event()
        self._human_input_text: str | None = None
        self._human_skipped = False

    def set_callbacks(
        self,
        on_message: Callable | None = None,
        on_turn_start: Callable | None = None,
        on_debate_end: Callable | None = None,
        on_error: Callable | None = None,
        on_waiting_human: Callable | None = None,
    ):
        """UIコールバックを設定する。"""
        self._on_message = on_message
        self._on_turn_start = on_turn_start
        self._on_debate_end = on_debate_end
        self._on_error = on_error
        self._on_waiting_human = on_waiting_human

    def start_debate(self, debate: Debate, participants: list[Participant]):
        """ディベートを開始する。"""
        self._debate = debate
        self._participants = {p.id: p for p in participants}
        self._role_to_participant = {p.role: p for p in participants}
        self._messages = []

        # 添付ファイルの読み込み
        for p in participants:
            atts = self._history.get_attachments(debate.id, p.role.value)
            self._attachments[p.role.value] = atts

        # DB保存
        debate.status = DebateStatus.RUNNING
        self._history.update_debate(debate)

        self._running = True
        self._paused = False

        # ワーカースレッドで進行
        self._worker_thread = threading.Thread(target=self._run_debate_loop, daemon=True)
        self._worker_thread.start()

    def pause_debate(self):
        """ディベートを一時停止する。"""
        self._paused = True
        if self._debate:
            self._debate.status = DebateStatus.PAUSED
            self._history.update_debate(self._debate)

    def resume_debate(self):
        """ディベートを再開する。"""
        self._paused = False
        if self._debate:
            self._debate.status = DebateStatus.RUNNING
            self._history.update_debate(self._debate)

    def stop_debate(self):
        """ディベートを強制終了する。"""
        self._running = False
        self._human_input_event.set()  # 人間入力待ちを解除
        if self._debate:
            self._debate.status = DebateStatus.COMPLETED
            self._debate.completed_at = datetime.now()
            self._history.update_debate(self._debate)

    def submit_human_input(self, text: str):
        """人間の入力を送信する。"""
        self._human_input_text = text
        self._human_skipped = False
        self._human_input_event.set()

    def submit_human_skip(self):
        """人間がスキップする。"""
        self._human_input_text = None
        self._human_skipped = True
        self._human_input_event.set()

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def is_paused(self) -> bool:
        return self._paused

    @property
    def current_debate(self) -> Debate | None:
        return self._debate

    def _run_debate_loop(self):
        """ディベートのメインループ（ワーカースレッドで実行）。"""
        debate = self._debate
        if debate is None:
            return

        try:
            while self._running and debate.current_round < debate.max_rounds:
                # 一時停止チェック
                while self._paused and self._running:
                    threading.Event().wait(0.5)

                if not self._running:
                    break

                debate.current_round += 1
                self._history.update_debate(debate)

                # 各ターンを実行
                for role in self.TURN_ORDER:
                    if not self._running:
                        break

                    participant = self._role_to_participant.get(role)
                    if participant is None:
                        continue

                    # 一時停止チェック
                    while self._paused and self._running:
                        threading.Event().wait(0.5)

                    if not self._running:
                        break

                    if self._on_turn_start:
                        self._on_turn_start(participant)

                    if participant.type == ParticipantType.LLM:
                        self._execute_llm_turn(participant)
                    else:
                        self._execute_human_turn(participant)

                    if not self._running:
                        break

                    # Cが判定を下したかチェック
                    if self._check_judgment():
                        self._running = False
                        break

            # ディベート終了
            if self._running and debate.current_round >= debate.max_rounds:
                # 最大ラウンド到達: Cに最終判定を求める
                judge = self._role_to_participant.get(ParticipantRole.JUDGE)
                if judge and judge.type == ParticipantType.LLM:
                    self._request_final_judgment(judge)

            debate.status = DebateStatus.COMPLETED
            debate.completed_at = datetime.now()
            self._history.update_debate(debate)
            self._running = False

            if self._on_debate_end:
                self._on_debate_end(debate)

        except Exception as e:
            self._running = False
            if self._on_error:
                self._on_error(str(e))

    def _execute_llm_turn(self, participant: Participant):
        """LLMの発言ターンを実行する。"""
        debate = self._debate
        if debate is None:
            return

        # プリセット取得
        preset = None
        if participant.preset_id:
            preset = self._preset.get_preset(participant.preset_id)

        # 添付ファイル
        attachments = self._attachments.get(participant.role.value, [])

        # システムプロンプト構築
        system_prompt = build_system_prompt(
            participant=participant,
            topic=debate.topic,
            proposal_x=debate.proposal_x,
            proposal_y=debate.proposal_y,
            judge_instruction=debate.judge_instruction,
            preset=preset,
            attachments=attachments,
        )

        # 会話履歴構築
        history = build_conversation_history(
            messages=self._messages,
            participants=self._participants,
            current_participant_id=participant.id,
            include_own_thinking=participant.include_own_thinking,
        )

        # LLM API呼び出し（同期的にasyncを実行）
        try:
            loop = asyncio.new_event_loop()
            response = loop.run_until_complete(
                self._llm.generate(
                    provider_id=participant.llm_provider,
                    system_prompt=system_prompt,
                    messages=history,
                    max_tokens=participant.max_tokens_per_turn,
                )
            )
            loop.close()
        except Exception as e:
            if self._on_error:
                self._on_error(f"LLMエラー ({participant.name}): {e}")
            return

        # レスポンスパース
        thinking, speech = parse_llm_response(response.content)

        # メッセージ保存
        if thinking:
            thinking_msg = Message(
                debate_id=debate.id,
                participant_id=participant.id,
                round_number=debate.current_round,
                message_type=MessageType.THINKING,
                content=thinking,
                token_count=count_tokens(thinking),
            )
            self._history.save_message(thinking_msg)
            self._messages.append(thinking_msg)

        # スキップ判定
        if speech.upper() == "SKIP":
            skip_msg = Message(
                debate_id=debate.id,
                participant_id=participant.id,
                round_number=debate.current_round,
                message_type=MessageType.SKIP,
                content="",
                token_count=0,
            )
            self._history.save_message(skip_msg)
            self._messages.append(skip_msg)
            if self._on_message:
                self._on_message(skip_msg, participant)
        elif "【判定】" in speech:
            judgment_msg = Message(
                debate_id=debate.id,
                participant_id=participant.id,
                round_number=debate.current_round,
                message_type=MessageType.JUDGMENT,
                content=speech,
                token_count=count_tokens(speech),
            )
            self._history.save_message(judgment_msg)
            self._messages.append(judgment_msg)
            if self._on_message:
                self._on_message(judgment_msg, participant)
        else:
            speech_msg = Message(
                debate_id=debate.id,
                participant_id=participant.id,
                round_number=debate.current_round,
                message_type=MessageType.SPEECH,
                content=speech,
                token_count=count_tokens(speech),
            )
            self._history.save_message(speech_msg)
            self._messages.append(speech_msg)
            if self._on_message:
                self._on_message(speech_msg, participant)

    def _execute_human_turn(self, participant: Participant):
        """人間の発言ターンを実行する。"""
        debate = self._debate
        if debate is None:
            return

        self._human_input_event.clear()
        self._human_input_text = None
        self._human_skipped = False

        if self._on_waiting_human:
            self._on_waiting_human(participant)

        # 入力待ち（無制限）
        self._human_input_event.wait()

        if not self._running:
            return

        if self._human_skipped or self._human_input_text is None:
            skip_msg = Message(
                debate_id=debate.id,
                participant_id=participant.id,
                round_number=debate.current_round,
                message_type=MessageType.SKIP,
                content="",
                token_count=0,
            )
            self._history.save_message(skip_msg)
            self._messages.append(skip_msg)
            if self._on_message:
                self._on_message(skip_msg, participant)
        else:
            text = self._human_input_text.strip()
            # 判定かどうか
            if "【判定】" in text:
                msg_type = MessageType.JUDGMENT
            else:
                msg_type = MessageType.SPEECH

            msg = Message(
                debate_id=debate.id,
                participant_id=participant.id,
                round_number=debate.current_round,
                message_type=msg_type,
                content=text,
                token_count=count_tokens(text),
            )
            self._history.save_message(msg)
            self._messages.append(msg)
            if self._on_message:
                self._on_message(msg, participant)

    def _check_judgment(self) -> bool:
        """Cが判定を下したかチェックする。"""
        for msg in reversed(self._messages):
            if msg.message_type == MessageType.JUDGMENT:
                # 判定結果を解析
                if "Aの" in msg.content or "案Xを支持" in msg.content:
                    self._debate.winner = "A"
                elif "Bの" in msg.content or "案Yを支持" in msg.content:
                    self._debate.winner = "B"
                else:
                    self._debate.winner = "undecided"
                return True
        return False

    def _request_final_judgment(self, judge: Participant):
        """最大ラウンド到達時にCに最終判定を求める。"""
        if self._on_turn_start:
            self._on_turn_start(judge)

        # 強制判定プロンプトを追加して実行
        self._execute_llm_turn(judge)
