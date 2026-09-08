# ADR-0005: One-way rendering in v1, reading back deliberately kept open

**Status:** proposed
**Date:** 2026-09-07

## Context

Clients edit delivered documents in Word and send them back, and experience shows that operators would rather change wording directly in the Word file than in the content document. A `.docx` to block tree (AST) reader would feed those changes back.

## Decision

v1 renders in one direction only. The block tree and the style profile are nevertheless designed so that a read-back path can be added later without rebuilding the data model.

## Rationale

Reading Word XML is considerably more work than writing it, and reconstructing semantic blocks from formatted text stays unreliable for good. The effort would double the library and delay the benefit v1 already delivers.

Keeping the option open, by contrast, costs little. It is enough that every block type leaves a distinct trace that can be recognised again in the `.docx` (a style role rather than direct formatting, which ADR-0001 gives us anyway), and that the block tree carries no information that disappears without trace in the rendered document.

Rejected alternatives:

- **Reading back in v1.** Doubles the scope for a workflow whose frequency is not yet known.
- **Ruling read-back out permanently.** Forces a discipline ("never edit in Word") that does not survive everyday use.

## Consequences

Easier: v1 stays lean and is usable sooner.

Harder: until the read-back path exists, changes made in the Word document are lost on the next render. The host application has to say this unmistakably where the operator can see it; a note in the documentation is not enough. All the library can do is make the fact available, for instance by exposing that a document has already been rendered and delivered.

Follow-up work: a warning when a document that has already been delivered is rendered again; add the design rule "no block detail without a trace in the document" to the definition of done for new block types.

## References

- `SPEC.md`
- ADR-0001, ADR-0002
