"""参加者情報カードコンポーネント"""

from __future__ import annotations

import customtkinter as ctk


# ステータスに応じた色設定
_STATUS_COLORS: dict[str, dict[str, str]] = {
    "待機中": {"fg": "#888888", "indicator": "#555555"},
    "発言中...": {"fg": "#60a5fa", "indicator": "#3b82f6"},
    "思考中...": {"fg": "#c084fc", "indicator": "#a855f7"},
    "あなたのターン": {"fg": "#fbbf24", "indicator": "#f59e0b"},
}

# ロール別アクセントカラー
_ROLE_ACCENT: dict[str, str] = {
    "proposer_a": "#2563eb",
    "proposer_b": "#16a34a",
    "judge": "#ea580c",
}

# ロール表示名
_ROLE_DISPLAY: dict[str, str] = {
    "proposer_a": "提案者 A",
    "proposer_b": "提案者 B",
    "judge": "審判 C",
}

# タイプ表示名
_TYPE_DISPLAY: dict[str, str] = {
    "llm": "LLM",
    "human": "人間",
}


class ParticipantCard(ctk.CTkFrame):
    """参加者情報を表示するカードウィジェット。

    名前、ロール、タイプ (LLM/Human)、モデル名、ステータスを表示する。
    update_status() でステータスを動的に変更できる。
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        name: str,
        role: str,
        participant_type: str,
        model_name: str | None = None,
        status: str = "待機中",
        **kwargs,
    ) -> None:
        """
        Parameters
        ----------
        master : 親ウィジェット
        name : 参加者名
        role : "proposer_a" | "proposer_b" | "judge"
        participant_type : "llm" | "human"
        model_name : LLM モデル名 (LLM の場合のみ)
        status : 初期ステータス ("待機中", "発言中...", "思考中...", "あなたのターン")
        """
        accent = _ROLE_ACCENT.get(role, "#555555")
        super().__init__(
            master, fg_color="#1e1e1e", corner_radius=8, border_width=2,
            border_color=accent, **kwargs,
        )

        self._role = role
        self._participant_type = participant_type

        # --- 上段: 名前 + ロールラベル ---
        top_row = ctk.CTkFrame(self, fg_color="transparent")
        top_row.pack(fill="x", padx=10, pady=(8, 2))

        name_label = ctk.CTkLabel(
            top_row,
            text=name,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color="#e0e0e0",
        )
        name_label.pack(side="left")

        role_text = _ROLE_DISPLAY.get(role, role)
        role_badge = ctk.CTkLabel(
            top_row,
            text=role_text,
            fg_color=accent,
            text_color="#ffffff",
            corner_radius=4,
            font=ctk.CTkFont(size=11),
            height=20,
        )
        role_badge.pack(side="right")

        # --- 中段: タイプ + モデル名 ---
        info_row = ctk.CTkFrame(self, fg_color="transparent")
        info_row.pack(fill="x", padx=10, pady=2)

        type_text = _TYPE_DISPLAY.get(participant_type, participant_type)
        type_label = ctk.CTkLabel(
            info_row,
            text=type_text,
            font=ctk.CTkFont(size=11),
            text_color="#aaaaaa",
        )
        type_label.pack(side="left")

        if model_name:
            model_label = ctk.CTkLabel(
                info_row,
                text=f"({model_name})",
                font=ctk.CTkFont(size=11),
                text_color="#888888",
            )
            model_label.pack(side="left", padx=(6, 0))

        # --- 下段: ステータス ---
        status_row = ctk.CTkFrame(self, fg_color="transparent")
        status_row.pack(fill="x", padx=10, pady=(2, 8))

        status_colors = _STATUS_COLORS.get(status, _STATUS_COLORS["待機中"])

        self._status_indicator = ctk.CTkLabel(
            status_row,
            text="\u25cf",  # ●
            font=ctk.CTkFont(size=10),
            text_color=status_colors["indicator"],
            width=16,
        )
        self._status_indicator.pack(side="left")

        self._status_label = ctk.CTkLabel(
            status_row,
            text=status,
            font=ctk.CTkFont(size=12),
            text_color=status_colors["fg"],
        )
        self._status_label.pack(side="left", padx=(2, 0))

    def update_status(self, status: str) -> None:
        """ステータスを更新する。

        Parameters
        ----------
        status : "待機中" | "発言中..." | "思考中..." | "あなたのターン"
        """
        colors = _STATUS_COLORS.get(status, _STATUS_COLORS["待機中"])
        self._status_label.configure(text=status, text_color=colors["fg"])
        self._status_indicator.configure(text_color=colors["indicator"])
