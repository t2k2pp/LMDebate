"""音声合成（TTS）サービス

ディベートの発言を音声で読み上げる機能を提供する。
Windows SAPI (pyttsx3) を使用。
"""

from __future__ import annotations

import logging
import queue
import threading
from typing import Callable

from src.utils.markdown_parser import strip_markdown_for_tts

logger = logging.getLogger(__name__)

# pyttsx3 は遅延インポート（未インストールの場合に対応）
_pyttsx3 = None


def _get_pyttsx3():
    """pyttsx3モジュールを遅延インポートする。"""
    global _pyttsx3
    if _pyttsx3 is None:
        try:
            import pyttsx3
            _pyttsx3 = pyttsx3
        except ImportError:
            _pyttsx3 = False  # インポート失敗を記録
    return _pyttsx3 if _pyttsx3 is not False else None


class TTSService:
    """音声合成サービス。

    発言テキストをキューに入れ、専用スレッドで順次読み上げる。
    Markdown記法はTTS読み上げ時に自動除去される。
    """

    def __init__(self) -> None:
        self._enabled = False
        self._queue: queue.Queue[str | None] = queue.Queue()
        self._thread: threading.Thread | None = None
        self._speaking = False
        self._engine = None
        self._on_speech_done: Callable[[], None] | None = None

        # 利用可能かチェック
        pyttsx3 = _get_pyttsx3()
        self._available = pyttsx3 is not None
        if not self._available:
            logger.warning("pyttsx3が未インストールのため、音声合成は利用できません。"
                           "pip install pyttsx3 でインストールしてください。")

    @property
    def is_available(self) -> bool:
        """TTS機能が利用可能かどうか。"""
        return self._available

    @property
    def is_enabled(self) -> bool:
        """TTS機能が有効かどうか。"""
        return self._enabled

    @property
    def is_speaking(self) -> bool:
        """現在読み上げ中かどうか。"""
        return self._speaking

    def set_enabled(self, enabled: bool) -> None:
        """TTS機能の有効/無効を切り替える。"""
        if enabled and not self._available:
            logger.warning("pyttsx3が未インストールのため、TTSを有効にできません。")
            return
        self._enabled = enabled
        if enabled:
            self._start_worker()
        else:
            self.stop()

    def speak(self, text: str, participant_name: str = "") -> None:
        """テキストを読み上げキューに追加する。

        Parameters
        ----------
        text : 読み上げるテキスト（Markdown含む可）
        participant_name : 発言者名（読み上げ前に名前を言う）
        """
        if not self._enabled or not self._available:
            return

        # Markdown記法を除去
        clean_text = strip_markdown_for_tts(text)
        if not clean_text or clean_text.upper() == "SKIP":
            return

        # 発言者名を付加
        if participant_name:
            full_text = f"{participant_name}。{clean_text}"
        else:
            full_text = clean_text

        self._queue.put(full_text)

    def stop(self) -> None:
        """読み上げを停止し、キューをクリアする。"""
        # キューをクリア
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except queue.Empty:
                break

        # エンジンの停止
        if self._engine:
            try:
                self._engine.stop()
            except Exception:
                pass

        self._speaking = False

    def shutdown(self) -> None:
        """サービスを完全に停止する。"""
        self.stop()
        self._enabled = False
        self._queue.put(None)  # ワーカースレッドを終了させる

    def _start_worker(self) -> None:
        """ワーカースレッドを開始する。"""
        if self._thread is not None and self._thread.is_alive():
            return

        self._thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._thread.start()

    def _worker_loop(self) -> None:
        """ワーカースレッドのメインループ。"""
        pyttsx3 = _get_pyttsx3()
        if pyttsx3 is None:
            return

        try:
            self._engine = pyttsx3.init()

            # 日本語対応の音声を探す
            voices = self._engine.getProperty("voices")
            for voice in voices:
                # Windows の場合 "Microsoft Haruka" や "Microsoft Ayumi" 等
                if "japanese" in voice.name.lower() or "ja" in voice.id.lower() \
                        or "haruka" in voice.name.lower() or "ayumi" in voice.name.lower() \
                        or "nanami" in voice.name.lower():
                    self._engine.setProperty("voice", voice.id)
                    logger.info("TTS 日本語音声を選択: %s", voice.name)
                    break

            # 読み上げ速度の調整
            self._engine.setProperty("rate", 180)

        except Exception as e:
            logger.error("TTS エンジン初期化失敗: %s", e)
            self._available = False
            return

        while self._enabled:
            try:
                text = self._queue.get(timeout=1.0)
                if text is None:
                    break  # shutdown指示

                self._speaking = True
                try:
                    self._engine.say(text)
                    self._engine.runAndWait()
                except Exception as e:
                    logger.warning("TTS 読み上げエラー: %s", e)
                finally:
                    self._speaking = False

            except queue.Empty:
                continue
            except Exception as e:
                logger.warning("TTS ワーカーエラー: %s", e)
                break

        # クリーンアップ
        try:
            if self._engine:
                self._engine.stop()
        except Exception:
            pass
        self._engine = None
