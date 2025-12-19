"""Attachment storage service for multi-modal memory.

Handles storing, retrieving, and managing file attachments for memories.
Supports images, audio, PDFs, and other file types.
"""

import hashlib
import logging
import mimetypes
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

from pydantic import BaseModel

logger = logging.getLogger(__name__)

# Base directory for attachments
ATTACHMENTS_DIR = Path.home() / ".thinkos" / "attachments"
ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)

# Thumbnail directory
THUMBNAILS_DIR = ATTACHMENTS_DIR / "thumbnails"
THUMBNAILS_DIR.mkdir(parents=True, exist_ok=True)

# Maximum file size (100MB)
MAX_FILE_SIZE = 100 * 1024 * 1024

# Allowed MIME types
ALLOWED_MIME_TYPES = {
    # Images
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/svg+xml",
    "image/bmp",
    "image/tiff",
    # Audio
    "audio/mpeg",
    "audio/wav",
    "audio/ogg",
    "audio/webm",
    "audio/flac",
    "audio/aac",
    "audio/mp4",
    # Video
    "video/mp4",
    "video/webm",
    "video/ogg",
    "video/quicktime",
    # Documents
    "application/pdf",
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/json",
    # Archives (for reference, not processed)
    "application/zip",
}


class AttachmentMetadata(BaseModel):
    """Metadata for a stored attachment."""
    id: str
    filename: str
    original_filename: str
    mime_type: str
    size_bytes: int
    hash_sha256: str
    created_at: datetime
    storage_path: str
    thumbnail_path: str | None = None
    extracted_text: str | None = None
    description: str | None = None
    width: int | None = None
    height: int | None = None
    duration_seconds: float | None = None


