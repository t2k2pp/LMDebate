"""ディベートメッセージ表示用バブルコンポーネント"""

from __future__ import annotations

import customtkinter as ctk


# ロール別カラー設定
_ROLE_COLORS: dict[str, dict[str, str]] = {
    "A": {
        "bg": "#1a3a5c",
        "bg_hover": "#1f4470",
        "label_bg": "#2563eb",
        "label_fg": "#ffffff",
        "name_fg": "#93bbf0",
        "content_fg": "#dbeafe",
        "round_fg": "#7eaadc",
    },
    "B": {
        "bg": "#1a3c2a",
        "bg_hover": "#1f4a32",
        "label_bg": "#16a34a",
        "label_fg": "#ffffff",
        "name_fg": "#86d9a0",
        "content_fg": "#dcfce7",
        "round_fg": "#7ecfa0",
    },
    "C": {
        "bg": "#3c2e1a",
        "bg_hover": "#4a3720",
        "label_bg": "#ea580c",
        "label_fg": "#ffffff",
        "name_fg": "#f9b97a",
        "content_fg": "#ffedd5",
        "round_fg": "#e0a86e",
    },
}

_SKIP_COLORS: dict[str, str] = {
    "bg": "#2b2b2b",
    "fg": "#888888",
}


class MessageBubble(ctk.CTkFrame):
    """単一のディベートメッセージを表示するバブルウィジェット。

    対応するメッセージタイプ: speech, thinking, skip, judgment
    ロール (A / B / C) に応じた色分けを行う。
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        participant_name: str,
        role_label: str,
        round_number: int,
        content: str,
        message_type: str = "speech",
        **kwargs,
    ) -> None:
        """
        Parameters
        ----------
        master : 親ウィジェット
        participant_name : 参加者名
        role_label : "A", "B", "C" のいずれか
        round_number : ラウンド番号
        content : メッセージ本文
        message_type : "speech" | "thinking" | "skip" | "judgment"
        """
        self._role_label = role_label.upper()
        self._message_type = message_type

        is_skip = message_type == "skip"
        colors = _SKIP_COLORS if is_skip else _ROLE_COLORS.get(
            self._role_label, _ROLE_COLORS["A"]
        )

        bg_color = colors.get("bg", "#2b2b2b")
        super().__init__(master, fg_color=bg_color, corner_radius=10, **kwargs)

        # --- ヘッダー行: ロールラベル + 名前 + ラウンド番号 ---
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(8, 2))

        if not is_skip:
            role_colors = _ROLE_COLORS.get(self._role_label, _ROLE_COLORS["A"])

            role_badge = ctk.CTkLabel(
                header,
                text=f" {self._role_label} ",
                fg_color=role_colors["label_bg"],
                text_color=role_colors["label_fg"],
                corner_radius=4,
                font=ctk.CTkFont(size=12, weight="bold"),
                width=28,
                height=22,
            )
            role_badge.pack(side="left", padx=(0, 6))

            name_label = ctk.CTkLabel(
                header,
                text=participant_name,
                text_color=role_colors["name_fg"],
                font=ctk.CTkFont(size=13, weight="bold"),
            )
            name_label.pack(side="left")

            round_label = ctk.CTkLabel(
                header,
                text=f"R{round_number}",
                text_color=role_colors["round_fg"],
                font=ctk.CTkFont(size=11),
            )
            round_label.pack(side="right")

            # メッセージタイプが judgment の場合にタイプ表示
            if message_type == "judgment":
                type_label = ctk.CTkLabel(
                    header,
                    text="[判定]",
                    text_color=role_colors["round_fg"],
                    font=ctk.CTkFont(size=11),
                )
                type_label.pack(side="right", padx=(0, 8))

            elif message_type == "thinking":
                type_label = ctk.CTkLabel(
                    header,
                    text="[思考]",
                    text_color=role_colors["round_fg"],
                    font=ctk.CTkFont(size=11),
                )
                type_label.pack(side="right", padx=(0, 8))

        # --- メッセージ本文 ---
        if is_skip:
            content_text = f"（{participant_name} はこのラウンドをスキップしました）"
            content_label = ctk.CTkLabel(
                self,
                text=content_text,
                text_color=_SKIP_COLORS["fg"],
                font=ctk.CTkFont(size=12, slant="italic"),
                wraplength=500,
                justify="left",
                anchor="w",
            )
            content_label.pack(fill="x", padx=14, pady=(4, 10))
        else:
            role_colors = _ROLE_COLORS.get(self._role_label, _ROLE_COLORS["A"])
            content_fg = role_colors["content_fg"]

            # thinking タイプはやや薄い表示
            if message_type == "thinking":
                content_fg = role_colors["round_fg"]

            content_label = ctk.CTkLabel(
                self,
                text=content,
                text_color=content_fg,
                font=ctk.CTkFont(size=13),
                wraplength=500,
                justify="left",
                anchor="nw",
            )
            content_label.pack(fill="x", padx=14, pady=(4, 10))
