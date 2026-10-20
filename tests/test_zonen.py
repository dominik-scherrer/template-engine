"""The zone model (ADR-0008): retained front, generated body, boundary bookmark.

The fixture is a synthetic template with the shape real ones have: a cover
page with an image, a version table, a table of contents field and a page
break, followed by example body content that must be replaced.
"""

from __future__ import annotations

import io
import struct
import zipfile
import zlib

import pytest
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_BREAK
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm
from lxml import etree

import template_engine as te
from template_engine import zonen

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def _png() -> bytes:
    raw = b"".join(b"\x00" + b"\x10\x60\x70" * 8 for _ in range(4))

    def chunk(t: bytes, d: bytes) -> bytes:
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d))

    ihdr = struct.pack(">IIBBBBB", 8, 4, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def _toc_absatz(doc: object) -> None:
    p = doc.add_paragraph()  # type: ignore[attr-defined]
    r = p.add_run()
    for art, text in (("begin", None), (None, ' TOC \\o "1-3" \\h '), ("end", None)):
        if art:
            fc = OxmlElement("w:fldChar")
            fc.set(qn("w:fldCharType"), art)
            r._r.append(fc)
        else:
            it = OxmlElement("w:instrText")
            it.text = text
            r._r.append(it)


def vorlage(abschnitt_im_koerper: bool = False) -> bytes:
    doc = Document()
    doc.sections[0].header.paragraphs[0].text = "Acme Advisory"
    doc.add_paragraph("Project report", style="Title")  # 0
    doc.add_paragraph().add_run().add_picture(io.BytesIO(_png()), width=Cm(6))  # 1
    t = doc.add_table(rows=2, cols=2)  # 2: version table
    t.cell(0, 0).text, t.cell(0, 1).text = "Version", "Date"
    t.cell(1, 0).text, t.cell(1, 1).text = "1.0", "2026-01-01"
    _toc_absatz(doc)  # 3
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)  # 4
    doc.add_paragraph("Old chapter", style="Heading 1")  # 5 <- body starts here
    doc.add_paragraph("Old body text.")  # 6
    doc.add_table(rows=1, cols=1).cell(0, 0).text = "old table"  # 7
    if abschnitt_im_koerper:
        doc.add_section(WD_SECTION.NEW_PAGE)  # turns paragraph 7's successor into a break
        doc.add_paragraph("Old appendix")
    out = io.BytesIO()
    doc.save(out)
    return out.getvalue()


PROFIL = te.StyleProfile(
    {
        "ueberschrift_1": "Heading1",
        "ueberschrift_2": "Heading2",
        "fliesstext": "Normal",
        "aufzaehlung": "ListBullet",
        "nummerierte_liste": "ListNumber",
    }
)
INHALT = te.from_markdown("# New chapter\n\nNew text.\n\n- a\n- b\n")


def _body(docx: bytes) -> etree._Element:
    root = etree.fromstring(zipfile.ZipFile(io.BytesIO(docx)).read("word/document.xml"))
    return root.find(W + "body")


def _bloecke_xml(docx: bytes) -> list[bytes]:
    return [etree.tostring(el) for el in _body(docx) if el.tag in zonen.BLOCK_TAGS]


# -- reading and proposing ---------------------------------------------------


def test_block_sequence_flags_what_matters() -> None:
    b = te.bloecke(vorlage())
    assert [x["kind"] for x in b[:4]] == ["paragraph", "paragraph", "table", "paragraph"]
    assert b[1]["image"] and b[3]["toc"] and b[4]["page_break"]
    assert b[5]["styleId"] == "Heading1" and b[5]["text"] == "Old chapter"


def test_heuristic_picks_the_first_heading_on_a_later_page() -> None:
    assert te.vorschlag_koerpergrenze(te.bloecke(vorlage()), "Heading1") == 5


def test_heuristic_ignores_a_heading_on_the_title_page() -> None:
    doc = Document()
    doc.add_paragraph("Cover heading", style="Heading 1")
    doc.add_paragraph("Body starts without a page break", style="Heading 1")
    out = io.BytesIO()
    doc.save(out)
    assert te.vorschlag_koerpergrenze(te.bloecke(out.getvalue()), "Heading1") == 0


def test_heuristic_is_part_of_the_proposal() -> None:
    from template_engine import ingest

    v = ingest.heuristischer_vorschlag(ingest.kontext_aus_bytes(vorlage()))
    assert v.koerpergrenze == 5


