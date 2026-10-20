"""The zone model (ADR-0008): a retained front and a generated body.

A client template usually opens with pages that must survive every render: a
cover page, an imprint, a version table, a table of contents. The generated body
follows. The boundary between the two is a position in the sequence of the
body's top-level *blocks* (paragraphs, tables and content controls), recorded
in two places:

- as ``koerpergrenze`` in the style profile: the index of the first generated
  block (``0`` means "everything is generated");
- as a hidden bookmark ``_TE_Body`` written into the prepared base document
  (ADR-0009) directly before that block.

The bookmark is authoritative, because it survives edits to the base document
that renumber blocks; the index is the fallback and keeps the profile readable
without opening the file.

Everything here is deterministic and calls no model.
"""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
import zipfile
from typing import Any

from lxml import etree

__all__ = [
    "LESEZEICHEN",
    "bloecke",
    "bloecke_aus_body",
    "vorschlag_koerpergrenze",
    "bereite_vor",
    "finde_grenze",
    "ZonenFehler",
]

W_NS = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_W = "{" + W_NS + "}"
LESEZEICHEN = "_TE_Body"
BLOCK_TAGS = (_W + "p", _W + "tbl", _W + "sdt")
_LESEZEICHEN_ID = "907"  # any id unused by the template; Word renumbers on save


class ZonenFehler(ValueError):
    """A boundary that does not fit the base document."""


# -- reading -------------------------------------------------------------------


def _text(el: Any, limit: int = 80) -> str:
    # Join a table's (or content control's) paragraphs with a separator, so
    # cell contents stay readable: "Version · Date · 1.0" rather than "VersionDate1.0".
    absaetze = ["".join(t.text or "" for t in p.iter(_W + "t")) for p in el.iter(_W + "p")]
    if el.tag == _W + "p" or not absaetze:
        return "".join(t.text or "" for t in el.iter(_W + "t"))[:limit]
    return " · ".join(a for a in absaetze if a.strip())[:limit]


def _beschreibe(index: int, el: Any) -> dict[str, Any]:
    art = {"p": "paragraph", "tbl": "table", "sdt": "control"}[el.tag[len(_W) :]]
    stil = ""
    ps = el.find(f"{_W}pPr/{_W}pStyle")
    if ps is not None:
        stil = ps.get(_W + "val") or ""
    feldcodes = " ".join(t.text or "" for t in el.iter(_W + "instrText"))
    galerie = el.find(f".//{_W}docPartGallery")
    seitenumbruch = any(b.get(_W + "type") == "page" for b in el.iter(_W + "br")) or (
        el.find(f".//{_W}pageBreakBefore") is not None
    )
    return {
        "index": index,
        "kind": art,
        "styleId": stil,
        "text": _text(el),
        "section_break": el.find(f"{_W}pPr/{_W}sectPr") is not None,
        "page_break": seitenumbruch,
        "toc": " TOC " in f" {feldcodes} "
        or (galerie is not None and "Table of Contents" in (galerie.get(_W + "val") or "")),
        "cover": galerie is not None and "Cover" in (galerie.get(_W + "val") or ""),
        "image": el.find(f".//{_W}drawing") is not None,
        "bookmark": False,
    }


def bloecke_aus_body(body: Any) -> list[dict[str, Any]]:
    """The top-level blocks of a ``w:body`` element, with what a person (or a
    proposer) needs to pick the boundary. ``bookmark`` marks the block the
    boundary bookmark currently sits in front of."""
    out: list[dict[str, Any]] = []
    vor_lesezeichen = False
    for el in list(body):
        if el.tag == _W + "bookmarkStart" and el.get(_W + "name") == LESEZEICHEN:
            vor_lesezeichen = True
            continue
        if el.tag in BLOCK_TAGS:
            b = _beschreibe(len(out), el)
            b["bookmark"] = vor_lesezeichen
            vor_lesezeichen = False
            out.append(b)
    return out


def bloecke(daten: bytes) -> list[dict[str, Any]]:
    """The top-level block sequence of a .docx/.dotx (see :func:`bloecke_aus_body`)."""
    z = zipfile.ZipFile(io.BytesIO(daten))
    root = ET.fromstring(z.read("word/document.xml"))
    body = root.find(_W + "body")
    return [] if body is None else bloecke_aus_body(body)


