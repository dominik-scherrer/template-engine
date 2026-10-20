"""Uploaded templates that are not profiles yet.

An upload becomes a draft. The admin interface (and, later, the agent
onboarding tools of ADR-0014) proposes and tests a mapping against the draft,
then publishes it as a profile version. Drafts expire after ``ttl_seconds``.
"""

from __future__ import annotations

import json
import re
import secrets
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from template_engine import ingest

__all__ = ["Draft", "DraftStore", "DraftNotFound"]

_ID = re.compile(r"^[A-Za-z0-9_-]{16,64}$")


class DraftNotFound(LookupError):
    pass


@dataclass(frozen=True)
class Draft:
    id: str
    filename: str
    original: bytes
    base_docx: bytes  # the original with a template content type swapped for a document one


class DraftStore:
    def __init__(self, root: str | Path, ttl_seconds: int = 7 * 24 * 3600) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.ttl = ttl_seconds

    def create(self, data: bytes, filename: str) -> Draft:
        """Store an upload. Raises ValueError if it is not a Word document."""
        try:
            basis = ingest.als_dokument_bytes(data)
        except Exception as e:  # zipfile.BadZipFile, KeyError for a missing part
            raise ValueError("not a Word document (.docx or .dotx)") from e
        self.cleanup()
        draft_id = secrets.token_urlsafe(18)
        d = self.root / draft_id
        d.mkdir()
        (d / "original").write_bytes(data)
        (d / "meta.json").write_text(
            json.dumps({"filename": Path(filename).name or "template.docx"}), encoding="utf-8"
        )
        return Draft(draft_id, Path(filename).name, data, basis)

    def get(self, draft_id: str) -> Draft:
        if not _ID.match(draft_id):
            raise DraftNotFound(draft_id)
        d = self.root / draft_id
        if not (d / "original").is_file() or self._expired(d):
            raise DraftNotFound(draft_id)
        meta = json.loads((d / "meta.json").read_text(encoding="utf-8"))
        roh = (d / "original").read_bytes()
        return Draft(draft_id, meta["filename"], roh, ingest.als_dokument_bytes(roh))

    def delete(self, draft_id: str) -> None:
        if _ID.match(draft_id):
            shutil.rmtree(self.root / draft_id, ignore_errors=True)

    def _expired(self, d: Path) -> bool:
        return time.time() - d.stat().st_mtime > self.ttl

    def cleanup(self) -> None:
        for d in self.root.iterdir():
            if d.is_dir() and _ID.match(d.name) and self._expired(d):
                shutil.rmtree(d, ignore_errors=True)
