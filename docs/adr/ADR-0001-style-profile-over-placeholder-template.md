# ADR-0001: Style profile instead of a placeholder template

**Status:** proposed · refined by ADR-0008
**Date:** 2026-09-07

## Context

The obvious default for producing client deliverables in Office formats is `python-docx` or `docxtemplater`, and an earlier prototype in this project followed exactly that pattern: a fixed document skeleton with `{{PLACEHOLDER}}` holes that get filled in.

The library, however, has to produce documents whose structure varies from one document to the next. Sections disappear, new ones appear, the order changes, and the number of team members, service groups and milestones is not known in advance. The earlier prototype encoded precisely two team members and three service groups. That is the breaking point.

A placeholder approach presupposes a skeleton into which the placeholders can be set. Without a fixed structure there is no skeleton.

## Decision

Visual fidelity is not achieved by reusing the client's layout but by reusing its **style definitions**. Rendering opens the client file as the base document, clears the generated zone (not the entire body, see ADR-0008), and creates the paragraphs programmatically with references to the client's named styles.

## Rationale

The client file carries `styles.xml`, `numbering.xml`, the theme, headers and footers, and the section properties (sectPr). As long as it stays the carrier document, the letterhead, fonts, margins and table styles are correct without any reconstruction, and at the same time the structure of the body is completely free.

Rejected alternatives:

- **docxtemplater or docxtpl on a tagged template.** Highest fidelity, but it presupposes a fixed structure. It fails on the requirement that documents vary freely.
- **Full reconstruction with explicit formatting instructions** (font, size and spacing set directly on each paragraph). This always works, but it produces documents without any style structure: they cannot be maintained in Word and fall apart the first time a client touches them.
- **Markdown through Pandoc with a `reference.docx`.** Close to this decision and considerably cheaper, but it fails on table styles, figure numbering and cross-references at the depth required here.

## Consequences

Easier: a new client template is ingested in minutes rather than tagged over hours. Document structure and appearance are fully decoupled, so the same content document renders for every client.

Harder: the role mapping becomes the critical path. If it points at a style the template does not know, Word falls back to the default paragraph style (`Normal`) and the whole document renders flat. That is what forces the structural conformance check in ADR-0006.

Follow-up work: define the role catalogue; build the ingest assistant; settle the behaviour for templates that carry no named styles (ADR-0007).

## References

- `SPEC.md`
- ADR-0008 (zone model, which pins down exactly which part of the body is cleared)
