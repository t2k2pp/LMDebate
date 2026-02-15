"""LMDebate - LLMディベートアプリケーション エントリーポイント"""

import logging
import sys

from src.app import App
from src.ui.main_window import MainWindow


def setup_logging() -> None:
    """ロギングの基本設定を行う。"""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


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