class AttachmentStorage:
    """Manages file attachment storage on local filesystem."""
    
    def __init__(self, base_dir: Path = ATTACHMENTS_DIR):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.thumbnails_dir = base_dir / "thumbnails"
        self.thumbnails_dir.mkdir(parents=True, exist_ok=True)
    
    def _generate_storage_path(self, attachment_id: str, extension: str) -> Path:
        """Generate a storage path using date-based directory structure."""
        now = datetime.utcnow()
        year_month = now.strftime("%Y/%m")
        dir_path = self.base_dir / year_month
        dir_path.mkdir(parents=True, exist_ok=True)
        return dir_path / f"{attachment_id}{extension}"
    
    def _compute_hash(self, file_path: Path) -> str:
        """Compute SHA-256 hash of a file."""
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    
    def _get_mime_type(self, filename: str, content: bytes | None = None) -> str:
        """Determine MIME type from filename or content."""
        mime_type, _ = mimetypes.guess_type(filename)
        if mime_type:
            return mime_type
        
        # Fallback to magic bytes detection if content provided
        if content:
            if content.startswith(b"\x89PNG"):
                return "image/png"
            elif content.startswith(b"\xff\xd8\xff"):
                return "image/jpeg"
            elif content.startswith(b"GIF8"):
                return "image/gif"
            elif content.startswith(b"RIFF") and b"WEBP" in content[:12]:
                return "image/webp"
            elif content.startswith(b"%PDF"):
                return "application/pdf"
            elif content.startswith(b"ID3") or content.startswith(b"\xff\xfb"):
                return "audio/mpeg"
        
        return "application/octet-stream"
    
    def _get_extension(self, mime_type: str, filename: str) -> str:
        """Get file extension from MIME type or filename."""
        # Try to get from filename first
        _, ext = os.path.splitext(filename)
        if ext:
            return ext.lower()
        
        # Fall back to MIME type
        extensions = mimetypes.guess_all_extensions(mime_type)
        if extensions:
            return extensions[0]
        
        return ""
    
    async def store(
        self,
        file: BinaryIO,
        filename: str,
        mime_type: str | None = None,
    ) -> AttachmentMetadata:
        """Store a file attachment.
        
        Args:
            file: File-like object to store
            filename: Original filename
            mime_type: MIME type (auto-detected if not provided)
            
        Returns:
            AttachmentMetadata with storage details
            
        Raises:
            ValueError: If file type not allowed or file too large
        """
        # Read file content
        content = file.read()
        size = len(content)
        
        # Check file size
        if size > MAX_FILE_SIZE:
            raise ValueError(f"File too large. Maximum size is {MAX_FILE_SIZE // (1024*1024)}MB")
        
        # Determine MIME type
        if not mime_type:
            mime_type = self._get_mime_type(filename, content)
        
        # Validate MIME type
        if mime_type not in ALLOWED_MIME_TYPES:
            raise ValueError(f"File type '{mime_type}' is not allowed")
        
        # Generate unique ID and storage path
        attachment_id = str(uuid.uuid4())
        extension = self._get_extension(mime_type, filename)
        storage_path = self._generate_storage_path(attachment_id, extension)
        
        # Write file
        with open(storage_path, "wb") as f:
            f.write(content)
        
        # Compute hash
        file_hash = self._compute_hash(storage_path)
        
        # Create metadata
        metadata = AttachmentMetadata(
            id=attachment_id,
            filename=storage_path.name,
            original_filename=filename,
            mime_type=mime_type,
            size_bytes=size,
            hash_sha256=file_hash,
            created_at=datetime.utcnow(),
            storage_path=str(storage_path),
        )
        
        logger.info(f"Stored attachment {attachment_id}: {filename} ({size} bytes)")
        return metadata
    
    async def store_from_path(self, source_path: Path, filename: str | None = None) -> AttachmentMetadata:
        """Store a file from a filesystem path.
        
        Args:
            source_path: Path to the source file
            filename: Optional filename override
            
        Returns:
            AttachmentMetadata with storage details
        """
        if not source_path.exists():
            raise FileNotFoundError(f"Source file not found: {source_path}")
        
        filename = filename or source_path.name
        
        with open(source_path, "rb") as f:
            return await self.store(f, filename)
    
    async def store_from_bytes(
        self,
        content: bytes,
        filename: str,
        mime_type: str | None = None,
    ) -> AttachmentMetadata:
        """Store a file from bytes.
        
        Args:
            content: File content as bytes
            filename: Filename for the attachment
            mime_type: MIME type (auto-detected if not provided)
            
        Returns:
            AttachmentMetadata with storage details
        """
        import io
        return await self.store(io.BytesIO(content), filename, mime_type)
    
    def get_path(self, attachment_id: str) -> Path | None:
        """Get the storage path for an attachment by ID.
        
        Searches the directory structure for the attachment.
        """
        # Search in all year/month directories
        for year_dir in self.base_dir.iterdir():
            if not year_dir.is_dir() or year_dir.name == "thumbnails":
                continue
            for month_dir in year_dir.iterdir():
                if not month_dir.is_dir():
                    continue
                for file_path in month_dir.iterdir():
                    if file_path.stem == attachment_id:
                        return file_path
        return None
    
    def get_content(self, attachment_id: str) -> bytes | None:
        """Get the content of an attachment by ID."""
        path = self.get_path(attachment_id)
        if path and path.exists():
            return path.read_bytes()
        return None
    
    def get_thumbnail_path(self, attachment_id: str) -> Path:
        """Get the thumbnail path for an attachment."""
        return self.thumbnails_dir / f"{attachment_id}_thumb.jpg"
    
    def delete(self, attachment_id: str) -> bool:
        """Delete an attachment and its thumbnail.
        
        Args:
            attachment_id: ID of the attachment to delete
            
        Returns:
            True if deleted, False if not found
        """
        path = self.get_path(attachment_id)
        if path and path.exists():
            path.unlink()
            
            # Also delete thumbnail if exists
            thumb_path = self.get_thumbnail_path(attachment_id)
            if thumb_path.exists():
                thumb_path.unlink()
            
            logger.info(f"Deleted attachment {attachment_id}")
            return True
        return False
    
    def get_storage_stats(self) -> dict:
        """Get storage statistics."""
        total_size = 0
        file_count = 0
        
        for root, dirs, files in os.walk(self.base_dir):
            # Skip thumbnails in count
            if "thumbnails" in root:
                continue
            for file in files:
                file_path = Path(root) / file
                total_size += file_path.stat().st_size
                file_count += 1
        
        return {
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "file_count": file_count,
            "storage_path": str(self.base_dir),
        }


# Singleton instance
_storage: AttachmentStorage | None = None


def get_attachment_storage() -> AttachmentStorage:
    """Get the attachment storage singleton."""
    global _storage
    if _storage is None:
        _storage = AttachmentStorage()
    return _storage
