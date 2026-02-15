"""メッセージデータモデル"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import uuid4


class MessageType(Enum):
    SPEECH = "speech"
    THINKING = "thinking"
    SKIP = "skip"
    JUDGMENT = "judgment"


@dataclass
class Message:
    debate_id: str
    participant_id: str
    round_number: int
    message_type: MessageType
    content: str
    token_count: int = 0
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "debate_id": self.debate_id,
            "participant_id": self.participant_id,
            "round_number": self.round_number,
            "message_type": self.message_type.value,
            "content": self.content,
            "token_count": self.token_count,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        return cls(
            id=data["id"],
            debate_id=data["debate_id"],
            participant_id=data["participant_id"],
            round_number=data["round_number"],
            message_type=MessageType(data["message_type"]),
            content=data["content"],
            token_count=data.get("token_count", 0),
            created_at=datetime.fromisoformat(data["created_at"]) if isinstance(data.get("created_at"), str) else data.get("created_at", datetime.now()),
        )
