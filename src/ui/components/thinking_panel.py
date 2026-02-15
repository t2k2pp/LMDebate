"""思考内容の展開/折りたたみパネルコンポーネント

履歴ビューで使用する。ライブディベートビューでは使用しない。
"""

from __future__ import annotations

import customtkinter as ctk


class ThinkingPanel(ctk.CTkFrame):
    """展開/折りたたみ可能な思考内容表示パネル。

    トグルボタンで思考テキストの表示・非表示を切り替える。
    思考テキストはミュートされた薄い色合いで表示される。
    """

    _COLLAPSED_TEXT = "思考を表示"
    _EXPANDED_TEXT = "思考を非表示"

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        thinking_text: str,
        participant_name: str = "",
        **kwargs,
    ) -> None:
        """
        Parameters
        ----------
        master : 親ウィジェット
        thinking_text : 思考内容のテキスト
        participant_name : 参加者名（ヘッダーに表示、省略可）
        """
        super().__init__(master, fg_color="#1e1e1e", corner_radius=8, **kwargs)

        self._thinking_text = thinking_text
        self._is_expanded = False

        # --- トグルボタン行 ---
        toggle_frame = ctk.CTkFrame(self, fg_color="transparent")
        toggle_frame.pack(fill="x", padx=8, pady=(6, 2))

        # 展開/折りたたみアイコン付きボタン
        label_text = ""
        if participant_name:
            label_text = f"{participant_name} の"
        label_text += self._COLLAPSED_TEXT

        self._toggle_button = ctk.CTkButton(
            toggle_frame,
            text=f"▶ {label_text}",
            fg_color="transparent",
            hover_color="#333333",
            text_color="#999999",
            font=ctk.CTkFont(size=12),
            anchor="w",
            command=self._toggle,
            height=26,
        )
        self._toggle_button.pack(fill="x")

        self._participant_name = participant_name

        # --- 思考テキスト表示エリア (初期状態: 非表示) ---
        self._content_frame = ctk.CTkFrame(
            self, fg_color="#171717", corner_radius=6
        )
        # pack しない (非表示)

        self._content_label = ctk.CTkLabel(
            self._content_frame,
            text=self._thinking_text,
            text_color="#777777",
            font=ctk.CTkFont(size=12),
            wraplength=480,
            justify="left",
            anchor="nw",
        )
        self._content_label.pack(fill="x", padx=10, pady=8)

    def _toggle(self) -> None:
        """思考テキストの表示/非表示を切り替える。"""
        self._is_expanded = not self._is_expanded

        if self._is_expanded:
            self._content_frame.pack(fill="x", padx=8, pady=(2, 8))
            label_text = ""
            if self._participant_name:
                label_text = f"{self._participant_name} の"
            label_text += self._EXPANDED_TEXT
            self._toggle_button.configure(text=f"▼ {label_text}")
        else:
            self._content_frame.pack_forget()
            label_text = ""
            if self._participant_name:
                label_text = f"{self._participant_name} の"
            label_text += self._COLLAPSED_TEXT
            self._toggle_button.configure(text=f"▶ {label_text}")

    @property
    def is_expanded(self) -> bool:
        """現在展開状態かどうかを返す。"""
        return self._is_expanded

    def set_thinking_text(self, text: str) -> None:
        """思考テキストを更新する。"""
        self._thinking_text = text
        self._content_label.configure(text=text)
