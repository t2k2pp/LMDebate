"""添付ファイルデータモデル"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import uuid4


class FileType(Enum):
    PDF = "pdf"
    TEXT = "text"
    IMAGE = "image"
    MARKDOWN = "markdown"
    CSV = "csv"


EXTENSION_TO_FILETYPE = {
    ".pdf": FileType.PDF,
    ".txt": FileType.TEXT,
    ".md": FileType.MARKDOWN,
    ".csv": FileType.CSV,
    ".png": FileType.IMAGE,
    ".jpg": FileType.IMAGE,
    ".jpeg": FileType.IMAGE,
    ".gif": FileType.IMAGE,
    ".webp": FileType.IMAGE,
}

SUPPORTED_EXTENSIONS = set(EXTENSION_TO_FILETYPE.keys())


@dataclass
class Attachment:
    debate_id: str
    participant_role: str  # proposer_a / proposer_b / judge
    original_filename: str
    stored_filename: str
    file_type: FileType
    file_size: int = 0
    extracted_text: str | None = None
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "debate_id": self.debate_id,
            "participant_role": self.participant_role,
            "original_filename": self.original_filename,
            "stored_filename": self.stored_filename,
            "file_type": self.file_type.value,
            "file_size": self.file_size,
            "extracted_text": self.extracted_text,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Attachment":
        return cls(
            id=data["id"],
            debate_id=data["debate_id"],
            participant_role=data["participant_role"],
            original_filename=data["original_filename"],
            stored_filename=data["stored_filename"],
            file_type=FileType(data["file_type"]),
            file_size=data.get("file_size", 0),
            extracted_text=data.get("extracted_text"),
            created_at=datetime.fromisoformat(data["created_at"]) if isinstance(data.get("created_at"), str) else data.get("created_at", datetime.now()),
        )
