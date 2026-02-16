"""ロールプリセット管理サービス"""

import json
from datetime import datetime
from pathlib import Path

from src.models.role_preset import RolePreset, TargetRole


class PresetService:
    """ロールプリセットのCRUD管理。JSONファイルとDB両方から読み込み可能。"""

    def __init__(self, history_service=None, presets_json_path: str | None = None):
        self._history_service = history_service
        self._presets_json_path = presets_json_path
        self._presets: list[RolePreset] = []
        self._load_presets()

    def _load_presets(self):
        """JSONファイルから初期プリセットを読み込み、DBに未登録のものを登録する。"""
        # JSONから読み込み
        if self._presets_json_path:
            json_path = Path(self._presets_json_path)
            if json_path.exists():
                with open(json_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for item in data.get("presets", []):
                    now = datetime.now().isoformat()
                    item.setdefault("created_at", now)
                    item.setdefault("updated_at", now)
                    preset = RolePreset.from_dict(item)
                    self._presets.append(preset)

        # DBからも読み込み（DB優先で上書き）
        if self._history_service:
            self._sync_with_db()

    def _sync_with_db(self):
        """JSONプリセットをDBに同期し、DB側の全プリセットで一覧を更新する。"""
        import sqlite3
        db = self._history_service

        # JSON由来のプリセットをDBに存在しなければ挿入
        for preset in self._presets:
            existing = self._get_preset_from_db(preset.id)
            if existing is None:
                self._save_preset_to_db(preset)

        # DBから全件読み込みで上書き
        self._presets = self._list_presets_from_db()

    def _get_preset_from_db(self, preset_id: str) -> RolePreset | None:
        with self._history_service._lock:
            conn = self._history_service._conn
            cursor = conn.execute("SELECT * FROM role_presets WHERE id = ?", (preset_id,))
            row = cursor.fetchone()
        if row is None:
            return None
        return self._row_to_preset(row)

    def _save_preset_to_db(self, preset: RolePreset):
        with self._history_service._lock:
            conn = self._history_service._conn
            conn.execute(
                """INSERT OR REPLACE INTO role_presets
                   (id, name, role_description, personality, guidelines, target_role, created_at, updated_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    preset.id,
                    preset.name,
                    preset.role_description,
                    preset.personality,
                    preset.guidelines,
                    preset.target_role.value,
                    preset.created_at.isoformat() if isinstance(preset.created_at, datetime) else preset.created_at,
                    preset.updated_at.isoformat() if isinstance(preset.updated_at, datetime) else preset.updated_at,
                ),
            )
            conn.commit()

    def _list_presets_from_db(self) -> list[RolePreset]:
        with self._history_service._lock:
            conn = self._history_service._conn
            cursor = conn.execute("SELECT * FROM role_presets ORDER BY name")
            rows = cursor.fetchall()
        return [self._row_to_preset(row) for row in rows]

    def _row_to_preset(self, row) -> RolePreset:
        return RolePreset(
            id=row[0],
            name=row[1],
            role_description=row[2],
            personality=row[3],
            guidelines=row[4],
            target_role=TargetRole(row[5]),
            created_at=datetime.fromisoformat(row[6]) if isinstance(row[6], str) else row[6],
            updated_at=datetime.fromisoformat(row[7]) if isinstance(row[7], str) else row[7],
        )

    def list_presets(self, target_role: TargetRole | None = None) -> list[RolePreset]:
        """プリセット一覧を取得する。target_roleでフィルタ可能。"""
        if target_role is None:
            return list(self._presets)
        return [
            p for p in self._presets
            if p.target_role == TargetRole.ANY or p.target_role == target_role
        ]

    def get_preset(self, preset_id: str) -> RolePreset | None:
        """IDでプリセットを取得する。"""
        for p in self._presets:
            if p.id == preset_id:
                return p
        return None

    def create_preset(self, preset: RolePreset) -> RolePreset:
        """新規プリセットを作成する。"""
        if self._history_service:
            self._save_preset_to_db(preset)
        self._presets.append(preset)
        return preset

    def update_preset(self, preset: RolePreset) -> RolePreset:
        """既存プリセットを更新する。"""
        preset.updated_at = datetime.now()
        if self._history_service:
            self._save_preset_to_db(preset)
        self._presets = [p if p.id != preset.id else preset for p in self._presets]
        return preset

    def delete_preset(self, preset_id: str) -> bool:
        """プリセットを削除する。"""
        if self._history_service:
            with self._history_service._lock:
                conn = self._history_service._conn
                conn.execute("DELETE FROM role_presets WHERE id = ?", (preset_id,))
                conn.commit()
        before = len(self._presets)
        self._presets = [p for p in self._presets if p.id != preset_id]
        return len(self._presets) < before
