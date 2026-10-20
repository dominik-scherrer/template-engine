"""Render a content document into a base document, against named styles.

This is the core bet of the whole project (ADR-0001) made concrete: visual
fidelity is not reconstructed, it is inherited. The renderer opens the client's
base document, clears the region it is going to generate while leaving the
document's styles, numbering, headers, footers and section properties untouched,
and writes each block as a paragraph carrying the client's own named style.

Zones (ADR-0008): everything before the body boundary (a bookmark in the
prepared base document, or the profile's ``koerpergrenze`` as fallback) is kept
verbatim: cover page, imprint, version table, table of contents, with their
images. Only the region after the boundary is cleared and regenerated. Without
a boundary the whole body is generated. When a kept table of contents exists,
the document asks Word to update its fields on opening (ADR-0003).

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
from template_engine.zonen import BLOCK_TAGS, finde_grenze

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

    # A style can be addressed by its display name or by its styleId. Real
    # templates make the distinction matter: a built-in heading has the display
    # name "Heading 1" but the styleId "Heading1", and its raw name in the file
    # may differ again by locale. Accepting either key lets a profile map roles
    # by the stable styleId (preferred, see docs/ingest-notes.md) or by name.
    nach_schluessel: dict[str, Any] = {}
    for style in doc.styles:
        if style.name:
            nach_schluessel[style.name] = style
        if style.style_id:
            nach_schluessel[style.style_id] = style

    # Resolve and check everything up front (ADR-0006): fail before mutating.
    plan: list[tuple[Any, str]] = []  # (style object, text)
    for b in dokument.bloecke:
        rolle = rolle_fuer_block(b)
        stil = profil.resolve(rolle)  # raises UnbekannteRolle
        stil_obj = nach_schluessel.get(stil)
        if stil_obj is None:
            raise FehlenderStil(
                f"role {rolle!r} maps to style {stil!r}, which the base document does not define"
            )
        for text in _absatztexte(b):
            plan.append((stil_obj, text))

    body = cast(Any, doc).element.body
    _leere_generierte_zone(body, finde_grenze(body, profil.koerpergrenze))
    if _hat_inhaltsverzeichnis(body):
        _felder_beim_oeffnen_aktualisieren(doc)

    for stil_obj, text in plan:
        doc.add_paragraph(text, style=stil_obj)

    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


def _leere_generierte_zone(body: Any, anker: Any | None) -> None:
    """Clear the generated zone: every top-level block after ``anker`` (or the
    whole body when ``anker`` is None).

    Kept: the trailing body ``sectPr`` (page geometry, header and footer
    references), paragraphs that end a section (emptied, so the section
    structure and its headers survive), and range markup such as bookmark ends.
    New content is appended at the end of the body, i.e. into the last section.
    """
    kinder = list(body)
    start = 0 if anker is None else kinder.index(anker) + 1
    for el in kinder[start:]:
        if el.tag not in BLOCK_TAGS:
            continue
        ppr = el.find(qn("w:pPr"))
        if el.tag == qn("w:p") and ppr is not None and ppr.find(qn("w:sectPr")) is not None:
            for kind in list(el):
                if kind is not ppr:
                    el.remove(kind)
            continue
        body.remove(el)


def _hat_inhaltsverzeichnis(body: Any) -> bool:
    return any(" TOC " in f" {t.text or ''} " for t in body.iter(qn("w:instrText")))


# Elements that must follow w:updateFields in w:settings (ECMA-376, CT_Settings).
_NACH_UPDATEFIELDS = {
    "hdrShapeDefaults",
    "footnotePr",
    "endnotePr",
    "compat",
    "docVars",
    "rsids",
    "mathPr",
    "attachedSchema",
    "themeFontLang",
    "clrSchemeMapping",
    "doNotIncludeSubdocsInStats",
    "doNotAutoCompressPictures",
    "forceUpgrade",
    "captions",
    "readModeInkLockDown",
    "smartTagType",
    "schemaLibrary",
    "shapeDefaults",
    "doNotEmbedSmartTags",
    "decimalSymbol",
    "listSeparator",
}


def _felder_beim_oeffnen_aktualisieren(doc: DocxDocument) -> None:
    """Set ``w:updateFields`` so Word refreshes the kept table of contents (and
    any other field) when the document is opened."""
    settings = cast(Any, doc).settings.element
    vorhanden = settings.find(qn("w:updateFields"))
    if vorhanden is not None:
        vorhanden.set(qn("w:val"), "true")
        return
    neu = settings.makeelement(qn("w:updateFields"), {qn("w:val"): "true"})
    for kind in settings:
        if isinstance(kind.tag, str) and kind.tag.split("}")[-1] in _NACH_UPDATEFIELDS:
            kind.addprevious(neu)
            return
    settings.append(neu)
