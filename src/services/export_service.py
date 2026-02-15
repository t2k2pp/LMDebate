"""Markdownエクスポートサービス"""

from datetime import datetime
from pathlib import Path

from src.models.debate import Debate
from src.models.participant import Participant, ParticipantRole, ParticipantType
from src.models.message import Message, MessageType


class ExportService:
    """ディベート内容をMarkdown形式でエクスポートする。"""

    def __init__(self, export_dir: str):
        self._export_dir = Path(export_dir)
        self._export_dir.mkdir(parents=True, exist_ok=True)

    def export_debate(
        self,
        debate: Debate,
        participants: list[Participant],
        messages: list[Message],
        include_thinking: bool = True,
    ) -> Path:
        """ディベート全体をMarkdownファイルにエクスポートする。"""
        md = self._build_markdown(debate, participants, messages, include_thinking)

        # ファイル名生成
        safe_title = "".join(c if c.isalnum() or c in "_ -" else "_" for c in debate.title)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{safe_title}_{timestamp}.md"
        filepath = self._export_dir / filename

        filepath.write_text(md, encoding="utf-8")
        return filepath

    def _build_markdown(
        self,
        debate: Debate,
        participants: list[Participant],
        messages: list[Message],
        include_thinking: bool,
    ) -> str:
        lines = []

        # ヘッダー
        lines.append(f"# ディベート: {debate.title}")
        lines.append("")
        lines.append(f"- **日時**: {debate.created_at.strftime('%Y-%m-%d %H:%M')}")
        lines.append(f"- **テーマ**: {debate.topic}")
        lines.append(f"- **案X**: {debate.proposal_x}")
        lines.append(f"- **案Y**: {debate.proposal_y}")
        if debate.judge_instruction:
            lines.append(f"- **判定の観点**: {debate.judge_instruction}")
        lines.append("")

        # 参加者テーブル
        lines.append("## 参加者")
        lines.append("")
        lines.append("| 役割 | 名前 | タイプ | モデル |")
        lines.append("|---|---|---|---|")

        participant_map = {}
        for p in participants:
            participant_map[p.id] = p
            role_label = self._role_display(p.role)
            type_label = "LLM" if p.type == ParticipantType.LLM else "人間"
            model_label = p.llm_model or "-"
            lines.append(f"| {role_label} | {p.name} | {type_label} | {model_label} |")
        lines.append("")

        # ディベート内容
        lines.append("## ディベート内容")
        lines.append("")

        # ラウンドごとにグループ化
        rounds: dict[int, list[Message]] = {}
        for msg in messages:
            if msg.round_number not in rounds:
                rounds[msg.round_number] = []
            rounds[msg.round_number].append(msg)

        for round_num in sorted(rounds.keys()):
            lines.append(f"### ラウンド {round_num}")
            lines.append("")

            round_msgs = rounds[round_num]

            # 参加者ごとにまとめる
            current_participant = None
            thinking_text = None
            speech_text = None

            for msg in round_msgs:
                p = participant_map.get(msg.participant_id)
                if p is None:
                    continue

                if msg.participant_id != current_participant:
                    # 前の参加者の内容を出力
                    if current_participant is not None:
                        self._flush_participant_block(
                            lines, participant_map.get(current_participant),
                            thinking_text, speech_text, include_thinking,
                        )
                    current_participant = msg.participant_id
                    thinking_text = None
                    speech_text = None

                if msg.message_type == MessageType.THINKING:
                    thinking_text = msg.content
                elif msg.message_type == MessageType.SPEECH:
                    speech_text = msg.content
                elif msg.message_type == MessageType.SKIP:
                    speech_text = "(スキップ)"
                elif msg.message_type == MessageType.JUDGMENT:
                    speech_text = msg.content

            # 最後の参加者の内容を出力
            if current_participant is not None:
                self._flush_participant_block(
                    lines, participant_map.get(current_participant),
                    thinking_text, speech_text, include_thinking,
                )

        # 最終判定
        judgment_msgs = [
            m for m in messages if m.message_type == MessageType.JUDGMENT
        ]
        if judgment_msgs or debate.winner:
            lines.append("## 最終判定")
            lines.append("")
            if debate.winner:
                lines.append(f"**結果**: {debate.winner}")
            for jm in judgment_msgs:
                lines.append(f"\n{jm.content}")
            lines.append("")

        lines.append("---")
        lines.append("*LMDebate により生成*")

        return "\n".join(lines)

    def _flush_participant_block(
        self,
        lines: list[str],
        participant: Participant | None,
        thinking: str | None,
        speech: str | None,
        include_thinking: bool,
    ):
        if participant is None:
            return

        name = participant.name
        role_label = self._role_short(participant.role)
        lines.append(f"#### {role_label} ({name})")

        if include_thinking and thinking:
            lines.append(f"> **思考**: {thinking}")
            lines.append(">")

        if speech:
            if speech == "(スキップ)":
                lines.append(f"*スキップ*")
            else:
                lines.append(f"> **発言**: {speech}")
        lines.append("")

    def _role_display(self, role: ParticipantRole) -> str:
        if role == ParticipantRole.PROPOSER_A:
            return "A（案X推進）"
        elif role == ParticipantRole.PROPOSER_B:
            return "B（案Y推進）"
        return "C（判定者）"

    def _role_short(self, role: ParticipantRole) -> str:
        if role == ParticipantRole.PROPOSER_A:
            return "A"
        elif role == ParticipantRole.PROPOSER_B:
            return "B"
        return "C"
