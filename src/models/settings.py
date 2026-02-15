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

    def to_dict(self) -> dict:
        """dict形式に変換する。None値のフィールドは除外する。"""
        result: dict = {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "default_max_tokens": self.default_max_tokens,
            "default_temperature": self.default_temperature,
        }
        if self.deployment_name is not None:
            result["deployment_name"] = self.deployment_name
        if self.api_version is not None:
            result["api_version"] = self.api_version
        if self.model is not None:
            result["model"] = self.model
        if self.base_url is not None:
            result["base_url"] = self.base_url
        return result
