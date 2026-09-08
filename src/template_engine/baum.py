"""The canonical block tree.

This is the project's own data model, deliberately not Pandoc's (see ADR-0012).
Domain types are named in the language of the authors (German); the surrounding
plumbing is English (see docs/GLOSSARY.md).

The tree carries *meaning*, never formatting: an ``Ueberschrift`` says "this is a
heading at level n", not "18pt bold". How that renders is decided elsewhere, by a
style profile.

A tree is *canonical* when its text nodes contain no leading or trailing
whitespace and no internal runs of whitespace. The Markdown surface only
guarantees a lossless round trip for canonical trees; ``normtext`` produces
canonical text and :func:`from_markdown` always returns a canonical tree.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "Block",
    "Dokument",
    "Ueberschrift",
    "Absatz",
    "Aufzaehlung",
    "NummerierteListe",
    "normtext",
    "block_from_dict",
    "BLOCK_REGISTRY",
]

_WS = re.compile(r"\s+")


def normtext(s: str) -> str:
    """Canonicalise a run of text: collapse whitespace, strip the ends.

    Whitespace normalisation is a property of the canonical form, not of any
    particular file format. Pandoc collapses whitespace on read, so a tree that
    kept ``"a  b"`` could never survive a Markdown round trip; the canonical tree
    simply does not contain such text.
    """
    return _WS.sub(" ", s).strip()


class Block:
    """Base class for every node that may appear in a document body.

    Subclasses are plain frozen dataclasses. Each declares a ``TYP`` string used
    as the discriminator in the serialised (JSON/YAML) form, and registers itself
    via :func:`_register`. Keeping the registry in one place is what makes adding
    a block type a localised change, as ADR-0002 requires.
    """

    TYP: str = ""

    def to_dict(self) -> dict[str, object]:  # pragma: no cover - overridden
        raise NotImplementedError

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Block:  # pragma: no cover - overridden
        raise NotImplementedError


BLOCK_REGISTRY: dict[str, type[Block]] = {}


def _register(cls: type[Block]) -> type[Block]:
    if not cls.TYP:
        raise ValueError(f"{cls.__name__} has no TYP")
    if cls.TYP in BLOCK_REGISTRY:
        raise ValueError(f"duplicate block TYP {cls.TYP!r}")
    BLOCK_REGISTRY[cls.TYP] = cls
    return cls


@_register
@dataclass(frozen=True)
class Ueberschrift(Block):
    """A heading. ``ebene`` is the outline level (1 = top)."""

    TYP = "ueberschrift"
    ebene: int
    text: str

    def to_dict(self) -> dict[str, object]:
        return {"typ": self.TYP, "ebene": self.ebene, "text": self.text}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Ueberschrift:
        return cls(ebene=int(d["ebene"]), text=str(d["text"]))


@_register
@dataclass(frozen=True)
class Absatz(Block):
    """A paragraph of plain text. No inline formatting in this catalogue yet."""

    TYP = "absatz"
    text: str

    def to_dict(self) -> dict[str, object]:
        return {"typ": self.TYP, "text": self.text}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Absatz:
        return cls(text=str(d["text"]))


@_register
@dataclass(frozen=True)
class Aufzaehlung(Block):
    """A bullet list. Single level, each point plain canonical text."""

    TYP = "aufzaehlung"
    punkte: list[str]

    def to_dict(self) -> dict[str, object]:
        return {"typ": self.TYP, "punkte": list(self.punkte)}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> Aufzaehlung:
        return cls(punkte=[str(x) for x in d["punkte"]])


@_register
@dataclass(frozen=True)
class NummerierteListe(Block):
    """An ordered list. Single level, decimal ``1.`` numbering, plain items."""

    TYP = "nummerierte_liste"
    punkte: list[str]

    def to_dict(self) -> dict[str, object]:
        return {"typ": self.TYP, "punkte": list(self.punkte)}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> NummerierteListe:
        return cls(punkte=[str(x) for x in d["punkte"]])


def block_from_dict(d: dict[str, Any]) -> Block:
    typ = d.get("typ")
    if not isinstance(typ, str) or typ not in BLOCK_REGISTRY:
        raise ValueError(f"unknown block typ {typ!r}")
    cls = BLOCK_REGISTRY[typ]
    return cls.from_dict(d)


@dataclass(frozen=True)
class Dokument:
    """A content document: metadata plus an ordered list of blocks.

    ``metadaten`` is orchestration data the caller owns (title, which style
    profile version to render against). It is carried by the JSON form and, in
    the Markdown surface, by a small front-matter block. The body itself is the
    block list.
    """

    bloecke: list[Block] = field(default_factory=list)
    metadaten: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "dokument": {
                "metadaten": dict(self.metadaten),
                "bloecke": [b.to_dict() for b in self.bloecke],
            }
        }

    @classmethod
    def from_dict(cls, d: dict[str, object]) -> Dokument:
        inner = d.get("dokument", d)
        assert isinstance(inner, dict)
        roh = inner.get("bloecke", [])
        assert isinstance(roh, list)
        meta = inner.get("metadaten", {})
        assert isinstance(meta, dict)
        return cls(
            bloecke=[block_from_dict(b) for b in roh],
            metadaten=dict(meta),
        )