def vorschlag_koerpergrenze(folge: list[dict[str, Any]], ueberschrift_1: str = "") -> int:
    """A deterministic first guess for where the generated body begins.

    The body starts at the first top-level heading that sits on a later page
    than the start of the document: after a page break, a section break, a
    table of contents or a cover page. A heading on the first page is taken to
    be part of a title page. Without such a heading the guess is ``0``
    (everything generated). A person confirms the result.
    """
    neue_seite = False
    nach_front = False
    for b in folge:
        if b["kind"] == "paragraph" and ueberschrift_1 and b["styleId"] == ueberschrift_1:
            if neue_seite or nach_front:
                return int(b["index"])
        if b["page_break"] or b["section_break"]:
            neue_seite = True
        if b["toc"] or b["cover"]:
            nach_front = True
    return 0


# -- preparing ---------------------------------------------------------------------


def _bloecke_lxml(body: Any) -> list[Any]:
    return [el for el in body if el.tag in BLOCK_TAGS]


def _entferne_lesezeichen(body: Any) -> None:
    for el in list(body):
        if el.tag == _W + "bookmarkStart" and el.get(_W + "name") == LESEZEICHEN:
            kennung = el.get(_W + "id")
            body.remove(el)
            for ende in list(body):
                if ende.tag == _W + "bookmarkEnd" and ende.get(_W + "id") == kennung:
                    body.remove(ende)


def setze_lesezeichen(body: Any, koerpergrenze: int) -> None:
    """Place the boundary bookmark before block ``koerpergrenze`` of an lxml
    ``w:body`` (replacing any earlier one)."""
    _entferne_lesezeichen(body)
    folge = _bloecke_lxml(body)
    if not 0 <= koerpergrenze <= len(folge):
        raise ZonenFehler(
            f"body boundary {koerpergrenze} is outside the template's {len(folge)} blocks"
        )
    start = etree.Element(_W + "bookmarkStart")
    start.set(_W + "id", _LESEZEICHEN_ID)
    start.set(_W + "name", LESEZEICHEN)
    ende = etree.Element(_W + "bookmarkEnd")
    ende.set(_W + "id", _LESEZEICHEN_ID)
    if koerpergrenze < len(folge):
        anker = folge[koerpergrenze]
        anker.addprevious(start)
        anker.addprevious(ende)
    else:
        schluss = body.find(_W + "sectPr")
        if schluss is not None:
            schluss.addprevious(start)
            schluss.addprevious(ende)
        else:
            body.append(start)
            body.append(ende)


def bereite_vor(basis_docx: bytes, koerpergrenze: int) -> bytes:
    """The prepared base document: ``basis_docx`` with the boundary bookmark
    written before block ``koerpergrenze``. Idempotent; nothing else changes."""
    zin = zipfile.ZipFile(io.BytesIO(basis_docx))
    root = etree.fromstring(zin.read("word/document.xml"))
    body = root.find(_W + "body")
    if body is None:
        raise ZonenFehler("the base document has no body")
    setze_lesezeichen(body, koerpergrenze)
    neu = etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            daten = neu if item.filename == "word/document.xml" else zin.read(item.filename)
            zout.writestr(item, daten)
    return out.getvalue()


def finde_grenze(body: Any, koerpergrenze: int | None) -> Any | None:
    """The body child after which the generated zone begins, or None when the
    whole body is generated. Prefers the bookmark, falls back to the index."""
    for el in body:
        if el.tag == _W + "bookmarkStart" and el.get(_W + "name") == LESEZEICHEN:
            # the matching bookmarkEnd follows directly; the zone starts after it
            nachfolger = el.getnext()
            if nachfolger is not None and nachfolger.tag == _W + "bookmarkEnd":
                return nachfolger
            return el
    if not koerpergrenze:
        return None
    folge = _bloecke_lxml(body)
    if koerpergrenze > len(folge):
        raise ZonenFehler(
            f"body boundary {koerpergrenze} is outside the template's {len(folge)} blocks"
        )
    if koerpergrenze == len(folge):
        return folge[-1]
    return folge[koerpergrenze].getprevious() if koerpergrenze else None
