"""Server-side profile store (ADR-0014).

A profile version is the role mapping and the base document, stored together
and never changed afterwards. Approval status is the one mutable thing, and it
lives in ``meta.json`` beside the version, never inside ``profile.json``, so
approving a version does not change what that version is (ADR-0004).

Layout of :class:`DirectoryProfileStore`::

    <root>/<client>/<template>/v<n>/
        profile.json    the role mapping (StyleProfile)
        base.docx       the base document the renderer opens
        original<.ext>  the file as uploaded, kept for traceability (ADR-0009)
        meta.json       status, source, timestamps
"""

from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Protocol

from template_engine import StyleProfile

__all__ = [
    "Status",
    "VersionInfo",
    "ProfileSummary",
    "StoredProfile",
    "ProfileStore",
    "DirectoryProfileStore",
    "ProfileNotFound",
    "ProfileUnavailable",
    "validate_name",
]

Status = Literal["unapproved", "approved", "deactivated"]
STATUSES: tuple[Status, ...] = ("unapproved", "approved", "deactivated")

_SEGMENT = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_VERSION_DIR = re.compile(r"^v([1-9][0-9]*)$")


class ProfileNotFound(LookupError):
    """No such profile, or no such version of it."""


class ProfileUnavailable(LookupError):
    """The profile exists but has no version that may be rendered."""


def validate_name(name: str) -> tuple[str, str]:
    """A profile name is ``<client>/<template>``: lowercase letters, digits,
    ``-`` and ``_``. Returns the two segments."""
    teile = name.split("/")
    if len(teile) != 2 or not all(_SEGMENT.match(t) for t in teile):
        raise ValueError(
            f"invalid profile name {name!r}: expected '<client>/<template>', "
            "lowercase letters, digits, '-' and '_'"
        )
    return teile[0], teile[1]


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(frozen=True)
class VersionInfo:
    name: str
    version: int
    status: Status
    created_at: str
    source: str
    approved_at: str | None = None
    original_filename: str | None = None

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class ProfileSummary:
    name: str
    versions: list[VersionInfo]

    @property
    def latest(self) -> VersionInfo | None:
        """The newest version that may be rendered (not deactivated)."""
        aktiv = [v for v in self.versions if v.status != "deactivated"]
        return aktiv[-1] if aktiv else None


@dataclass(frozen=True)
class StoredProfile:
    info: VersionInfo
    profile: StyleProfile
    base_docx: bytes


class ProfileStore(Protocol):
    def profiles(self) -> list[ProfileSummary]: ...

    def get(self, name: str, version: int | None = None) -> StoredProfile: ...

    def publish(
        self,
        name: str,
        profile: StyleProfile,
        base_docx: bytes,
        *,
        source: str,
        original: bytes | None = None,
        original_filename: str | None = None,
        status: Status = "unapproved",
    ) -> VersionInfo: ...

    def set_status(self, name: str, version: int, status: Status) -> VersionInfo: ...


