"""ディベート履歴のSQLite永続化サービス"""

import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from src.models.debate import Debate, DebateStatus
from src.models.participant import Participant, ParticipantRole, ParticipantType
from src.models.message import Message, MessageType
from src.models.attachment import Attachment, FileType


class HistoryService:
    """SQLiteを使用したディベート履歴の保存・読み込みサービス"""

    def __init__(self, db_path: str) -> None:
        db_file = Path(db_path)
        db_file.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(db_file), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._lock = threading.Lock()
        self.init_db()

    # ------------------------------------------------------------------
    # Schema initialisation
    # ------------------------------------------------------------------

    def init_db(self) -> None:
        """全テーブルをIF NOT EXISTSで作成する"""
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS role_presets (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    role_description TEXT NOT NULL DEFAULT '',
                    personality TEXT NOT NULL DEFAULT '',
                    guidelines TEXT NOT NULL DEFAULT '',
                    target_role TEXT NOT NULL DEFAULT 'any',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS debates (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    proposal_x TEXT NOT NULL,
                    proposal_y TEXT NOT NULL,
                    judge_instruction TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'pending',
                    max_rounds INTEGER NOT NULL DEFAULT 5,
                    current_round INTEGER NOT NULL DEFAULT 0,
                    winner TEXT,
                    created_at TEXT NOT NULL,
                    completed_at TEXT
                );

                CREATE TABLE IF NOT EXISTS participants (
                    id TEXT PRIMARY KEY,
                    debate_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    llm_provider TEXT,
                    llm_model TEXT,
                    preset_id TEXT,
                    custom_role_desc TEXT,
                    custom_personality TEXT,
                    custom_guidelines TEXT,
                    max_tokens_per_turn INTEGER NOT NULL DEFAULT 500,
                    include_own_thinking INTEGER NOT NULL DEFAULT 1,
                    FOREIGN KEY (debate_id) REFERENCES debates(id),
                    FOREIGN KEY (preset_id) REFERENCES role_presets(id)
                );

                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    debate_id TEXT NOT NULL,
                    participant_id TEXT NOT NULL,
                    round_number INTEGER NOT NULL,
                    message_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    token_count INTEGER DEFAULT 0,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (debate_id) REFERENCES debates(id),
                    FOREIGN KEY (participant_id) REFERENCES participants(id)
                );

                CREATE TABLE IF NOT EXISTS attachments (
                    id TEXT PRIMARY KEY,
                    debate_id TEXT NOT NULL,
                    participant_role TEXT NOT NULL,
                    original_filename TEXT NOT NULL,
                    stored_filename TEXT NOT NULL,
                    file_type TEXT NOT NULL,
                    file_size INTEGER NOT NULL DEFAULT 0,
                    extracted_text TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (debate_id) REFERENCES debates(id)
                );

                CREATE INDEX IF NOT EXISTS idx_messages_debate
                    ON messages(debate_id, round_number);
                CREATE INDEX IF NOT EXISTS idx_participants_debate
                    ON participants(debate_id);
                CREATE INDEX IF NOT EXISTS idx_attachments_debate
                    ON attachments(debate_id, participant_role);
                """
            )

            # Schema migration: Web検索カラム追加
            try:
                self._conn.execute(
                    "ALTER TABLE participants ADD COLUMN enable_web_search INTEGER NOT NULL DEFAULT 0"
                )
            except sqlite3.OperationalError:
                pass  # カラム既存

            try:
                self._conn.execute(
                    "ALTER TABLE participants ADD COLUMN max_search_count INTEGER NOT NULL DEFAULT 3"
                )
            except sqlite3.OperationalError:
                pass  # カラム既存

            self._conn.commit()

    # ------------------------------------------------------------------
    # Debate CRUD
    # ------------------------------------------------------------------

    def save_debate(self, debate: Debate) -> None:
        """ディベートを新規保存する"""
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO debates
                    (id, title, topic, proposal_x, proposal_y, judge_instruction,
                     status, max_rounds, current_round, winner, created_at, completed_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    debate.id,
                    debate.title,
                    debate.topic,
                    debate.proposal_x,
                    debate.proposal_y,
                    debate.judge_instruction,
                    debate.status.value,
                    debate.max_rounds,
                    debate.current_round,
                    debate.winner,
                    debate.created_at.isoformat(),
                    debate.completed_at.isoformat() if debate.completed_at else None,
                ),
            )
            self._conn.commit()

    def update_debate(self, debate: Debate) -> None:
        """既存ディベートを更新する"""
        with self._lock:
            self._conn.execute(
                """
                UPDATE debates
                SET title = ?,
                    topic = ?,
                    proposal_x = ?,
                    proposal_y = ?,
                    judge_instruction = ?,
                    status = ?,
                    max_rounds = ?,
                    current_round = ?,
                    winner = ?,
                    completed_at = ?
                WHERE id = ?
                """,
                (
                    debate.title,
                    debate.topic,
                    debate.proposal_x,
                    debate.proposal_y,
                    debate.judge_instruction,
                    debate.status.value,
                    debate.max_rounds,
                    debate.current_round,
                    debate.winner,
                    debate.completed_at.isoformat() if debate.completed_at else None,
                    debate.id,
                ),
            )
            self._conn.commit()

    def get_debate(self, debate_id: str) -> Debate | None:
        """IDでディベートを取得する。見つからなければNone"""
        with self._lock:
            cur = self._conn.execute("SELECT * FROM debates WHERE id = ?", (debate_id,))
            row = cur.fetchone()
        if row is None:
            return None
        return self._row_to_debate(row)

    def list_debates(self) -> list[Debate]:
        """全ディベートをcreated_at降順で取得する"""
        with self._lock:
            cur = self._conn.execute("SELECT * FROM debates ORDER BY created_at DESC")
            rows = cur.fetchall()
        return [self._row_to_debate(row) for row in rows]

    # ------------------------------------------------------------------
    # Participant CRUD
    # ------------------------------------------------------------------

    def save_participant(self, participant: Participant) -> None:
        """参加者を保存する"""
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO participants
                    (id, debate_id, role, name, type, llm_provider, llm_model,
                     preset_id, custom_role_desc, custom_personality, custom_guidelines,
                     max_tokens_per_turn, include_own_thinking,
                     enable_web_search, max_search_count)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    participant.id,
                    participant.debate_id,
                    participant.role.value,
                    participant.name,
                    participant.type.value,
                    participant.llm_provider,
                    participant.llm_model,
                    participant.preset_id,
                    participant.custom_role_desc,
                    participant.custom_personality,
                    participant.custom_guidelines,
                    participant.max_tokens_per_turn,
                    1 if participant.include_own_thinking else 0,
                    1 if participant.enable_web_search else 0,
                    participant.max_search_count,
                ),
            )
            self._conn.commit()

    def get_participants(self, debate_id: str) -> list[Participant]:
        """ディベートIDに紐づく参加者一覧を取得する"""
        with self._lock:
            cur = self._conn.execute(
                "SELECT * FROM participants WHERE debate_id = ?", (debate_id,)
            )
            rows = cur.fetchall()
        return [self._row_to_participant(row) for row in rows]

    # ------------------------------------------------------------------
    # Message CRUD
    # ------------------------------------------------------------------

    def save_message(self, message: Message) -> None:
        """メッセージを保存する"""
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO messages
                    (id, debate_id, participant_id, round_number, message_type,
                     content, token_count, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message.id,
                    message.debate_id,
                    message.participant_id,
                    message.round_number,
                    message.message_type.value,
                    message.content,
                    message.token_count,
                    message.created_at.isoformat(),
                ),
            )
            self._conn.commit()

    def get_messages(
        self, debate_id: str, round_number: int | None = None
    ) -> list[Message]:
        """ディベートIDに紐づくメッセージを取得する。round_number指定時はそのラウンドのみ"""
        with self._lock:
            if round_number is not None:
                cur = self._conn.execute(
                    "SELECT * FROM messages WHERE debate_id = ? AND round_number = ? ORDER BY created_at",
                    (debate_id, round_number),
                )
            else:
                cur = self._conn.execute(
                    "SELECT * FROM messages WHERE debate_id = ? ORDER BY round_number, created_at",
                    (debate_id,),
                )
            rows = cur.fetchall()
        return [self._row_to_message(row) for row in rows]

    # ------------------------------------------------------------------
    # Attachment CRUD
    # ------------------------------------------------------------------

    def save_attachment(self, attachment: Attachment) -> None:
        """添付ファイルメタデータを保存する"""
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO attachments
                    (id, debate_id, participant_role, original_filename, stored_filename,
                     file_type, file_size, extracted_text, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    attachment.id,
                    attachment.debate_id,
                    attachment.participant_role,
                    attachment.original_filename,
                    attachment.stored_filename,
                    attachment.file_type.value,
                    attachment.file_size,
                    attachment.extracted_text,
                    attachment.created_at.isoformat(),
                ),
            )
            self._conn.commit()

    def get_attachments(
        self, debate_id: str, participant_role: str | None = None
    ) -> list[Attachment]:
        """ディベートIDに紐づく添付ファイルを取得する。participant_role指定時はそのロールのみ"""
        with self._lock:
            if participant_role is not None:
                cur = self._conn.execute(
                    "SELECT * FROM attachments WHERE debate_id = ? AND participant_role = ? ORDER BY created_at",
                    (debate_id, participant_role),
                )
            else:
                cur = self._conn.execute(
                    "SELECT * FROM attachments WHERE debate_id = ? ORDER BY created_at",
                    (debate_id,),
                )
            rows = cur.fetchall()
        return [self._row_to_attachment(row) for row in rows]

    # ------------------------------------------------------------------
    # Delete (cascading)
    # ------------------------------------------------------------------

    def delete_debate(self, debate_id: str) -> None:
        """ディベートとそれに紐づく参加者・メッセージ・添付ファイルを削除する"""
        with self._lock:
            self._conn.execute(
                "DELETE FROM messages WHERE debate_id = ?", (debate_id,)
            )
            self._conn.execute(
                "DELETE FROM attachments WHERE debate_id = ?", (debate_id,)
            )
            self._conn.execute(
                "DELETE FROM participants WHERE debate_id = ?", (debate_id,)
            )
            self._conn.execute("DELETE FROM debates WHERE id = ?", (debate_id,))
            self._conn.commit()

    # ------------------------------------------------------------------
    # Row -> Model converters
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_debate(row: sqlite3.Row) -> Debate:
        return Debate(
            id=row["id"],
            title=row["title"],
            topic=row["topic"],
            proposal_x=row["proposal_x"],
            proposal_y=row["proposal_y"],
            judge_instruction=row["judge_instruction"],
            status=DebateStatus(row["status"]),
            max_rounds=row["max_rounds"],
            current_round=row["current_round"],
            winner=row["winner"],
            created_at=datetime.fromisoformat(row["created_at"]),
            completed_at=(
                datetime.fromisoformat(row["completed_at"])
                if row["completed_at"]
                else None
            ),
        )

    @staticmethod
    def _row_to_participant(row: sqlite3.Row) -> Participant:
        # 後方互換: enable_web_search / max_search_count カラムが存在しない場合に備える
        keys = row.keys()
        return Participant(
            id=row["id"],
            debate_id=row["debate_id"],
            role=ParticipantRole(row["role"]),
            name=row["name"],
            type=ParticipantType(row["type"]),
            llm_provider=row["llm_provider"],
            llm_model=row["llm_model"],
            preset_id=row["preset_id"],
            custom_role_desc=row["custom_role_desc"],
            custom_personality=row["custom_personality"],
            custom_guidelines=row["custom_guidelines"],
            max_tokens_per_turn=row["max_tokens_per_turn"],
            include_own_thinking=bool(row["include_own_thinking"]),
            enable_web_search=bool(row["enable_web_search"]) if "enable_web_search" in keys else False,
            max_search_count=row["max_search_count"] if "max_search_count" in keys else 3,
        )

    @staticmethod
    def _row_to_message(row: sqlite3.Row) -> Message:
        return Message(
            id=row["id"],
            debate_id=row["debate_id"],
            participant_id=row["participant_id"],
            round_number=row["round_number"],
            message_type=MessageType(row["message_type"]),
            content=row["content"],
            token_count=row["token_count"] or 0,
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    @staticmethod
    def _row_to_attachment(row: sqlite3.Row) -> Attachment:
        return Attachment(
            id=row["id"],
            debate_id=row["debate_id"],
            participant_role=row["participant_role"],
            original_filename=row["original_filename"],
            stored_filename=row["stored_filename"],
            file_type=FileType(row["file_type"]),
            file_size=row["file_size"] or 0,
            extracted_text=row["extracted_text"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )
