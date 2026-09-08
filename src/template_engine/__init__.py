"""Template Engine: render structured content in a client template's appearance.

Design stage. This package currently implements only the canonical block tree
(``baum``) and its lossless Markdown surface, together with the round-trip gate
that guards every future block type (see docs/adr/ADR-0002).
"""

from template_engine.baum import Absatz, Block, Dokument, Ueberschrift
from template_engine.markdown_surface import from_markdown, to_markdown

__all__ = [
    "Dokument",
    "Block",
    "Ueberschrift",
    "Absatz",
    "from_markdown",
    "to_markdown",
]