class DirectoryProfileStore:
    """A :class:`ProfileStore` on a plain directory tree. Good enough for one
    server; replace it for anything that needs shared storage."""

    def __init__(self, root: str | os.PathLike[str]) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    # -- reading -------------------------------------------------------------

    def _profile_dir(self, name: str) -> Path:
        kunde, vorlage = validate_name(name)
        return self.root / kunde / vorlage

    def _versions(self, name: str) -> list[int]:
        d = self._profile_dir(name)
        if not d.is_dir():
            return []
        nummern = []
        for p in d.iterdir():
            m = _VERSION_DIR.match(p.name)
            if m and (p / "meta.json").is_file():
                nummern.append(int(m.group(1)))
        return sorted(nummern)

    def _info(self, name: str, version: int) -> VersionInfo:
        meta = json.loads(
            (self._profile_dir(name) / f"v{version}" / "meta.json").read_text(encoding="utf-8")
        )
        return VersionInfo(
            name=name,
            version=version,
            status=meta["status"],
            created_at=meta["created_at"],
            source=meta.get("source", "unknown"),
            approved_at=meta.get("approved_at"),
            original_filename=meta.get("original_filename"),
        )

    def profiles(self) -> list[ProfileSummary]:
        out = []
        for kunde in sorted(p for p in self.root.iterdir() if p.is_dir()):
            for vorlage in sorted(p for p in kunde.iterdir() if p.is_dir()):
                name = f"{kunde.name}/{vorlage.name}"
                try:
                    validate_name(name)
                except ValueError:
                    continue
                versionen = [self._info(name, v) for v in self._versions(name)]
                if versionen:
                    out.append(ProfileSummary(name=name, versions=versionen))
        return out

    def summary(self, name: str) -> ProfileSummary:
        versionen = [self._info(name, v) for v in self._versions(name)]
        if not versionen:
            raise ProfileNotFound(f"no profile named {name!r}")
        return ProfileSummary(name=name, versions=versionen)

    def get(self, name: str, version: int | None = None) -> StoredProfile:
        zusammenfassung = self.summary(name)
        if version is None:
            info = zusammenfassung.latest
            if info is None:
                raise ProfileUnavailable(f"every version of {name!r} is deactivated")
        else:
            treffer = [v for v in zusammenfassung.versions if v.version == version]
            if not treffer:
                raise ProfileNotFound(f"profile {name!r} has no version {version}")
            info = treffer[0]
            if info.status == "deactivated":
                raise ProfileUnavailable(f"{name!r} v{version} is deactivated")
        d = self._profile_dir(name) / f"v{info.version}"
        profil = StyleProfile.from_json((d / "profile.json").read_text(encoding="utf-8"))
        return StoredProfile(info=info, profile=profil, base_docx=(d / "base.docx").read_bytes())

    # -- writing -------------------------------------------------------------

    def publish(
        self,
        name: str,
        profile: StyleProfile,
        base_docx: bytes,
        *,
        source: str,
        original: bytes | None = None,
        original_filename: str | None = None,
        status: Status = "unapproved",
    ) -> VersionInfo:
        if status not in STATUSES:
            raise ValueError(f"unknown status {status!r}")
        ziel = self._profile_dir(name)
        ziel.mkdir(parents=True, exist_ok=True)

        # Write everything into a scratch directory first, then rename it into
        # place. A version directory therefore appears complete or not at all.
        tmp = ziel / f".tmp-{uuid.uuid4().hex}"
        tmp.mkdir()
        try:
            (tmp / "profile.json").write_text(profile.to_json(), encoding="utf-8")
            (tmp / "base.docx").write_bytes(base_docx)
            if original is not None:
                endung = Path(original_filename or "original.docx").suffix.lower() or ".docx"
                (tmp / f"original{endung}").write_bytes(original)
            meta = {
                "status": status,
                "created_at": _now(),
                "source": source,
                "approved_at": _now() if status == "approved" else None,
                "original_filename": original_filename,
            }
            (tmp / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
            for _ in range(20):
                naechste = (self._versions(name) or [0])[-1] + 1
                try:
                    tmp.rename(ziel / f"v{naechste}")
                except OSError:
                    continue  # another writer took that number; try the next
                return self._info(name, naechste)
            raise RuntimeError(f"could not allocate a version number for {name!r}")
        finally:
            if tmp.exists():
                shutil.rmtree(tmp, ignore_errors=True)

    def set_status(self, name: str, version: int, status: Status) -> VersionInfo:
        if status not in STATUSES:
            raise ValueError(f"unknown status {status!r}")
        pfad = self._profile_dir(name) / f"v{version}" / "meta.json"
        if not pfad.is_file():
            raise ProfileNotFound(f"profile {name!r} has no version {version}")
        meta = json.loads(pfad.read_text(encoding="utf-8"))
        meta["status"] = status
        meta["approved_at"] = _now() if status == "approved" else None
        tmp = pfad.with_name(f".meta-{uuid.uuid4().hex}.json")
        tmp.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        os.replace(tmp, pfad)
        return self._info(name, version)
