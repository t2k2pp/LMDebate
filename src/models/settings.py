"""設定データモデル"""

from dataclasses import dataclass


@dataclass
class AppSettings:
    theme: str = "dark"
    language: str = "ja"
    export_dir: str = "./exports"
    db_path: str = "./data/debates.db"
    attachments_dir: str = "./data/attachments"
    max_attachment_size_mb: int = 50
    max_attachments_per_participant: int = 5
    default_max_rounds: int = 5
    default_max_tokens_per_turn: int = 500
    default_c_skip_timeout_sec: int = 5
    default_include_own_thinking: bool = True

    @classmethod
    def from_dict(cls, data: dict) -> "AppSettings":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})


@dataclass
class LLMProviderConfig:
    id: str
    name: str
    type: str
    default_max_tokens: int = 500
    default_temperature: float = 0.7
    # Azure OpenAI
    deployment_name: str | None = None
    api_version: str | None = None
    # Anthropic / Ollama
    model: str | None = None
    # Local providers
    base_url: str | None = None

    @classmethod
    def from_dict(cls, data: dict) -> "LLMProviderConfig":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
