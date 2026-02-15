"""ディベートデータモデル"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import uuid4


class DebateStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"


class Winner(Enum):
    A = "A"
    B = "B"
    DRAW = "draw"
    UNDECIDED = "undecided"


@dataclass
class Debate:
    title: str
    topic: str
    proposal_x: str
    proposal_y: str
    judge_instruction: str = ""
    status: DebateStatus = DebateStatus.PENDING
    max_rounds: int = 5
    current_round: int = 0
    winner: str | None = None
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "topic": self.topic,
            "proposal_x": self.proposal_x,
            "proposal_y": self.proposal_y,
            "judge_instruction": self.judge_instruction,
            "status": self.status.value,
            "max_rounds": self.max_rounds,
            "current_round": self.current_round,
            "winner": self.winner,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Debate":
        return cls(
            id=data["id"],
            title=data["title"],
            topic=data["topic"],
            proposal_x=data["proposal_x"],
            proposal_y=data["proposal_y"],
            judge_instruction=data.get("judge_instruction", ""),
            status=DebateStatus(data.get("status", "pending")),
            max_rounds=data.get("max_rounds", 5),
            current_round=data.get("current_round", 0),
            winner=data.get("winner"),
            created_at=datetime.fromisoformat(data["created_at"]) if isinstance(data.get("created_at"), str) else data.get("created_at", datetime.now()),
            completed_at=datetime.fromisoformat(data["completed_at"]) if isinstance(data.get("completed_at"), str) and data.get("completed_at") else None,
        )
