# ADR-0008: Zone model, retained and generated areas

**Status:** proposed
**Date:** 2026-09-07
**Refines:** ADR-0001

## Context

ADR-0001 assumed that the body of the base document is entirely disposable: open it, clear it, write it anew. Client templates, however, carry parts in the body that must survive: the title page, the version and change table, the table of contents, the lists of figures and tables. Clearing the body destroys exactly what makes the template a template.

These parts differ from one another. The title page keeps its structure but changes its values from document to document. The table of contents is not content at all, it is a field. The version table stays untouched for now. There is no single procedure that handles all three.

## Decision

A document is an ordered sequence of **zones**, each either `retained` or `generated`. The style profile records that sequence.

- **Retained zone:** taken over unchanged from the prepared base document. Jinja tags inside it are substituted (ADR-0009, ADR-0010), Word fields inside it stay fields and resolve when the document is opened (ADR-0003). Nothing else is touched.
- **Generated zone:** cleared and rebuilt from the block tree (AST), using the styles from the role mapping (ADR-0001).

The boundaries between zones are recorded during preparation as paragraph ranges in the style profile **and**, additionally, written into the prepared base document as Word bookmarks. The bookmark is authoritative; the paragraph range serves as a fallback and makes the profile readable without opening the file.

For v1 the usual sequence is `retained` (front matter) followed by `generated` (body). The model permits any number of zones, so that a retained closing part (a signature block, terms and conditions, appendices) can be added later without changing the model.

## Rationale

Zones separate two procedures that would otherwise damage each other. In the retained area the structure is fixed, so placeholder substitution is the right tool there: precisely the procedure ADR-0001 rejected for the body, because the body's structure is not fixed. The apparent contradiction dissolves as soon as one stops treating the document as homogeneous.

A paragraph range on its own would be brittle if it pointed into the live client file. It does not: it points into the prepared base document, which is immutable per profile version (ADR-0004, ADR-0009), and a change to the client template forces a new version anyway. The bookmark complements the range because it survives renumbering during a repeated preparation and because it is visible in Word.

Rejected alternatives for drawing the boundary:

- **Section break as the boundary.** Uses structure that is already there, but not every template separates front matter and body by section, and some templates break several times for layout reasons.
- **First level 1 heading.** Requires no configuration, but it is wrong as soon as a title page uses a heading style, which happens often.
- **Marker paragraph in the text.** Robust and visible, but a visible foreign body; the bookmark achieves the same thing invisibly.

## Consequences

Easier: the title page, the lists and the version table survive without being rebuilt. The table of contents in the retained front matter picks up the headings of the generated body automatically when fields are updated, so the two procedures mesh instead of obstructing each other.

Harder: section properties (`sectPr`) cut across the zones. Front matter and body often use different page numbering (roman, then arabic), and a section break sits exactly on the boundary. Clearing the generated zone must not take the section structure with it. This is the most delicate point of the implementation.

Still open: the list of figures in the front matter counts `SEQ` fields carrying a particular label. The captions produced in the body must use that same label, since `Abbildung` and `Figure` yield two separate counters. The role mapping has to take the label from the template.

Follow-up work: the zone sequence in the data model; boundary selection exposed through the ingest API, with the host application driving the choice; preservation of section properties as a test of its own; the `SEQ` label in the capability profile.

## References

- `SPEC.md`
- ADR-0001, ADR-0003, ADR-0004, ADR-0009, ADR-0010
