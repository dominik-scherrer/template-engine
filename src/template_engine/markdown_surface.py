"""The Markdown editing surface for a content document.

Markdown is a *projection* of the canonical tree, never a second source of truth
(ADR-0002). People and language models read and write Markdown; the tree is what
is stored and rendered.

The document body goes through pandoc. Document metadata does not: it rides in a
small front-matter block handled here, so that pandoc only ever sees body
content. For this first catalogue, metadata values are ``str``, ``int`` or
``bool``.
"""

from __future__ import annotations

from template_engine._pandoc import blocks_to_markdown, markdown_to_blocks
from template_engine.baum import (
    Absatz,
    Aufzaehlung,
    Block,
    Dokument,
    NummerierteListe,
    Ueberschrift,
    normtext,
)
from template_engine.pandoc_ast import baum_zu_pandoc, pandoc_zu_baum

__all__ = ["to_markdown", "from_markdown"]

_FENCE = "---"


def _emit_frontmatter(metadaten: dict[str, object]) -> str:
    lines = [_FENCE]
    for key in metadaten:
        wert = metadaten[key]
        if isinstance(wert, bool):
            s = "true" if wert else "false"
        elif isinstance(wert, (int, str)):
            s = str(wert)
        else:
            raise ValueError(
                f"metadata value for {key!r} must be str, int or bool, got {type(wert).__name__}"
            )
        if "\n" in s:
            raise ValueError(f"metadata value for {key!r} must be single-line")
        lines.append(f"{key}: {s}")
    lines.append(_FENCE)
    return "\n".join(lines)


def _parse_scalar(s: str) -> object:
    if s == "true":
        return True
    if s == "false":
        return False
    try:
        return int(s)
    except ValueError:
        return s


def _split_frontmatter(text: str) -> tuple[dict[str, object], str]:
    if not text.startswith(_FENCE + "\n"):
        return {}, text
    rest = text[len(_FENCE) + 1 :]
    ende = rest.find("\n" + _FENCE)
    if ende == -1:
        return {}, text
    block = rest[:ende]
    body = rest[ende + len("\n" + _FENCE) :]
    meta: dict[str, object] = {}
    for line in block.splitlines():
        if not line.strip():
            continue
        key, _, wert = line.partition(":")
        meta[key.strip()] = _parse_scalar(wert.strip())
    return meta, body.lstrip("\n")


def to_markdown(dok: Dokument) -> str:
    body = blocks_to_markdown(baum_zu_pandoc(dok.bloecke))
    if dok.metadaten:
        return _emit_frontmatter(dok.metadaten) + "\n\n" + body
    return body


def from_markdown(text: str) -> Dokument:
    metadaten, body = _split_frontmatter(text)
    bloecke = pandoc_zu_baum(markdown_to_blocks(body))
    # A tree returned by the surface is always canonical.
    bloecke = [_kanonisch(b) for b in bloecke]
    return Dokument(bloecke=bloecke, metadaten=metadaten)


def _kanonisch(b: Block) -> Block:
    if isinstance(b, Ueberschrift):
        return Ueberschrift(ebene=b.ebene, text=normtext(b.text))
    if isinstance(b, Absatz):
        return Absatz(text=normtext(b.text))
    if isinstance(b, Aufzaehlung):
        return Aufzaehlung(punkte=[normtext(x) for x in b.punkte])
    if isinstance(b, NummerierteListe):
        return NummerierteListe(punkte=[normtext(x) for x in b.punkte])
    return b
