"""The style profile: the mapping from semantic role to a base document's style.

This is the minimal profile the renderer needs today: a role-to-style-name
mapping. The other parts the design calls for (the zone sequence, the capability
profile, the prepared base document) are deferred to the ingest work and are not
modelled here yet.

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

    def resolve(self, rolle: str) -> str:
        try:
            return self.rollen[rolle]
        except KeyError:
            raise UnbekannteRolle(f"the profile has no style for role {rolle!r}") from None

    def to_json(self) -> str:
        return json.dumps({"rollen": self.rollen}, ensure_ascii=False, indent=2)

    @classmethod
    def from_json(cls, text: str) -> StyleProfile:
        d = json.loads(text)
        rollen = d.get("rollen", {})
        if not isinstance(rollen, dict):
            raise ValueError("'rollen' must be an object of role -> style name")
        return cls(rollen={str(k): str(v) for k, v in rollen.items()})
