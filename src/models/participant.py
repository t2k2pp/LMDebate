"""参加者データモデル"""

from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4


class ParticipantRole(Enum):
    PROPOSER_A = "proposer_a"
    PROPOSER_B = "proposer_b"
    JUDGE = "judge"


class ParticipantType(Enum):
    HUMAN = "human"
    LLM = "llm"


@dataclass
class Participant:
    debate_id: str
    role: ParticipantRole
    name: str
    type: ParticipantType
    llm_provider: str | None = None
    llm_model: str | None = None
    preset_id: str | None = None
    custom_role_desc: str | None = None
    custom_personality: str | None = None
    custom_guidelines: str | None = None
    max_tokens_per_turn: int = 500
    include_own_thinking: bool = True
    enable_web_search: bool = False
    max_search_count: int = 3
    id: str = field(default_factory=lambda: str(uuid4()))

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "debate_id": self.debate_id,
            "role": self.role.value,
            "name": self.name,
            "type": self.type.value,
            "llm_provider": self.llm_provider,
            "llm_model": self.llm_model,
            "preset_id": self.preset_id,
            "custom_role_desc": self.custom_role_desc,
            "custom_personality": self.custom_personality,
            "custom_guidelines": self.custom_guidelines,
            "max_tokens_per_turn": self.max_tokens_per_turn,
            "include_own_thinking": self.include_own_thinking,
            "enable_web_search": self.enable_web_search,
            "max_search_count": self.max_search_count,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Participant":
        return cls(
            id=data["id"],
            debate_id=data["debate_id"],
            role=ParticipantRole(data["role"]),
            name=data["name"],
            type=ParticipantType(data["type"]),
            llm_provider=data.get("llm_provider"),
            llm_model=data.get("llm_model"),
            preset_id=data.get("preset_id"),
            custom_role_desc=data.get("custom_role_desc"),
            custom_personality=data.get("custom_personality"),
            custom_guidelines=data.get("custom_guidelines"),
            max_tokens_per_turn=data.get("max_tokens_per_turn", 500),
            include_own_thinking=bool(data.get("include_own_thinking", True)),
            enable_web_search=bool(data.get("enable_web_search", False)),
            max_search_count=data.get("max_search_count", 3),
        )
