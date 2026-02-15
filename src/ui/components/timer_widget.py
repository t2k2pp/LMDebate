"""カウントダウンタイマーウィジェット

人間参加者 C のスキップタイムアウト用。
Tkinter の after() を使用したスレッドセーフなタイマー更新。
"""

from __future__ import annotations

from typing import Callable

import customtkinter as ctk


class TimerWidget(ctk.CTkFrame):
    """カウントダウンタイマーウィジェット。

    残り時間をラベルとプログレスバーで表示する。
    タイムアウト時に on_timeout コールバックを呼び出す。
    """

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        on_timeout: Callable[[], None] | None = None,
        show_progress_bar: bool = True,
        **kwargs,
    ) -> None:
        """
        Parameters
        ----------
        master : 親ウィジェット
        on_timeout : タイムアウト時に呼ばれるコールバック
        show_progress_bar : プログレスバーを表示するかどうか
        """
        super().__init__(master, fg_color="transparent", **kwargs)

        self._on_timeout = on_timeout
        self._total_seconds: int = 0
        self._remaining_seconds: int = 0
        self._is_running: bool = False
        self._after_id: str | None = None

        # --- 残り時間ラベル ---
        self._time_label = ctk.CTkLabel(
            self,
            text="残り: --s",
            font=ctk.CTkFont(size=13),
            text_color="#cccccc",
        )
        self._time_label.pack(pady=(4, 2))

        # --- プログレスバー (オプション) ---
        self._show_progress_bar = show_progress_bar
        if show_progress_bar:
            self._progress_bar = ctk.CTkProgressBar(
                self,
                width=200,
                height=8,
                progress_color="#f59e0b",
                fg_color="#333333",
                corner_radius=4,
            )
            self._progress_bar.set(1.0)
            self._progress_bar.pack(pady=(2, 4))

    def start(self, seconds: int) -> None:
        """カウントダウンを開始する。

        Parameters
        ----------
        seconds : カウントダウン秒数
        """
        self.stop()  # 既存タイマーがあればキャンセル

        self._total_seconds = max(seconds, 1)
        self._remaining_seconds = self._total_seconds
        self._is_running = True

        self._update_display()
        self._schedule_tick()

    def stop(self) -> None:
        """カウントダウンを停止する。タイムアウトコールバックは呼ばない。"""
        self._is_running = False
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except ValueError:
                pass
            self._after_id = None

    def reset(self) -> None:
        """タイマーを初期状態にリセットする。"""
        self.stop()
        self._total_seconds = 0
        self._remaining_seconds = 0
        self._time_label.configure(text="残り: --s", text_color="#cccccc")
        if self._show_progress_bar:
            self._progress_bar.set(1.0)
            self._progress_bar.configure(progress_color="#f59e0b")

    @property
    def is_running(self) -> bool:
        """タイマーが動作中かどうかを返す。"""
        return self._is_running

    @property
    def remaining(self) -> int:
        """残り秒数を返す。"""
        return self._remaining_seconds

    def _schedule_tick(self) -> None:
        """1 秒後の tick をスケジュールする。"""
        if self._is_running:
            self._after_id = self.after(1000, self._tick)

    def _tick(self) -> None:
        """1 秒ごとに呼ばれるタイマーコールバック。"""
        if not self._is_running:
            return

        self._remaining_seconds -= 1

        if self._remaining_seconds <= 0:
            self._remaining_seconds = 0
            self._is_running = False
            self._update_display()
            if self._on_timeout is not None:
                self._on_timeout()
            return

        self._update_display()
        self._schedule_tick()

    def _update_display(self) -> None:
        """ラベルとプログレスバーの表示を更新する。"""
        remaining = self._remaining_seconds

        # テキスト更新
        self._time_label.configure(text=f"残り: {remaining}s")

        # 残り少なくなったら色を変更
        if remaining <= 5:
            self._time_label.configure(text_color="#ef4444")
            bar_color = "#ef4444"
        elif remaining <= 10:
            self._time_label.configure(text_color="#f59e0b")
            bar_color = "#f59e0b"
        else:
            self._time_label.configure(text_color="#cccccc")
            bar_color = "#f59e0b"

        # プログレスバー更新
        if self._show_progress_bar:
            progress = remaining / self._total_seconds if self._total_seconds > 0 else 0.0
            self._progress_bar.set(progress)
            self._progress_bar.configure(progress_color=bar_color)
