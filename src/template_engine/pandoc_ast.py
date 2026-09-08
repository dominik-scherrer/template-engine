"""Mapping between the canonical block tree and pandoc's block dicts.

This is the only place that knows pandoc's shape. Keeping it isolated is what
lets the Pandoc dependency sit at the edge of the system (ADR-0012): a pandoc
API change touches this file and nothing that is stored.

Two rules keep the mapping honest:

* Unsupported constructs fail loudly. An inline or block this catalogue cannot
  represent yet raises rather than being silently dropped. Silent loss is the
  one outcome the round-trip gate exists to prevent.
* Pandoc's own artefacts are absorbed. Between two adjacent lists of the same
  kind pandoc writes an HTML-comment separator (a ``RawBlock``); it is a
  rendering device, not content, so it is dropped on read. Any other raw block
  is treated as unsupported and raises.
"""

from __future__ import annotations

from typing import Any

from template_engine.baum import (
    Absatz,
    Aufzaehlung,
    Block,
    NummerierteListe,
    Ueberschrift,
)

_EMPTY_ATTR = ["", [], []]

# The list-attributes pandoc produces for a plain "1." decimal list. This
# catalogue supports only that; fancier numbering (a., i., parenthesised) is
# unsupported and made to fail loudly rather than be normalised away.
_DEFAULT_ORDERED_ATTR = [1, {"t": "Decimal"}, {"t": "Period"}]


# -- inlines -----------------------------------------------------------------


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


def _item_text(item: list[dict[str, Any]]) -> str:
    """A list item is one Plain (tight list). More than that is unsupported.

    Nested lists and multi-paragraph items are deliberately outside this
    catalogue for now; they raise instead of being flattened.
    """
    if len(item) != 1 or item[0].get("t") not in ("Plain", "Para"):
        raise ValueError("unsupported list item: expected a single tight paragraph")
    return inlines_to_text(item[0]["c"])


def _plain_item(text: str) -> list[dict[str, Any]]:
    return [{"t": "Plain", "c": text_to_inlines(text)}]


# -- blocks ------------------------------------------------------------------


def block_to_pandoc(b: Block) -> dict[str, Any]:
    if isinstance(b, Ueberschrift):
        # A heading whose text ends in "#" cannot round-trip: pandoc writes ATX
        # headings and its reader strips a trailing run of "#" as a closing
        # sequence. Refuse it loudly rather than lose the character silently.
        if b.text.endswith("#"):
            raise ValueError(
                "heading text ending in '#' cannot be represented in Markdown "
                "(pandoc ATX closing sequence)"
            )
        return {"t": "Header", "c": [b.ebene, _EMPTY_ATTR, text_to_inlines(b.text)]}
    if isinstance(b, Absatz):
        return {"t": "Para", "c": text_to_inlines(b.text)}
    if isinstance(b, Aufzaehlung):
        return {"t": "BulletList", "c": [_plain_item(p) for p in b.punkte]}
    if isinstance(b, NummerierteListe):
        return {
            "t": "OrderedList",
            "c": [list(_DEFAULT_ORDERED_ATTR), [_plain_item(p) for p in b.punkte]],
        }
    raise ValueError(f"unsupported block type: {type(b).__name__}")


def _ist_listentrenner(node: dict[str, Any]) -> bool:
    """True for pandoc's inter-list separator: a RawBlock holding an HTML comment."""
    if node.get("t") != "RawBlock":
        return False
    fmt, text = node["c"]
    return bool(fmt == "html" and text.strip().startswith("<!--"))


def pandoc_to_block(node: dict[str, Any]) -> Block:
    t = node.get("t")
    if t == "Header":
        ebene, _attr, inlines = node["c"]
        return Ueberschrift(ebene=int(ebene), text=inlines_to_text(inlines))
    if t in ("Para", "Plain"):
        return Absatz(text=inlines_to_text(node["c"]))
    if t == "BulletList":
        return Aufzaehlung(punkte=[_item_text(item) for item in node["c"]])
    if t == "OrderedList":
        attr, items = node["c"]
        if attr != _DEFAULT_ORDERED_ATTR:
            raise ValueError(f"unsupported ordered-list numbering: {attr!r}")
        return NummerierteListe(punkte=[_item_text(item) for item in items])
    if t == "RawBlock":
        raise ValueError("unsupported raw block")
    raise ValueError(f"unsupported block for this catalogue: {t!r}")


def baum_zu_pandoc(bloecke: list[Block]) -> list[dict[str, Any]]:
    return [block_to_pandoc(b) for b in bloecke]


def pandoc_zu_baum(blocks: list[dict[str, Any]]) -> list[Block]:
    return [pandoc_to_block(n) for n in blocks if not _ist_listentrenner(n)]