# -- preparing ---------------------------------------------------------------------


def test_preparation_writes_one_bookmark_and_changes_nothing_else() -> None:
    basis = vorlage()
    einmal = te.bereite_vor(basis, 5)
    zweimal = te.bereite_vor(einmal, 5)
    marken = [el for el in _body(zweimal) if el.get(W + "name") == te.LESEZEICHEN]
    assert len(marken) == 1
    assert _bloecke_xml(zweimal) == _bloecke_xml(basis)
    assert [b["bookmark"] for b in te.bloecke(zweimal)].index(True) == 5


def test_preparation_rejects_a_boundary_outside_the_document() -> None:
    with pytest.raises(te.ZonenFehler):
        te.bereite_vor(vorlage(), 99)


# -- rendering ---------------------------------------------------------------------


@pytest.mark.parametrize("vorbereitet", [True, False], ids=["bookmark", "index-fallback"])
def test_front_is_kept_verbatim_and_body_replaced(vorbereitet: bool) -> None:
    basis = vorlage()
    profil = te.StyleProfile(PROFIL.rollen, koerpergrenze=5)
    traeger = te.bereite_vor(basis, 5) if vorbereitet else basis
    out = te.render(INHALT, profil, traeger)

    vorher, nachher = _bloecke_xml(basis), _bloecke_xml(out)
    assert nachher[:5] == vorher[:5]  # cover, image, version table, TOC, page break
    texte = [b["text"] for b in te.bloecke(out)[5:]]
    assert texte == ["New chapter", "New text.", "a", "b"]
    assert "Old body text." not in str(te.bloecke(out))


def test_whole_body_is_generated_without_a_boundary() -> None:
    out = te.render(INHALT, PROFIL, vorlage())
    assert [b["text"] for b in te.bloecke(out)] == ["New chapter", "New text.", "a", "b"]


def test_boundary_at_the_end_keeps_everything_and_appends() -> None:
    basis = vorlage()
    n = len(te.bloecke(basis))
    out = te.render(INHALT, te.StyleProfile(PROFIL.rollen, n), te.bereite_vor(basis, n))
    assert _bloecke_xml(out)[:n] == _bloecke_xml(basis)
    assert te.bloecke(out)[n]["text"] == "New chapter"


def test_kept_toc_makes_word_update_fields_on_open() -> None:
    out = te.render(INHALT, te.StyleProfile(PROFIL.rollen, 5), te.bereite_vor(vorlage(), 5))
    settings = etree.fromstring(zipfile.ZipFile(io.BytesIO(out)).read("word/settings.xml"))
    namen = [el.tag.split("}")[-1] for el in settings if isinstance(el.tag, str)]
    assert "updateFields" in namen
    if "compat" in namen:  # schema order: updateFields precedes compat
        assert namen.index("updateFields") < namen.index("compat")


def test_no_update_prompt_without_fields() -> None:
    out = te.render(INHALT, PROFIL, vorlage())
    assert b"updateFields" not in zipfile.ZipFile(io.BytesIO(out)).read("word/settings.xml")


def test_a_section_break_in_the_body_is_kept_but_emptied() -> None:
    basis = vorlage(abschnitt_im_koerper=True)
    out = te.render(INHALT, te.StyleProfile(PROFIL.rollen, 5), te.bereite_vor(basis, 5))
    body = _body(out)
    abschnitte = [p for p in body.iter(W + "sectPr")]
    assert len(abschnitte) == len(list(_body(basis).iter(W + "sectPr")))
    assert "Old appendix" not in str(te.bloecke(out))


# -- profile -------------------------------------------------------------------------


def test_profile_carries_the_boundary_through_json() -> None:
    p = te.StyleProfile({"fliesstext": "Normal"}, koerpergrenze=5)
    assert te.StyleProfile.from_json(p.to_json()) == p
    assert te.StyleProfile.from_json('{"rollen": {}}').koerpergrenze is None


@pytest.mark.parametrize("wert", ["5", -1, 1.5, True])
def test_profile_rejects_a_malformed_boundary(wert: object) -> None:
    import json

    with pytest.raises(ValueError):
        te.StyleProfile.from_json(json.dumps({"rollen": {}, "koerpergrenze": wert}))
