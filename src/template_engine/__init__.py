"""Template Engine: render structured content in a client template's appearance.

Design stage. This package currently implements only the canonical block tree
(``baum``) and its lossless Markdown surface, together with the round-trip gate
that guards every future block type (see docs/adr/ADR-0002).
"""

from template_engine.baum import (
    Absatz,
    Aufzaehlung,
    Block,
    Dokument,
    NummerierteListe,
    Ueberschrift,
)
from template_engine.fehler import FehlenderStil, RenderFehler, UnbekannteRolle
from template_engine.markdown_surface import from_markdown, to_markdown
from template_engine.render import render, rolle_fuer_block
from template_engine.stilprofil import StyleProfile

__all__ = [
    "Dokument",
    "Block",
    "Ueberschrift",
    "Absatz",
    "Aufzaehlung",
    "NummerierteListe",
    "from_markdown",
    "to_markdown",
    "StyleProfile",
    "render",
    "rolle_fuer_block",
    "RenderFehler",
    "UnbekannteRolle",
    "FehlenderStil",
]
