"""Checks a role mapping against its base document before it is stored.

The check is a trial render of one block per mapped role, so it fails for
exactly the reasons a real render would (ADR-0006), with the library's own
messages.
"""

from __future__ import annotations

import template_engine as te
from template_engine.baum import Block

__all__ = ["probe_document", "check_profile", "prepare", "ProfileInvalid"]


class ProfileInvalid(ValueError):
    """The mapping cannot be rendered against the base document."""


def probe_document(profile: te.StyleProfile) -> te.Dokument:
    bloecke: list[Block] = []
    for rolle in profile.rollen:
        if rolle.startswith("ueberschrift_"):
            stufe = rolle.removeprefix("ueberschrift_")
            if stufe.isdigit():
                bloecke.append(te.Ueberschrift(ebene=int(stufe), text=f"Heading {stufe}"))
        elif rolle == "fliesstext":
            bloecke.append(te.Absatz(text="Body text."))
        elif rolle == "aufzaehlung":
            bloecke.append(te.Aufzaehlung(punkte=["Bullet item"]))
        elif rolle == "nummerierte_liste":
            bloecke.append(te.NummerierteListe(punkte=["Numbered item"]))
    return te.Dokument(bloecke=bloecke)


def check_profile(profile: te.StyleProfile, base_docx: bytes) -> None:
    """Raise :class:`ProfileInvalid` unless every mapped role renders and the
    body boundary fits the base document."""
    prepare(profile, base_docx)


def prepare(profile: te.StyleProfile, base_docx: bytes) -> bytes:
    """Check the profile against ``base_docx`` and return the prepared base
    document to store: the boundary bookmark written in (ADR-0009). Raises
    :class:`ProfileInvalid`."""
    if not profile.rollen:
        raise ProfileInvalid("the mapping is empty")
    if "fliesstext" not in profile.rollen:
        raise ProfileInvalid("the mapping has no style for body text ('fliesstext')")
    try:
        vorbereitet = (
            te.bereite_vor(base_docx, profile.koerpergrenze)
            if profile.koerpergrenze is not None
            else base_docx
        )
        te.render(probe_document(profile), profile, vorbereitet)
    except (te.RenderFehler, te.ZonenFehler) as e:
        raise ProfileInvalid(str(e)) from e
    return vorbereitet
