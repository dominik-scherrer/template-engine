"""Mapping between the canonical block tree and pandoc's block dicts.

This is the only place that knows pandoc's shape. Keeping it isolated is what
lets the Pandoc dependency sit at the edge of the system (ADR-0012): a pandoc
API change touches this file and nothing that is stored.

Unsupported constructs fail loudly. If Markdown carries an inline this catalogue
cannot represent yet (emphasis, a link), :func:`inlines_to_text` raises rather
than silently dropping it. Silent loss is the one outcome the round-trip gate
exists to prevent.
"""

from __future__ import annotations

from typing import Any

from template_engine.baum import Absatz, Block, Ueberschrift

# -- inlines -----------------------------------------------------------------

_EMPTY_ATTR = ["", [], []]


def text_to_inlines(text: str) -> list[dict[str, Any]]:
    """Canonical plain text to pandoc inlines: words as Str, gaps as Space.

    Escaping of Markdown-special characters is pandoc's job on the way out and
    back, so ``"a*b"`` survives as literal text.
    """
    if text == "":
        return []
    woerter = text.split(" ")
    inlines: list[dict[str, Any]] = []
    for i, w in enumerate(woerter):
        if i:
            inlines.append({"t": "Space"})
        inlines.append({"t": "Str", "c": w})
    return inlines


def inlines_to_text(inlines: list[dict[str, Any]]) -> str:
    teile: list[str] = []
    for inl in inlines:
        t = inl.get("t")
        if t == "Str":
            teile.append(inl["c"])
        elif t in ("Space", "SoftBreak"):
            teile.append(" ")
        else:
            raise ValueError(f"unsupported inline for this block catalogue: {t!r}")
    return "".join(teile)


# -- blocks ------------------------------------------------------------------


def block_to_pandoc(b: Block) -> dict[str, Any]:
    if isinstance(b, Ueberschrift):
        return {"t": "Header", "c": [b.ebene, _EMPTY_ATTR, text_to_inlines(b.text)]}
    if isinstance(b, Absatz):
        return {"t": "Para", "c": text_to_inlines(b.text)}
    raise ValueError(f"unsupported block type: {type(b).__name__}")


def pandoc_to_block(node: dict[str, Any]) -> Block:
    t = node.get("t")
    if t == "Header":
        ebene, _attr, inlines = node["c"]
        return Ueberschrift(ebene=int(ebene), text=inlines_to_text(inlines))
    if t in ("Para", "Plain"):
        return Absatz(text=inlines_to_text(node["c"]))
    raise ValueError(f"unsupported block for this catalogue: {t!r}")


def baum_zu_pandoc(bloecke: list[Block]) -> list[dict[str, Any]]:
    return [block_to_pandoc(b) for b in bloecke]


def pandoc_zu_baum(blocks: list[dict[str, Any]]) -> list[Block]:
    return [pandoc_to_block(n) for n in blocks]
