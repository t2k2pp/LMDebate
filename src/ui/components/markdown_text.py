"""Markdown対応テキスト表示ウィジェット

CTkTextboxベースで太字・斜体・箇条書き・見出しを表示する。
"""

from __future__ import annotations

import customtkinter as ctk

from src.utils.markdown_parser import (
    ParsedLine,
    SpanStyle,
    parse_markdown_lines,
)


class MarkdownText(ctk.CTkTextbox):
    """Markdownテキストをリッチ表示するウィジェット。"""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        text: str,
        text_color: str = "#ffffff",
        font_size: int = 13,
        wrap_width: int = 500,
        **kwargs,
    ) -> None:
        # 高さを自動調整するため、初期高さは小さく設定
        super().__init__(
            master,
            fg_color="transparent",
            wrap="word",
            activate_scrollbars=False,
            width=wrap_width,
            height=20,  # 初期値（後で自動調整）
            **kwargs,
        )

        self._text_color = text_color
        self._font_size = font_size

        # タグの設定
        self._setup_tags()

        # テキストの挿入
        self._insert_markdown(text)

        # 読み取り専用にする
        self.configure(state="disabled")

        # 高さの自動調整（テキスト挿入後にスケジュール）
        self.after(10, self._auto_resize)

    def _setup_tags(self) -> None:
        """テキストタグ（スタイル）を設定する。"""
        base_font = ctk.CTkFont(size=self._font_size)
        bold_font = ctk.CTkFont(size=self._font_size, weight="bold")
        italic_font = ctk.CTkFont(size=self._font_size, slant="italic")
        heading_font = ctk.CTkFont(size=self._font_size + 2, weight="bold")

        self._textbox.tag_configure("normal", foreground=self._text_color, font=base_font)
        self._textbox.tag_configure("bold", foreground=self._text_color, font=bold_font)
        self._textbox.tag_configure("italic", foreground=self._text_color, font=italic_font)
        self._textbox.tag_configure("heading", foreground=self._text_color, font=heading_font)
        self._textbox.tag_configure("indent", lmargin1=20, lmargin2=30)
        self._textbox.tag_configure("marker", foreground=self._text_color, font=bold_font)

    def _insert_markdown(self, text: str) -> None:
        """パースしたMarkdownテキストを挿入する。"""
        lines = parse_markdown_lines(text)

        for i, line in enumerate(lines):
            if i > 0:
                self._textbox.insert("end", "\n")

            # 箇条書きのマーカー
            if line.is_list_item:
                self._textbox.insert("end", f"  {line.list_marker} ", ("marker", "indent"))

            # スパンを挿入
            for span in line.spans:
                tag = self._span_style_to_tag(span.style)
                tags = (tag,)
                if line.indent > 0 and not line.is_list_item:
                    tags = (tag, "indent")
                self._textbox.insert("end", span.text, tags)

    def _span_style_to_tag(self, style: SpanStyle) -> str:
        """SpanStyleをタグ名に変換する。"""
        return {
            SpanStyle.NORMAL: "normal",
            SpanStyle.BOLD: "bold",
            SpanStyle.ITALIC: "italic",
            SpanStyle.HEADING: "heading",
        }.get(style, "normal")

    def _auto_resize(self) -> None:
        """テキスト内容に合わせて高さを自動調整する。"""
        try:
            # 行数を取得
            self._textbox.update_idletasks()
            # テキストの最終行のインデックスを取得
            end_index = self._textbox.index("end-1c")
            num_lines = int(end_index.split(".")[0])

            # 行の高さを推定（フォントサイズ + 行間）
            line_height = self._font_size + 6
            # wrap による追加行を考慮
            estimated_height = max(num_lines * line_height + 10, 30)
            # 最大高さを制限
            max_height = 800
            final_height = min(estimated_height, max_height)

            self.configure(height=final_height)
        except Exception:
            pass
