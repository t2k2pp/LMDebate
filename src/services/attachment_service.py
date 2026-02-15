"""添付ファイル管理サービス"""

import os
import shutil
from pathlib import Path
from uuid import uuid4

from src.models.attachment import (
    Attachment,
    FileType,
    EXTENSION_TO_FILETYPE,
    SUPPORTED_EXTENSIONS,
)


class AttachmentService:
    """添付ファイルの保存・テキスト抽出を管理する。"""

    def __init__(self, attachments_dir: str):
        self._base_dir = Path(attachments_dir)

    def save_file(
        self,
        debate_id: str,
        participant_role: str,
        source_path: str,
    ) -> Attachment:
        """ファイルをコピー保存し、テキスト抽出を行う。"""
        source = Path(source_path)
        ext = source.suffix.lower()

        if ext not in SUPPORTED_EXTENSIONS:
            raise ValueError(f"非対応のファイル形式: {ext}")

        file_type = EXTENSION_TO_FILETYPE[ext]
        stored_name = f"{uuid4()}{ext}"
        dest_dir = self._base_dir / debate_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / stored_name

        shutil.copy2(source_path, dest_path)

        file_size = dest_path.stat().st_size
        extracted_text = self._extract_text(dest_path, file_type)

        return Attachment(
            debate_id=debate_id,
            participant_role=participant_role,
            original_filename=source.name,
            stored_filename=stored_name,
            file_type=file_type,
            file_size=file_size,
            extracted_text=extracted_text,
        )

    def _extract_text(self, file_path: Path, file_type: FileType) -> str | None:
        """ファイルからテキストを抽出する。"""
        try:
            if file_type == FileType.TEXT:
                return file_path.read_text(encoding="utf-8")
            elif file_type == FileType.MARKDOWN:
                return file_path.read_text(encoding="utf-8")
            elif file_type == FileType.CSV:
                return file_path.read_text(encoding="utf-8")
            elif file_type == FileType.PDF:
                return self._extract_pdf_text(file_path)
            elif file_type == FileType.IMAGE:
                # 画像はテキスト抽出不可（マルチモーダルLLM用にパスを保持）
                return None
        except Exception:
            return None
        return None

    def _extract_pdf_text(self, file_path: Path) -> str | None:
        """PDFからテキストを抽出する。"""
        try:
            from PyPDF2 import PdfReader

            reader = PdfReader(str(file_path))
            texts = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    texts.append(text)
            return "\n".join(texts) if texts else None
        except ImportError:
            return "[PDF読み込みにはPyPDF2が必要です]"
        except Exception:
            return None

    def get_file_path(self, debate_id: str, stored_filename: str) -> Path:
        """保存済みファイルのパスを返す。"""
        return self._base_dir / debate_id / stored_filename

    def delete_debate_files(self, debate_id: str) -> None:
        """ディベートに紐づく全添付ファイルを削除する。"""
        target_dir = self._base_dir / debate_id
        if target_dir.exists():
            shutil.rmtree(target_dir)
