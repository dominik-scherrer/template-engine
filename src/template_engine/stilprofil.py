"""The style profile: the mapping from semantic role to a base document's style.

Today the profile holds the role-to-style mapping and the body boundary of the
zone model (ADR-0008): the index of the first top-level block that is generated,
``None`` or ``0`` meaning the whole body is generated. The capability profile and
binding sites are not modelled yet.

Per ADR-0004 and ADR-0013 the profile is a serialisable value; the caller
persists and versions it. This class is that value; storage lives elsewhere.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from template_engine.fehler import UnbekannteRolle

__all__ = ["StyleProfile"]


@dataclass(frozen=True)
class StyleProfile:
    """Maps a semantic role (``ueberschrift_1``, ``fliesstext``) to the style
    name used for it in a particular client's base document (``"Titel 1"``)."""

    rollen: dict[str, str] = field(default_factory=dict)
    koerpergrenze: int | None = None

    def resolve(self, rolle: str) -> str:
        try:
            return self.rollen[rolle]
        except KeyError:
            raise UnbekannteRolle(f"the profile has no style for role {rolle!r}") from None

    def to_json(self) -> str:
        d: dict[str, object] = {"rollen": self.rollen}
        if self.koerpergrenze is not None:
            d["koerpergrenze"] = self.koerpergrenze
        return json.dumps(d, ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, text: str) -> StyleProfile:
        d = json.loads(text)
        rollen = d.get("rollen", {})
        if not isinstance(rollen, dict):
            raise ValueError("'rollen' must be an object of role -> style name")
        grenze = d.get("koerpergrenze")
        if grenze is not None and (isinstance(grenze, bool) or not isinstance(grenze, int)):
            raise ValueError("'koerpergrenze' must be a non-negative integer or null")
        if grenze is not None and grenze < 0:
            raise ValueError("'koerpergrenze' must be a non-negative integer or null")
        return cls(rollen={str(k): str(v) for k, v in rollen.items()}, koerpergrenze=grenze)
