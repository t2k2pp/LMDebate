"""ディベート進行管理サービス"""

from __future__ import annotations

import asyncio
import logging
import re
import threading
from datetime import datetime
from typing import Callable, TYPE_CHECKING

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

if TYPE_CHECKING:
    from src.services.search_service import SearchService

logger = logging.getLogger(__name__)


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

    def __init__(self, history_service, llm_service, preset_service, attachment_service,
                 search_service: SearchService | None = None):
        self._history = history_service
        self._llm = llm_service
        self._preset = preset_service
        self._attachment = attachment_service
        self._search = search_service

        self._debate: Debate | None = None
        self._participants: dict[str, Participant] = {}
        self._role_to_participant: dict[ParticipantRole, Participant] = {}
        self._messages: list[Message] = []
        self._attachments: dict[str, list[Attachment]] = {}  # role.value -> [Attachment]

        self._running = False
        self._paused = False
        self._worker_thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None

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

        # ワーカースレッド専用のevent loopを作成・維持する
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

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
        finally:
            # ワーカースレッド専用loopをクリーンアップ
            try:
                self._loop.close()
            except Exception:
                pass
            self._loop = None

    def _generate_search_query(self, participant: Participant, debate: Debate) -> str:
        """LLMに検索クエリを生成させる。"""
        query_prompt = (
            "あなたはディベートの参加者です。\n"
            f"議論テーマ: {debate.topic}\n"
            "これから発言するために、ウェブ検索で裏付けとなる情報を探したいです。\n"
            "最も効果的な検索クエリを1つだけ、簡潔に（日本語または英語で）出力してください。\n"
            "検索クエリのみを出力し、他の文章は不要です。"
        )
        # 最近の会話の要約を含める
        recent_messages = self._messages[-6:] if self._messages else []
        context_parts = []
        for msg in recent_messages:
            p = self._participants.get(msg.participant_id)
            if p and msg.message_type in (MessageType.SPEECH, MessageType.JUDGMENT):
                label = "A" if p.role == ParticipantRole.PROPOSER_A else (
                    "B" if p.role == ParticipantRole.PROPOSER_B else "C"
                )
                context_parts.append(f"{label}: {msg.content[:200]}")

        if context_parts:
            query_prompt += "\n\n最近の議論:\n" + "\n".join(context_parts)

        try:
            response = self._loop.run_until_complete(
                self._llm.generate(
                    provider_id=participant.llm_provider,
                    system_prompt=query_prompt,
                    messages=[],
                    max_tokens=50,
                    temperature=0.3,
                )
            )
            query = response.content.strip().strip('"').strip("'")
            logger.info("検索クエリ生成: participant=%s, query=%r", participant.name, query)
            return query
        except Exception as e:
            logger.warning("検索クエリ生成に失敗: %s", e)
            # フォールバック: テーマをそのままクエリに使用
            return debate.topic

    def _execute_llm_turn(self, participant: Participant, force_judgment: bool = False):
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

        # Web検索（有効な場合）
        search_results = None
        if (participant.enable_web_search
                and self._search is not None
                and self._search.is_configured):
            try:
                query = self._generate_search_query(participant, debate)
                search_results = self._search.search(
                    query=query,
                    max_results=participant.max_search_count,
                )
                if search_results:
                    logger.info(
                        "Web検索完了: participant=%s, 結果=%d件",
                        participant.name, len(search_results),
                    )
            except Exception as e:
                logger.warning("Web検索に失敗しました: %s", e)

        # システムプロンプト構築
        system_prompt = build_system_prompt(
            participant=participant,
            topic=debate.topic,
            proposal_x=debate.proposal_x,
            proposal_y=debate.proposal_y,
            judge_instruction=debate.judge_instruction,
            preset=preset,
            attachments=attachments,
            search_results=search_results,
            current_round=debate.current_round,
            max_rounds=debate.max_rounds,
        )

        # 最終判定強制モード: システムプロンプトに判定強制指示を追加
        if force_judgment:
            system_prompt += (
                "\n\n"
                "【重要：最終判定指示】\n"
                "最終ラウンドに到達しました。あなたは今すぐ最終判定を下さなければなりません。\n"
                "SKIPは絶対に許可されません。必ず以下の形式で判定を下してください：\n"
                "<speech>\n"
                "【判定】案X（A）または案Y（B）を支持します。\n"
                "【理由】これまでの議論を踏まえた判定理由を述べてください。\n"
                "</speech>"
            )

        # 会話履歴構築
        history = build_conversation_history(
            messages=self._messages,
            participants=self._participants,
            current_participant_id=participant.id,
            include_own_thinking=participant.include_own_thinking,
        )

        # LLM API呼び出し（ワーカースレッド専用event loopで実行、リトライ付き）
        # max_tokens_per_turn は発言(speech)の目安であり、thinking含む全出力の制限ではない
        # APIには十分大きな値を渡し、プロンプト側で発言量を指示する
        api_max_tokens = max(participant.max_tokens_per_turn * 4, 4096)
        max_retries = 3
        response = None
        for attempt in range(max_retries):
            try:
                response = self._loop.run_until_complete(
                    self._llm.generate(
                        provider_id=participant.llm_provider,
                        system_prompt=system_prompt,
                        messages=history,
                        max_tokens=api_max_tokens,
                    )
                )
                break
            except Exception as e:
                logger.warning(
                    "LLM API呼び出し失敗 (試行%d/%d, %s): %s",
                    attempt + 1, max_retries, participant.name, e,
                )
                if attempt < max_retries - 1:
                    import time
                    wait_sec = 2 ** attempt  # 1s, 2s
                    logger.info("リトライまで%d秒待機...", wait_sec)
                    time.sleep(wait_sec)
                else:
                    if self._on_error:
                        self._on_error(
                            f"LLMエラー ({participant.name}): {max_retries}回試行後も失敗 - {e}"
                        )
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

        # 審判が最終ラウンド以前に勝手に判定を出した場合はSKIP扱いにする
        is_premature_judgment = (
            "【判定】" in speech
            and participant.role == ParticipantRole.JUDGE
            and not force_judgment
            and debate.current_round < debate.max_rounds
        )
        if is_premature_judgment:
            logger.warning(
                "審判が最終ラウンド前に判定を出そうとしました（ラウンド%d/%d）。SKIP扱いにします。",
                debate.current_round, debate.max_rounds,
            )
            speech = "SKIP"

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
                # 判定結果を解析（多様なパターンに対応）
                content = msg.content
                # A勝利パターン: 案X, A, 案X（A）, 案X(A) 等
                a_patterns = [
                    r"案\s*X.*支持", r"案\s*X.*勝", r"Aの.*(?:勝|支持|優)",
                    r"(?:A|Ａ)\s*を支持", r"(?:A|Ａ)\s*の(?:勝|案|主張)",
                    r"案\s*X\s*[（(]\s*A\s*[）)]",
                    r"討論者\s*A", r"参加者\s*A.*支持",
                ]
                # B勝利パターン: 案Y, B, 案Y（B）, 案Y(B) 等
                b_patterns = [
                    r"案\s*Y.*支持", r"案\s*Y.*勝", r"Bの.*(?:勝|支持|優)",
                    r"(?:B|Ｂ)\s*を支持", r"(?:B|Ｂ)\s*の(?:勝|案|主張)",
                    r"案\s*Y\s*[（(]\s*B\s*[）)]",
                    r"討論者\s*B", r"参加者\s*B.*支持",
                ]

                is_a = any(re.search(p, content) for p in a_patterns)
                is_b = any(re.search(p, content) for p in b_patterns)

                if is_a and not is_b:
                    self._debate.winner = "A（案X）"
                elif is_b and not is_a:
                    self._debate.winner = "B（案Y）"
                elif is_a and is_b:
                    # 両方マッチした場合は「【判定】」直後のテキストで判断
                    judgment_section = re.search(r"【判定】(.{0,50})", content)
                    if judgment_section:
                        j_text = judgment_section.group(1)
                        if re.search(r"[AＡ]|案\s*X", j_text):
                            self._debate.winner = "A（案X）"
                        elif re.search(r"[BＢ]|案\s*Y", j_text):
                            self._debate.winner = "B（案Y）"
                        else:
                            self._debate.winner = "判定済み（詳細は判定文を参照）"
                    else:
                        self._debate.winner = "判定済み（詳細は判定文を参照）"
                else:
                    self._debate.winner = "判定済み（詳細は判定文を参照）"
                return True
        return False

    def _request_final_judgment(self, judge: Participant):
        """最大ラウンド到達時にCに最終判定を求める。"""
        if self._on_turn_start:
            self._on_turn_start(judge)

        # 最終判定を促すシステムメッセージを会話に追加
        final_prompt_msg = Message(
            debate_id=self._debate.id,
            participant_id="system",
            round_number=self._debate.current_round,
            message_type=MessageType.SPEECH,
            content="【システム】最終ラウンドに到達しました。判定者Cは最終判定を下してください。"
                    "「【判定】」と「【理由】」を含む発言で、どちらの案を支持するか明確に述べてください。"
                    "SKIPは許可されません。",
            token_count=0,
        )
        self._messages.append(final_prompt_msg)

        # 強制判定モードでLLMターン実行（SKIPを無効化）
        self._execute_llm_turn(judge, force_judgment=True)

        # 判定が出なかった場合はリトライ（最大2回）
        for retry in range(2):
            if self._check_judgment():
                return  # 判定済み
            # まだSKIPされた場合、もう一度強制
            logger.warning("最終判定がスキップされました。リトライ %d/2", retry + 1)
            retry_msg = Message(
                debate_id=self._debate.id,
                participant_id="system",
                round_number=self._debate.current_round,
                message_type=MessageType.SPEECH,
                content="【システム】判定が下されていません。SKIPは無効です。"
                        "必ず「【判定】」を含む発言で最終判定を下してください。",
                token_count=0,
            )
            self._messages.append(retry_msg)
            self._execute_llm_turn(judge, force_judgment=True)
