# ADR-0003: Real Word fields instead of substituted values

**Status:** proposed · Addendum 2026-09-07 following ADR-0008
**Date:** 2026-09-07

## Context

A table of contents, chapter numbering, figure and table numbers, and cross-references ("see section 2.1") cannot be computed with `python-docx`. Those values only come into existence when Word or LibreOffice opens the document and updates the fields.

## Decision

Rendering inserts real Word fields (`TOC`, `SEQ`, `REF`, `STYLEREF`). Resolving them is left to the recipient's word processor.

## Rationale

Fields stay correct after handover: if the operator or the client inserts a section, Word renumbers. Substituted plain-text values look right immediately and are wrong from the first edit onwards, and these documents are, in practice, always edited further.

Rejected alternatives:

- **Headless resolution through LibreOffice.** It delivers a finished document, but it drags a heavy dependency into the render path, and LibreOffice noticeably alters Word layout in edge cases, which contradicts the requirement of visual indistinguishability head-on.
- **Substituting values as plain text.** Rejected, see above.

## Consequences

Easier: the render path stays a pure Python dependency, fast and runnable in CI.

Harder: on opening, the table of contents shows placeholders at first. Countermeasure: set `w:updateFields` in the document so that Word updates by itself on open, and make sure the host application tells operators about it.

Open: for PDF output the resolution has to happen somewhere. If a PDF path is built, headless resolution should be reassessed there, and only there.

## References

- `SPEC.md`

---

## Addendum: the field surface is smaller than assumed here

This ADR predates the zone model and assumed the library would have to produce `TOC`, `SEQ`, `REF` and `STYLEREF` itself. The zone model (ADR-0008) moves almost all of them into the retained zone, where they already sit finished in the client template.

Exactly one construct actually has to be produced by the library: **`SEQ` in captions**, so that the list of figures and the list of tables in the front matter pick up the captions generated in the body. A caption set as plain text leaves that list empty.

Not to be produced, because it is already present or derived from styles: the table of contents (the field sits in the front matter and collects heading styles), chapter numbering (from `numbering.xml`), page numbers (`PAGE` in the footer). Cross-references (`REF`) are deferred for v1.

The decision itself, real fields with resolution by the recipient's word processor, is unchanged. It is supported by what commercial document generation products admit about themselves: at least one documents that its own table of contents "can be inaccurate" when sub-documents are pulled in dynamically. Headless resolution through LibreOffice would therefore not have been a rescue either.

See ADR-0011 for what this implies for the choice of renderer.
