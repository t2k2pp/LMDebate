"""ロールプリセットデータモデル"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import uuid4


class TargetRole(Enum):
    ANY = "any"
    PROPOSER = "proposer"
    JUDGE = "judge"


@dataclass
class RolePreset:
    name: str
    role_description: str = ""
    personality: str = ""
    guidelines: str = ""
    target_role: TargetRole = TargetRole.ANY
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "role_description": self.role_description,
            "personality": self.personality,
            "guidelines": self.guidelines,
            "target_role": self.target_role.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "RolePreset":
        return cls(
            id=data["id"],
            name=data["name"],
            role_description=data.get("role_description", ""),
            personality=data.get("personality", ""),
            guidelines=data.get("guidelines", ""),
            target_role=TargetRole(data.get("target_role", "any")),
            created_at=datetime.fromisoformat(data["created_at"]) if isinstance(data.get("created_at"), str) else data.get("created_at", datetime.now()),
            updated_at=datetime.fromisoformat(data["updated_at"]) if isinstance(data.get("updated_at"), str) else data.get("updated_at", datetime.now()),
        )
