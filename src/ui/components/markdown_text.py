"""Markdown対応テキスト表示ウィジェット

CTkFrameベースで太字・箇条書き・見出しを複数CTkLabelで表示する。
CTkTextboxの内部スクロール問題を回避するため、Label方式を採用。
"""

from __future__ import annotations

import re

import customtkinter as ctk


def render_markdown_content(
    parent: ctk.CTkBaseClass,
    text: str,
    text_color: str = "#ffffff",
    font_size: int = 13,
    wraplength: int = 500,
) -> ctk.CTkFrame:
    """Markdownテキストを複数ラベルで表示するフレームを生成する。

    Parameters
    ----------
    parent : 親ウィジェット
    text : Markdown含むテキスト
    text_color : テキスト色
    font_size : フォントサイズ
    wraplength : ラップ幅

    Returns
    -------
    CTkFrame : ラベルを含むフレーム
    """
    frame = ctk.CTkFrame(parent, fg_color="transparent")
    frame.grid_columnconfigure(0, weight=1)

    base_font = ctk.CTkFont(size=font_size)
    bold_font = ctk.CTkFont(size=font_size, weight="bold")
    heading_font = ctk.CTkFont(size=font_size + 2, weight="bold")

    lines = text.split("\n")
    row = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            # 空行 → スペーサー
            spacer = ctk.CTkLabel(frame, text="", height=6)
            spacer.grid(row=row, column=0, sticky="w")
            row += 1
            continue

        # 見出し (## ...)
        heading_match = re.match(r"^(#{1,3})\s+(.+)$", stripped)
        if heading_match:
            content = _strip_inline_md(heading_match.group(2))
            lbl = ctk.CTkLabel(
                frame, text=content, text_color=text_color,
                font=heading_font, anchor="w", justify="left",
                wraplength=wraplength,
            )
            lbl.grid(row=row, column=0, sticky="w", pady=(2, 2))
            row += 1
            continue

        # 箇条書き (- ... / * ...)
        bullet_match = re.match(r"^[-*]\s+(.+)$", stripped)
        if bullet_match:
            content = bullet_match.group(1)
            display = "  • " + _render_inline_display(content)
            font = _pick_font_for_line(content, base_font, bold_font)
            lbl = ctk.CTkLabel(
                frame, text=display, text_color=text_color,
                font=font, anchor="w", justify="left",
                wraplength=wraplength,
            )
            lbl.grid(row=row, column=0, sticky="w")
            row += 1
            continue

        # 番号付きリスト (1. ...)
        num_match = re.match(r"^(\d+)[.)]\s+(.+)$", stripped)
        if num_match:
            number = num_match.group(1)
            content = num_match.group(2)
            display = f"  {number}. " + _render_inline_display(content)
            font = _pick_font_for_line(content, base_font, bold_font)
            lbl = ctk.CTkLabel(
                frame, text=display, text_color=text_color,
                font=font, anchor="w", justify="left",
                wraplength=wraplength,
            )
            lbl.grid(row=row, column=0, sticky="w")
            row += 1
            continue

        # 通常行
        display = _render_inline_display(stripped)
        font = _pick_font_for_line(stripped, base_font, bold_font)
        lbl = ctk.CTkLabel(
            frame, text=display, text_color=text_color,
            font=font, anchor="w", justify="left",
            wraplength=wraplength,
        )
        lbl.grid(row=row, column=0, sticky="w")
        row += 1

    return frame


def _strip_inline_md(text: str) -> str:
    """インラインMarkdown記号を除去する。"""
    result = re.sub(r"\*\*(.+?)\*\*", r"\1", text)
    result = re.sub(r"__(.+?)__", r"\1", result)
    result = re.sub(r"\*(.+?)\*", r"\1", result)
    result = re.sub(r"_(.+?)_", r"\1", result)
    return result


def _render_inline_display(text: str) -> str:
    """インラインMarkdownを表示用テキストに変換する。

    太字(**)や斜体(*)のマーカーを除去し、プレーンテキストにする。
    CTkLabelは1ラベルで部分的にフォントを変えられないため、
    マーカー除去のみ行い、全体的な太字判定は_pick_font_for_lineで行う。
    """
    return _strip_inline_md(text)


def _pick_font_for_line(
    raw_text: str,
    base_font: ctk.CTkFont,
    bold_font: ctk.CTkFont,
) -> ctk.CTkFont:
    """行の大部分が太字の場合はbold_fontを返す。"""
    # **text** の部分がテキストの50%以上を占めるなら太字
    bold_matches = re.findall(r"\*\*(.+?)\*\*", raw_text)
    if not bold_matches:
        bold_matches = re.findall(r"__(.+?)__", raw_text)
    if bold_matches:
        bold_len = sum(len(m) for m in bold_matches)
        plain = _strip_inline_md(raw_text)
        if plain and bold_len / len(plain) > 0.5:
            return bold_font
    return base_font


# 後方互換のためクラスも公開（ただし中身はrender_markdown_contentのラッパー）
class MarkdownText(ctk.CTkFrame):
    """Markdownテキストをリッチ表示するウィジェット（CTkFrameベース）。"""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        text: str,
        text_color: str = "#ffffff",
        font_size: int = 13,
        wrap_width: int = 500,
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self.grid_columnconfigure(0, weight=1)

        inner = render_markdown_content(
            self,
            text=text,
            text_color=text_color,
            font_size=font_size,
            wraplength=wrap_width,
        )
        inner.grid(row=0, column=0, sticky="ew")
