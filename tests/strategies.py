"""Hypothesis strategies that generate *canonical* trees.

The generator encodes the profile precisely: it produces exactly the trees the
Markdown surface promises to round-trip. Anything deliberately excluded here
(whitespace runs, empty text) is a documented limit of the canonical form, not a
bug to be found later. As the block catalogue grows, this file grows with it,
and no block type is "done" until it appears here and the gate stays green
(ADR-0002).
"""

from __future__ import annotations

from hypothesis import strategies as st

from template_engine.baum import (
    Absatz,
    Aufzaehlung,
    Block,
    Dokument,
    NummerierteListe,
    Ueberschrift,
)

# A deliberately hostile alphabet: letters and digits, but also the Markdown
# metacharacters most likely to expose an escaping bug, plus the non-ASCII
# punctuation that turns up constantly in real German and French deliverables.
_ZEICHEN = (
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    "*_#`[]()>|~^\\+-.!:;,=&%$@{}/"
    "äöüÄÖÜéèàçß"
    "«»„“”‘’–—…"
)

_wort = st.text(alphabet=_ZEICHEN, min_size=1, max_size=12)


def _kanonischer_text() -> st.SearchStrategy[str]:
    # Words joined by single spaces: canonical by construction.
    return st.lists(_wort, min_size=1, max_size=6).map(" ".join)


_ueberschrift = st.builds(
    Ueberschrift,
    ebene=st.integers(min_value=1, max_value=6),
    text=_kanonischer_text(),
)

_absatz = st.builds(Absatz, text=_kanonischer_text())

# Lists: one to four canonical items. Drawing blocks i.i.d. means two adjacent
# same-type lists occur naturally, which is exactly the merge hazard the mapping
# has to absorb (pandoc's HTML-comment separator).
_punkte = st.lists(_kanonischer_text(), min_size=1, max_size=4)
_aufzaehlung = st.builds(Aufzaehlung, punkte=_punkte)
_nummerierte = st.builds(NummerierteListe, punkte=_punkte)

_block: st.SearchStrategy[Block] = st.one_of(_ueberschrift, _absatz, _aufzaehlung, _nummerierte)


def dokumente() -> st.SearchStrategy[Dokument]:
    """Documents with a non-empty body and no metadata.

    Metadata is exercised separately by an example test; keeping it out of the
    property isolates the part that is actually at risk, the block tree.
    """
    return st.lists(_block, min_size=1, max_size=8).map(lambda bs: Dokument(bloecke=bs))
