"""LMDebate - LLMディベートアプリケーション エントリーポイント"""

import logging
import sys
from pathlib import Path

from src.app import App
from src.ui.main_window import MainWindow


def setup_logging() -> None:
    """ロギングの基本設定を行う。コンソールとファイルの両方に出力する。"""
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # ログディレクトリ作成
    log_dir = Path(__file__).resolve().parent / "logs"
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "lmdebate.log"

    # ルートロガー設定
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # コンソールハンドラ (INFO以上)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))
    root_logger.addHandler(console_handler)

    # ファイルハンドラ (DEBUG以上、ローテーション付き)
    from logging.handlers import RotatingFileHandler
    file_handler = RotatingFileHandler(
        log_file, maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(log_format, datefmt=date_format))
    root_logger.addHandler(file_handler)


def main() -> None:
    """アプリケーションのエントリーポイント。"""
    setup_logging()
    logger = logging.getLogger(__name__)

    try:
        logger.info("LMDebate を起動しています...")

        # アプリケーションオーケストレーター初期化
        app = App()

        # メインウィンドウ生成・起動
        window = MainWindow(app)
        window.mainloop()

    except Exception as e:
        logger.exception("アプリケーションの起動に失敗しました: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
