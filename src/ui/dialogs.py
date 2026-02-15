"""共通ダイアログユーティリティ"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk


def show_info(parent: ctk.CTkBaseClass, title: str, message: str) -> None:
    """情報ダイアログを表示する。"""
    dialog = ctk.CTkToplevel(parent)
    dialog.title(title)
    dialog.geometry("450x150")
    dialog.transient(parent.winfo_toplevel())
    dialog.grab_set()

    ctk.CTkLabel(dialog, text=message, wraplength=400).pack(
        expand=True, padx=20, pady=20
    )
    ctk.CTkButton(dialog, text="OK", command=dialog.destroy).pack(pady=(0, 16))


def show_error(parent: ctk.CTkBaseClass, message: str) -> None:
    """エラーダイアログを表示する。"""
    dialog = ctk.CTkToplevel(parent)
    dialog.title("エラー")
    dialog.geometry("450x150")
    dialog.transient(parent.winfo_toplevel())
    dialog.grab_set()

    ctk.CTkLabel(dialog, text=message, wraplength=400, text_color="red").pack(
        expand=True, padx=20, pady=20
    )
    ctk.CTkButton(dialog, text="OK", command=dialog.destroy).pack(pady=(0, 16))


def show_confirm(
    parent: ctk.CTkBaseClass,
    message: str,
    on_confirm: Callable[[], None],
    confirm_text: str = "OK",
    confirm_color: str = "red",
) -> None:
    """確認ダイアログを表示する。"""
    dialog = ctk.CTkToplevel(parent)
    dialog.title("確認")
    dialog.geometry("450x180")
    dialog.transient(parent.winfo_toplevel())
    dialog.grab_set()

    ctk.CTkLabel(dialog, text=message, wraplength=400).pack(
        expand=True, padx=20, pady=20
    )

    btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
    btn_frame.pack(pady=(0, 16))

    ctk.CTkButton(
        btn_frame,
        text="キャンセル",
        fg_color="gray40",
        command=dialog.destroy,
    ).pack(side="left", padx=8)

    def confirm() -> None:
        dialog.destroy()
        on_confirm()

    ctk.CTkButton(
        btn_frame,
        text=confirm_text,
        fg_color=confirm_color,
        hover_color="darkred" if confirm_color == "red" else None,
        command=confirm,
    ).pack(side="left", padx=8)
