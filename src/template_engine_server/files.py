"""Rendered documents, kept for a limited time and served by unguessable link.

Each rendered file sits in its own directory named by a random token. The link
is ``<public_url>/files/<token>/<filename>``. Files older than ``ttl_seconds``
are removed whenever a new one is stored.
"""

from __future__ import annotations

import re
import secrets
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

__all__ = ["RenderedFiles", "StoredFile", "safe_filename"]

_TOKEN = re.compile(r"^[A-Za-z0-9_-]{20,64}$")
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(name: str | None, default: str = "document.docx") -> str:
    """A plain ``.docx`` filename with no path parts or odd characters."""
    stem = Path(name or "").stem if name else ""
    stem = _UNSAFE.sub("-", stem).strip(".-")[:80]
    return f"{stem or Path(default).stem}.docx"


@dataclass(frozen=True)
class StoredFile:
    token: str
    filename: str
    path: Path
    expires_at: float


class RenderedFiles:
    def __init__(self, root: str | Path, ttl_seconds: int = 24 * 3600) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl_seconds

    def put(self, data: bytes, filename: str) -> StoredFile:
        self.cleanup()
        token = secrets.token_urlsafe(24)
        d = self.root / token
        d.mkdir()
        name = safe_filename(filename)
        pfad = d / name
        pfad.write_bytes(data)
        return StoredFile(token, name, pfad, time.time() + self.ttl)

    def resolve(self, token: str, filename: str) -> Path | None:
        """The file behind a link, or None if unknown, expired or malformed."""
        if not _TOKEN.match(token) or filename != safe_filename(filename):
            return None
        pfad = self.root / token / filename
        if not pfad.is_file() or self._expired(pfad.parent):
            return None
        return pfad

    def _expired(self, d: Path) -> bool:
        return time.time() - d.stat().st_mtime > self.ttl

    def cleanup(self) -> None:
        for d in self.root.iterdir():
            if d.is_dir() and _TOKEN.match(d.name) and self._expired(d):
                shutil.rmtree(d, ignore_errors=True)
