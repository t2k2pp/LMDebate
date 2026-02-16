"""LLMプロンプト構築ユーティリティ"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from src.models.participant import Participant, ParticipantRole
from src.models.message import Message, MessageType
from src.models.role_preset import RolePreset
from src.models.attachment import Attachment

if TYPE_CHECKING:
    from src.services.search_service import SearchResult


def build_system_prompt(
    participant: Participant,
    topic: str,
    proposal_x: str,
    proposal_y: str,
    judge_instruction: str,
    preset: RolePreset | None,
    attachments: list[Attachment],
    search_results: list[SearchResult] | None = None,
) -> str:
    """参加者の役割に応じたシステムプロンプトを構築する。"""

    # 性格・行動指針（プリセット or カスタム）
    personality = ""
    guidelines = ""
    if preset:
        personality = preset.personality
        guidelines = preset.guidelines
    else:
        personality = participant.custom_personality or ""
        guidelines = participant.custom_guidelines or ""

    if participant.role == ParticipantRole.PROPOSER_A:
        return _build_proposer_prompt(
            role_label="A",
            proposal_label="案X",
            own_proposal=proposal_x,
            opponent_label="案Y",
            opponent_proposal=proposal_y,
            topic=topic,
            personality=personality,
            guidelines=guidelines,
            attachments=attachments,
            max_tokens=participant.max_tokens_per_turn,
            search_results=search_results,
        )
    elif participant.role == ParticipantRole.PROPOSER_B:
        return _build_proposer_prompt(
            role_label="B",
            proposal_label="案Y",
            own_proposal=proposal_y,
            opponent_label="案X",
            opponent_proposal=proposal_x,
            topic=topic,
            personality=personality,
            guidelines=guidelines,
            attachments=attachments,
            max_tokens=participant.max_tokens_per_turn,
            search_results=search_results,
        )
    else:  # JUDGE
        return _build_judge_prompt(
            topic=topic,
            proposal_x=proposal_x,
            proposal_y=proposal_y,
            judge_instruction=judge_instruction,
            personality=personality,
            guidelines=guidelines,
            attachments=attachments,
            max_tokens=participant.max_tokens_per_turn,
            search_results=search_results,
        )


def _build_proposer_prompt(
    role_label: str,
    proposal_label: str,
    own_proposal: str,
    opponent_label: str,
    opponent_proposal: str,
    topic: str,
    personality: str,
    guidelines: str,
    attachments: list[Attachment],
    max_tokens: int,
    search_results: list[SearchResult] | None = None,
) -> str:
    lines = [
        f"あなたは公式ディベートの討論者{role_label}です。「{proposal_label}」を支持する立場として参加しています。",
        "",
        "【ディベートのルール】",
        "- これは正式なディベート（討論）です。雑談や日常会話ではありません。",
        "- あなたの唯一の目的は、判定者Cを説得して自分の案が優れていると認めさせることです。",
        "- 相手（対立側）の主張に対して、論理的に反論してください。",
        "- 具体的な根拠、データ、事例を挙げて自分の主張を裏付けてください。",
        "- 相手の論点の弱点を指摘し、自分の主張の優位性を明確に示してください。",
        "- 感情的にならず、論理的かつ説得力のある議論を展開してください。",
        "- 相手の発言を無視せず、必ず反論または応答してから自分の主張を展開してください。",
    ]

    if personality:
        lines.append(f"\n【あなたの性格】{personality}")
    if guidelines:
        lines.append(f"【あなたの行動指針】{guidelines}")

    lines.append(f"\n【議論テーマ】{topic}")
    lines.append(f"\n【あなたの主張（{proposal_label}）】\n{own_proposal}")

    # 添付資料
    attachment_text = _build_attachment_text(attachments)
    if attachment_text:
        lines.append(f"\n--- 参考資料（あなたの主張の根拠）---\n{attachment_text}\n--- 参考資料ここまで ---")

    # ウェブ検索結果
    search_text = _build_search_results_text(search_results)
    if search_text:
        lines.append(f"\n--- ウェブ検索結果 ---\n{search_text}\n--- ウェブ検索結果ここまで ---")

    lines.append(f"\n【対立する主張（{opponent_label}）】{opponent_proposal}")

    lines.append(
        f"\n【発言の指針】"
    )
    if search_results:
        lines.append("- ウェブ検索結果を活用し、具体的な根拠やデータを引用して議論を強化してください。")
    lines.append(f"- <speech>内の発言は{max_tokens}トークン程度に収めてください。")
    lines.append("- <thinking>内では自由に思考を整理してください（長さ制限なし）。")

    lines.append("\n必ず日本語で回答してください。")

    lines.append(
        "\n以下の形式で回答してください:\n"
        "<thinking>\n"
        "（ここで相手の発言を分析し、反論のポイントを整理し、自分の主張を組み立てる）\n"
        "</thinking>\n"
        "<speech>\n"
        "（ここにディベートの発言を記述。相手への反論と自分の主張を論理的に展開する）\n"
        "</speech>"
    )

    return "\n".join(lines)


def _build_judge_prompt(
    topic: str,
    proposal_x: str,
    proposal_y: str,
    judge_instruction: str,
    personality: str,
    guidelines: str,
    attachments: list[Attachment],
    max_tokens: int,
    search_results: list[SearchResult] | None = None,
) -> str:
    lines = [
        "あなたは公式ディベートの判定者（審判）Cです。",
        "",
        "【審判としてのルール】",
        "- これは正式なディベート（討論）です。あなたは審判であり、討論者ではありません。",
        "- 審判は基本的に発言しません。討論者AとBの議論を黙って聞いてください。",
        "- 通常のラウンドでは「SKIP」してください。これがデフォルトの行動です。",
        "- 以下の場合のみ発言が許可されます：",
        "  1. 議論のルール違反があった場合（人身攻撃、論点のすり替え等）",
        "  2. 議論の方向性が完全にテーマから外れた場合",
        "  3. 最終判定を下す場合",
        "- 質問や意見を述べる必要はありません。判定に必要な情報は討論者の発言から得てください。",
        "- 十分に議論が尽くされたと判断したら、最終判定を下してください。",
    ]

    if personality:
        lines.append(f"\n【あなたの性格】{personality}")
    if guidelines:
        lines.append(f"【あなたの行動指針】{guidelines}")

    lines.append(f"\n【議論テーマ】{topic}")
    lines.append(f"【案X（Aの主張）】{proposal_x}")
    lines.append(f"【案Y（Bの主張）】{proposal_y}")

    if judge_instruction:
        lines.append(f"\n【判定の観点・指示】\n{judge_instruction}")

    attachment_text = _build_attachment_text(attachments)
    if attachment_text:
        lines.append(f"\n--- 参考資料 ---\n{attachment_text}\n--- 参考資料ここまで ---")

    # ウェブ検索結果
    search_text = _build_search_results_text(search_results)
    if search_text:
        lines.append(f"\n--- ウェブ検索結果 ---\n{search_text}\n--- ウェブ検索結果ここまで ---")

    lines.append(
        "\n【回答方法】"
        "\n■ 通常（デフォルト）: 発言せずスキップ"
        '\n  → "<speech>SKIP</speech>" と回答してください。ほとんどのラウンドではこれが正しい行動です。'
        "\n"
        "\n■ ルール違反や脱線への指摘が必要な場合のみ:"
        f"\n  → <speech>内に短い指摘を記述（{max_tokens}トークン以内）"
        "\n"
        "\n■ 最終判定を下す場合:"
        "\n  → 以下の形式で回答してください:"
        "\n  <speech>"
        "\n  【判定】案X（A）または案Y（B）を支持します。"
        "\n  【理由】判定理由を論理的に説明"
        "\n  </speech>"
    )

    lines.append("\n必ず日本語で回答してください。")

    lines.append(
        "\n以下の形式で回答してください:\n"
        "<thinking>\n"
        "（ここで両者の議論を分析し、それぞれの論点の強弱を評価する。判定を下すべきか検討する）\n"
        "</thinking>\n"
        "<speech>\n"
        "SKIP\n"
        "（通常はSKIPです。指摘や最終判定が必要な場合のみ発言内容を記述）\n"
        "</speech>"
    )

    return "\n".join(lines)


def _build_attachment_text(attachments: list[Attachment]) -> str:
    """添付ファイルの抽出テキストを結合する。"""
    texts = []
    for att in attachments:
        if att.extracted_text:
            texts.append(f"[{att.original_filename}]\n{att.extracted_text}")
        else:
            texts.append(f"[{att.original_filename}] (テキスト抽出不可)")
    return "\n\n".join(texts)


def _build_search_results_text(search_results: list[SearchResult] | None) -> str:
    """検索結果をプロンプト用テキストに変換する。"""
    if not search_results:
        return ""
    texts = []
    for i, result in enumerate(search_results, 1):
        parts = [f"[{i}] {result.title}"]
        if result.url:
            parts.append(f"    URL: {result.url}")
        if result.content:
            parts.append(f"    {result.content}")
        texts.append("\n".join(parts))
    return "\n\n".join(texts)


def build_conversation_history(
    messages: list[Message],
    participants: dict[str, Participant],
    current_participant_id: str,
    include_own_thinking: bool,
) -> list[dict]:
    """会話履歴をLLM API用のメッセージリストに変換する。

    - 全参加者のspeechを含む
    - 他者のthinkingは含めない
    - 自身のthinkingはinclude_own_thinkingに依存
    """
    history = []

    for msg in messages:
        participant = participants.get(msg.participant_id)
        if participant is None:
            continue

        role_label = _get_role_label(participant.role)

        if msg.message_type == MessageType.SPEECH:
            history.append({
                "role": "assistant" if msg.participant_id == current_participant_id else "user",
                "content": f"{role_label}: {msg.content}",
            })
        elif msg.message_type == MessageType.THINKING:
            # 自身の思考のみ、設定に応じて含める
            if msg.participant_id == current_participant_id and include_own_thinking:
                history.append({
                    "role": "assistant",
                    "content": f"[あなたの過去の思考] {msg.content}",
                })
        elif msg.message_type == MessageType.SKIP:
            history.append({
                "role": "user",
                "content": f"{role_label}: (スキップ)",
            })
        elif msg.message_type == MessageType.JUDGMENT:
            history.append({
                "role": "user",
                "content": f"{role_label} (判定): {msg.content}",
            })

    return history


def _get_role_label(role: ParticipantRole) -> str:
    if role == ParticipantRole.PROPOSER_A:
        return "A"
    elif role == ParticipantRole.PROPOSER_B:
        return "B"
    else:
        return "C"


def parse_llm_response(response: str) -> tuple[str, str]:
    """LLMレスポンスからthinkingとspeechを分離する。

    Returns:
        (thinking, speech) のタプル
    """
    thinking_match = re.search(r"<thinking>(.*?)</thinking>", response, re.DOTALL)
    speech_match = re.search(r"<speech>(.*?)</speech>", response, re.DOTALL)

    thinking = thinking_match.group(1).strip() if thinking_match else ""

    if speech_match:
        speech = speech_match.group(1).strip()
    else:
        # <speech>タグがない場合: <thinking>タグ部分を除去してから残りをspeechとする
        fallback = response
        fallback = re.sub(r"<thinking>.*?</thinking>", "", fallback, flags=re.DOTALL)
        speech = fallback.strip()

    # speechから残っている可能性のあるタグを除去
    speech = re.sub(r"</?(?:thinking|speech)>", "", speech).strip()

    return thinking, speech
