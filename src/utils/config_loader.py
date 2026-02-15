"""設定ファイルと環境変数の読み込みユーティリティ"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

from src.models.settings import AppSettings, LLMProviderConfig


def _find_project_root() -> Path:
    """config/ ディレクトリを含む祖先ディレクトリをプロジェクトルートとして検出する。"""
    current = Path(__file__).resolve().parent
    while current != current.parent:
        if (current / "config").is_dir():
            return current
        current = current.parent
    raise FileNotFoundError(
        "プロジェクトルートが見つかりません。config/ ディレクトリを含むディレクトリが必要です。"
    )


PROJECT_ROOT: Path = _find_project_root()


def load_env() -> None:
    """プロジェクトルート直下の .env ファイルを読み込む。"""
    env_path = PROJECT_ROOT / ".env"
    load_dotenv(dotenv_path=env_path)


def get_env(key: str, default: str | None = None) -> str | None:
    """環境変数を取得する。"""
    return os.environ.get(key, default)


def load_app_settings() -> AppSettings:
    """config/default_settings.json から AppSettings を読み込む。"""
    settings_path = PROJECT_ROOT / "config" / "default_settings.json"
    with open(settings_path, encoding="utf-8") as f:
        data: dict = json.load(f)
    return AppSettings.from_dict(data)


def load_llm_providers() -> list[LLMProviderConfig]:
    """config/llm_providers.json から LLMProviderConfig のリストを読み込む。"""
    providers_path = PROJECT_ROOT / "config" / "llm_providers.json"
    with open(providers_path, encoding="utf-8") as f:
        data: dict = json.load(f)
    return [LLMProviderConfig.from_dict(p) for p in data["providers"]]


def save_llm_providers(configs: list[LLMProviderConfig]) -> None:
    """LLMProviderConfig のリストを config/llm_providers.json に保存する。"""
    providers_path = PROJECT_ROOT / "config" / "llm_providers.json"
    data = {"providers": [c.to_dict() for c in configs]}
    with open(providers_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
