"""Markdownテキストの簡易パース・表示ユーティリティ

CustomTkinterのCTkTextboxにMarkdown的なリッチテキスト表示を行うための
シンプルなパーサー。対応するMarkdown記法:
  - **太字** / __太字__
  - *斜体* / _斜体_
  - - 箇条書き / * 箇条書き
  - 1. 番号付きリスト
  - ## 見出し
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, auto


class SpanStyle(Enum):
    """テキストスパンのスタイル種別。"""
    NORMAL = auto()
    BOLD = auto()
    ITALIC = auto()
    HEADING = auto()


@dataclass
class TextSpan:
    """スタイル付きテキストの断片。"""
    text: str
    style: SpanStyle = SpanStyle.NORMAL


@dataclass
class ParsedLine:
    """パースされた1行分のデータ。"""
    spans: list[TextSpan] = field(default_factory=list)
    indent: int = 0  # 箇条書きのインデント
    is_list_item: bool = False
    list_marker: str = ""  # "•" or "1." etc.


def parse_markdown_lines(text: str) -> list[ParsedLine]:
    """Markdownテキストを行ごとにパースする。"""
    lines = text.split("\n")
    result: list[ParsedLine] = []

    for line in lines:
        parsed = _parse_line(line)
        result.append(parsed)

    return result


def _parse_line(line: str) -> ParsedLine:
    """1行をパースする。"""
    stripped = line.strip()

    # 見出し (## ...)
    heading_match = re.match(r"^(#{1,3})\s+(.+)$", stripped)
    if heading_match:
        level = len(heading_match.group(1))
        content = heading_match.group(2)
        return ParsedLine(
            spans=[TextSpan(content, SpanStyle.HEADING)],
            indent=0,
        )

    # 箇条書き (- ... / * ...)
    bullet_match = re.match(r"^[-*]\s+(.+)$", stripped)
    if bullet_match:
        content = bullet_match.group(1)
        return ParsedLine(
            spans=_parse_inline(content),
            indent=1,
            is_list_item=True,
            list_marker="•",
        )

    # 番号付きリスト (1. ...)
    num_match = re.match(r"^(\d+)[.)]\s+(.+)$", stripped)
    if num_match:
        number = num_match.group(1)
        content = num_match.group(2)
        return ParsedLine(
            spans=_parse_inline(content),
            indent=1,
            is_list_item=True,
            list_marker=f"{number}.",
        )

    # 通常行
    if stripped:
        return ParsedLine(spans=_parse_inline(stripped))
    else:
        return ParsedLine(spans=[TextSpan("")])


def _parse_inline(text: str) -> list[TextSpan]:
    """インラインのMarkdown記法（太字・斜体）をパースする。"""
    spans: list[TextSpan] = []

    # **太字** と *斜体* をパース
    # パターン: **text** -> bold, *text* -> italic
    pattern = re.compile(
        r"(\*\*(.+?)\*\*)"    # **bold**
        r"|(__(.+?)__)"        # __bold__
        r"|(\*(.+?)\*)"       # *italic*
        r"|(_(.+?)_)"         # _italic_
    )

    pos = 0
    for match in pattern.finditer(text):
        # マッチ前のテキスト
        if match.start() > pos:
            spans.append(TextSpan(text[pos:match.start()], SpanStyle.NORMAL))

        if match.group(2):  # **bold**
            spans.append(TextSpan(match.group(2), SpanStyle.BOLD))
        elif match.group(4):  # __bold__
            spans.append(TextSpan(match.group(4), SpanStyle.BOLD))
        elif match.group(6):  # *italic*
            spans.append(TextSpan(match.group(6), SpanStyle.ITALIC))
        elif match.group(8):  # _italic_
            spans.append(TextSpan(match.group(8), SpanStyle.ITALIC))

        pos = match.end()

    # 残りのテキスト
    if pos < len(text):
        spans.append(TextSpan(text[pos:], SpanStyle.NORMAL))

    if not spans:
        spans.append(TextSpan(text, SpanStyle.NORMAL))

    return spans


def strip_markdown_for_tts(text: str) -> str:
    """Markdown記法を除去して音声合成用のプレーンテキストにする。

    - **太字** → 太字
    - *斜体* → 斜体
    - # 見出し → 見出し
    - 箇条書きマーカー → 削除
    - 番号リスト → そのまま
    """
    result = text

    # 太字 (**text** or __text__)
    result = re.sub(r"\*\*(.+?)\*\*", r"\1", result)
    result = re.sub(r"__(.+?)__", r"\1", result)

    # 斜体 (*text* or _text_)
    result = re.sub(r"\*(.+?)\*", r"\1", result)
    result = re.sub(r"_(.+?)_", r"\1", result)

    # 見出し (# text)
    result = re.sub(r"^#{1,3}\s+", "", result, flags=re.MULTILINE)

    # 箇条書きマーカー
    result = re.sub(r"^[-*]\s+", "", result, flags=re.MULTILINE)

    return result.strip()
