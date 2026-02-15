"""ファイル添付ウィジェット

ファイル選択ダイアログによるファイル追加、一覧表示、削除機能を提供する。
"""

from __future__ import annotations

import os
from pathlib import Path
from tkinter import filedialog

import customtkinter as ctk


# サポートする拡張子
_SUPPORTED_EXTENSIONS: tuple[str, ...] = (
    ".pdf", ".txt", ".md", ".csv",
    ".png", ".jpg", ".jpeg", ".gif", ".webp",
)

# ファイルダイアログ用フィルター文字列
_FILETYPES: list[tuple[str, str]] = [
    ("サポートされたファイル", " ".join(f"*{ext}" for ext in _SUPPORTED_EXTENSIONS)),
    ("ドキュメント", "*.pdf *.txt *.md *.csv"),
    ("画像", "*.png *.jpg *.jpeg *.gif *.webp"),
    ("すべてのファイル", "*.*"),
]


def _format_file_size(size_bytes: int) -> str:
    """ファイルサイズを人間に読みやすい形式に変換する。"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


class _FileRow(ctk.CTkFrame):
    """添付ファイル一覧の 1 行を表すウィジェット。"""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        file_path: str,
        on_remove: callable,
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color="#2a2a2a", corner_radius=6, height=32, **kwargs)

        self.file_path = file_path
        path_obj = Path(file_path)
        file_name = path_obj.name

        try:
            file_size = os.path.getsize(file_path)
        except OSError:
            file_size = 0
        size_text = _format_file_size(file_size)

        # ファイル名
        name_label = ctk.CTkLabel(
            self,
            text=file_name,
            font=ctk.CTkFont(size=12),
            text_color="#e0e0e0",
            anchor="w",
        )
        name_label.pack(side="left", padx=(8, 4), pady=4)

        # ファイルサイズ
        size_label = ctk.CTkLabel(
            self,
            text=size_text,
            font=ctk.CTkFont(size=11),
            text_color="#888888",
            anchor="w",
        )
        size_label.pack(side="left", padx=(0, 8), pady=4)

        # 削除ボタン
        remove_btn = ctk.CTkButton(
            self,
            text="\u00d7",  # ×
            width=24,
            height=24,
            font=ctk.CTkFont(size=14),
            fg_color="transparent",
            hover_color="#ef4444",
            text_color="#999999",
            command=lambda: on_remove(self),
        )
        remove_btn.pack(side="right", padx=(0, 4), pady=4)


class FileAttachmentWidget(ctk.CTkFrame):
    """ファイル添付ウィジェット。

    ファイル選択ボタンと添付ファイル一覧を表示する。
    ファイルの追加・削除・取得機能を持つ。
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)

        self._file_paths: list[str] = []
        self._file_rows: list[_FileRow] = []

        # --- ファイル選択ボタン ---
        self._select_button = ctk.CTkButton(
            self,
            text="ファイルを選択...",
            command=self._open_file_dialog,
            font=ctk.CTkFont(size=12),
            fg_color="#333333",
            hover_color="#444444",
            text_color="#cccccc",
            height=30,
            width=140,
        )
        self._select_button.pack(anchor="w", pady=(4, 4))

        # --- ファイル一覧コンテナ ---
        self._list_frame = ctk.CTkFrame(self, fg_color="transparent")
        self._list_frame.pack(fill="x")

    def _open_file_dialog(self) -> None:
        """ファイル選択ダイアログを開き、選択されたファイルを追加する。"""
        paths = filedialog.askopenfilenames(
            title="添付ファイルを選択",
            filetypes=_FILETYPES,
        )
        for path in paths:
            self.add_file(path)

    def add_file(self, path: str) -> bool:
        """ファイルを追加する。

        Parameters
        ----------
        path : ファイルパス

        Returns
        -------
        bool
            追加に成功した場合 True、拡張子が未対応または重複の場合 False
        """
        path = os.path.normpath(path)
        ext = Path(path).suffix.lower()

        # 拡張子チェック
        if ext not in _SUPPORTED_EXTENSIONS:
            return False

        # 重複チェック
        if path in self._file_paths:
            return False

        # ファイル存在チェック
        if not os.path.isfile(path):
            return False

        self._file_paths.append(path)

        row = _FileRow(
            self._list_frame,
            file_path=path,
            on_remove=self._remove_file_row,
        )
        row.pack(fill="x", pady=(2, 0))
        self._file_rows.append(row)

        return True

    def _remove_file_row(self, row: _FileRow) -> None:
        """ファイル行を削除する。"""
        if row.file_path in self._file_paths:
            self._file_paths.remove(row.file_path)
        if row in self._file_rows:
            self._file_rows.remove(row)
        row.destroy()

    def get_files(self) -> list[str]:
        """現在添付されているファイルパスのリストを返す。

        Returns
        -------
        list[str]
            ファイルパスのリスト
        """
        return list(self._file_paths)

    def clear(self) -> None:
        """すべての添付ファイルをクリアする。"""
        for row in self._file_rows:
            row.destroy()
        self._file_rows.clear()
        self._file_paths.clear()
