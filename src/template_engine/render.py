"""Render a content document into a base document, against named styles.

This is the core bet of the whole project (ADR-0001) made concrete: visual
fidelity is not reconstructed, it is inherited. The renderer opens the client's
base document, clears the region it is going to generate while leaving the
document's styles, numbering, headers, footers and section properties untouched,
and writes each block as a paragraph carrying the client's own named style.

Scope of this increment: the base document is treated as a single generated
zone (its whole body is regenerated). The zone model of ADR-0008, where a
retained front such as a title page is kept and only a marked body region is
regenerated, arrives with the ingest work; the sectPr-preserving clear built
here is the mechanism that increment will reuse.

python-docx is the substrate (ADR-0011). Rendering is deterministic and calls no
model.
"""

from __future__ import annotations

import io
from typing import Any, cast

from docx import Document
from docx.document import Document as DocxDocument
from docx.oxml.ns import qn

from template_engine.baum import (
    Absatz,
    Aufzaehlung,
    Block,
    Dokument,
    NummerierteListe,
    Ueberschrift,
)
from template_engine.fehler import FehlenderStil
from template_engine.stilprofil import StyleProfile

__all__ = ["render", "rolle_fuer_block"]


def rolle_fuer_block(b: Block) -> str:
    """The semantic role a block maps to. Heading level becomes part of the role."""
    if isinstance(b, Ueberschrift):
        return f"ueberschrift_{b.ebene}"
    if isinstance(b, Absatz):
        return "fliesstext"
    if isinstance(b, Aufzaehlung):
        return "aufzaehlung"
    if isinstance(b, NummerierteListe):
        return "nummerierte_liste"
    raise ValueError(f"no role rule for block type {type(b).__name__}")


def _absatztexte(b: Block) -> list[str]:
    """The paragraph texts a block contributes. A list yields one per item, all
    sharing the block's single resolved style."""
    if isinstance(b, (Ueberschrift, Absatz)):
        return [b.text]
    if isinstance(b, (Aufzaehlung, NummerierteListe)):
        return list(b.punkte)
    raise ValueError(f"cannot render block type {type(b).__name__}")


def render(dokument: Dokument, profil: StyleProfile, basis_docx: bytes) -> bytes:
    """Render ``dokument`` into a copy of ``basis_docx`` and return the bytes.

    Raises :class:`UnbekannteRolle` if a block needs a role the profile does not
    map, and :class:`FehlenderStil` if a mapped style is absent from the base
    document. Both checks run before the document is touched, so a failure never
    leaves a half-rendered result.
    """
    doc = Document(io.BytesIO(basis_docx))

    vorhandene_stile = {s.name for s in doc.styles}

    # Resolve and check everything up front (ADR-0006): fail before mutating.
    plan: list[tuple[str, str]] = []  # (style name, text)
    for b in dokument.bloecke:
        rolle = rolle_fuer_block(b)
        stil = profil.resolve(rolle)  # raises UnbekannteRolle
        if stil not in vorhandene_stile:
            raise FehlenderStil(
                f"role {rolle!r} maps to style {stil!r}, which the base document does not define"
            )
        for text in _absatztexte(b):
            plan.append((stil, text))

    _leere_generierte_zone(doc)

    for stil, text in plan:
        doc.add_paragraph(text, style=stil)

    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def _leere_generierte_zone(doc: DocxDocument) -> None:
    """Remove block-level content from the body, keeping the trailing sectPr.

    The body-level ``sectPr`` is the last child of ``<w:body>`` and holds the
    section geometry; headers and footers live in section parts, not the body,
    so clearing paragraphs and tables leaves all of that intact. This is the
    recipe verified against python-docx before it was relied on here.
    """
    body = cast(Any, doc).element.body
    for child in list(body):
        if child.tag in (qn("w:p"), qn("w:tbl")):
            body.remove(child)
