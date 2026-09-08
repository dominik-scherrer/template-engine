# ADR-0011: python-docx as the renderer, minimal field surface

**Status:** proposed
**Date:** 2026-09-07

## Context

Pandoc is ruled out as the renderer: it discards the body of the reference template unconditionally (which makes the zone model impossible), emits exactly one `sectPr` (which makes separate page numbering impossible), knows a single hard-coded table style name, and produces no figure numbering.

That leaves python-docx (free, MIT licensed, but with no field support whatsoever: issue #31 has been open since 2014) and the commercial OOXML libraries, at least one of which offers documented programmatic field update.

The trade-off appeared to hinge on how much field support we need. A closer look shows that the need is far smaller than assumed.

## Decision

**python-docx** is the renderer. The field surface is limited to **one** construct we write ourselves: `SEQ` in captions.

## Rationale

The zone model (ADR-0008) moves almost all fields into the retained zone, where they already sit finished in the client template and do not have to be generated at all:

| Need | Where it comes from | Must it be generated? |
|---|---|---|
| Table of contents | The `TOC` field sits in the retained front matter | **No.** The body only has to supply correctly formatted headings; Word collects them when fields are updated |
| Chapter numbering | `numbering.xml`, bound to the heading styles | **No**, it follows from the style assignment |
| Page numbers | `PAGE` fields in the footer, which is never touched | **No** |
| Lists of figures and tables | The `TOC \c` field sits in the front matter, but it collects `SEQ` fields carrying a given label | **Yes.** A caption set as plain text, "Abbildung 1: …", is not collected, and the list would stay empty |
| Cross-references | Running text in the body | **Later.** Not required for v1 |

Exactly one construct remains: a `fldChar` begin / `instrText` / `fldChar` end triple for `SEQ Abbildung \* ARABIC`. That is roughly fifteen lines of lxml, written and tested once, not a field layer.

The main advantage of the commercial option is *resolving* fields (programmatic field update plus repagination). ADR-0003, however, has already decided that resolution is left to the recipient's word processor. The advantage that would have to justify a licence is therefore never drawn on.

To that come two empirically confirmed properties of python-docx:

- **Clearing a paragraph range while preserving the section properties works.** Delete every paragraph except those whose `pPr` carries a `w:sectPr`. Both sections and both headers stayed intact. This makes the most delicate open question of the zone model solvable.
- **Assigning a style by name raises `KeyError` when the style is missing**, contrary to python-docx's own documentation. That makes the most important part of the conformance check from ADR-0006 free of charge.

Rejected alternatives:

- **A commercial OOXML library.** Technically superior, but its decisive added value is not drawn on, because of ADR-0003. Taking on a licensed dependency for a fifteen-line construct is not justifiable. It stays documented as a fallback.
- **Pandoc as the renderer.** Ruled out, see Context.
- **docxcompose** (front matter as its own file, generated body appended). Appealingly simple, but it discards the headers and footers of the appended documents and gives up control over the section boundary. Noted as an emergency exit.

## Consequences

Easier: no licence cost, no .NET dependency in the container, pure Python. The conformance check comes partly for free.

Harder: the `SEQ` construct and the section-preserving clearing are hand-written OOXML with no library backing them. Both need a test of their own, against a real client template rather than a synthetic document.

**docxbuilder** (`docxbuilder/docx/docx.py`) serves as the blueprint: a three-stage fallback chain for title page detection, and reuse of all `sectPr` from the style template. Not to be taken on as a dependency (last release 2020, Python 2 legacy, coupled to Sphinx), but to be read and reimplemented as patterns.

**Exit criterion:** if the field surface grows beyond `SEQ` and `REF`, or if section-preserving clearing turns out to be unreliable on real client templates, a commercial OOXML library is re-evaluated. Rendering is therefore to be encapsulated behind a narrow interface.

## References

- ADR-0003, ADR-0006, ADR-0008
- [docxbuilder](https://github.com/amedama41/docxbuilder) · [python-docx#31](https://github.com/python-openxml/python-docx/issues/31)
