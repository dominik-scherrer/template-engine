"""Renderer tests: content rendered against a base document's named styles.

The base documents come from tests/basis.py and vary their style vocabularies
on purpose, so a passing renderer is demonstrably following the base document's
own names rather than assuming a fixed scheme.
"""

from __future__ import annotations

import io

import pytest
from docx import Document

import template_engine as te
from template_engine import FehlenderStil, StyleProfile, UnbekannteRolle, render
from tests.basis import Basis, alle_basen


def _paragraphen(docx: bytes) -> list[tuple[str, str]]:
    doc = Document(io.BytesIO(docx))
    return [(p.text, p.style.name) for p in doc.paragraphs]


def _profil(basis: Basis) -> StyleProfile:
    return StyleProfile(dict(basis.rollen))


@pytest.mark.parametrize("basis", alle_basen(), ids=lambda b: b.name)
def test_rendert_alle_bloecke_gegen_basis_stile(basis: Basis) -> None:
    r = basis.rollen
    dok = te.Dokument(
        bloecke=[
            te.Ueberschrift(1, "Ausgangslage"),
            te.Absatz("Ein Absatz."),
            te.Ueberschrift(2, "Punkte"),
            te.Aufzaehlung(["alpha", "beta", "gamma"]),
            te.NummerierteListe(["erstens", "zweitens"]),
        ]
    )
    out = render(dok, _profil(basis), basis.docx)

    assert _paragraphen(out) == [
        ("Ausgangslage", r["ueberschrift_1"]),
        ("Ein Absatz.", r["fliesstext"]),
        ("Punkte", r["ueberschrift_2"]),
        ("alpha", r["aufzaehlung"]),
        ("beta", r["aufzaehlung"]),
        ("gamma", r["aufzaehlung"]),
        ("erstens", r["nummerierte_liste"]),
        ("zweitens", r["nummerierte_liste"]),
    ]


@pytest.mark.parametrize("basis", alle_basen(), ids=lambda b: b.name)
def test_kopfzeile_ueberlebt_und_alter_inhalt_verschwindet(basis: Basis) -> None:
    dok = te.Dokument(bloecke=[te.Ueberschrift(1, "Neu")])
    out = render(dok, _profil(basis), basis.docx)
    doc = Document(io.BytesIO(out))
    assert doc.paragraphs[0].text == "Neu"
    assert all("alt" not in p.text and "prior" not in p.text for p in doc.paragraphs)


def test_unbekannte_rolle_wird_laut() -> None:
    basis = alle_basen()[0]
    # Drop the heading-3 role: nothing maps ueberschrift_3.
    dok = te.Dokument(bloecke=[te.Ueberschrift(3, "Zu tief")])
    with pytest.raises(UnbekannteRolle):
        render(dok, _profil(basis), basis.docx)


def test_fehlender_stil_wird_laut() -> None:
    basis = alle_basen()[0]
    profil = StyleProfile({**basis.rollen, "fliesstext": "GibtEsNicht"})
    dok = te.Dokument(bloecke=[te.Absatz("y")])
    with pytest.raises(FehlenderStil):
        render(dok, profil, basis.docx)


def test_pruefung_vor_mutation() -> None:
    basis = alle_basen()[0]
    profil = StyleProfile({**basis.rollen, "ueberschrift_1": "Fehlt"})
    dok = te.Dokument(bloecke=[te.Absatz("ok"), te.Ueberschrift(1, "kaputt")])
    with pytest.raises(FehlenderStil):
        render(dok, profil, basis.docx)


def test_rolle_fuer_block() -> None:
    assert te.rolle_fuer_block(te.Ueberschrift(2, "x")) == "ueberschrift_2"
    assert te.rolle_fuer_block(te.Absatz("x")) == "fliesstext"
    assert te.rolle_fuer_block(te.Aufzaehlung(["x"])) == "aufzaehlung"
    assert te.rolle_fuer_block(te.NummerierteListe(["x"])) == "nummerierte_liste"


def test_profil_json_rundreise() -> None:
    p = StyleProfile({"ueberschrift_1": "Titel 1", "fliesstext": "Fliesstext"})
    assert StyleProfile.from_json(p.to_json()) == p
