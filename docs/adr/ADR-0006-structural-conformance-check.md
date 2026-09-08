# ADR-0006: Structural conformance check, no visual check in v1

**Status:** proposed
**Date:** 2026-09-07

## Context

The acceptance criterion reads: "visually indistinguishable from a document written in the client template". Without an automated check that is a hope, not a guarantee. A visual comparison (rendering to images, comparing page geometry and typography) would catch real regressions, but it needs a rendering dependency and the upkeep of reference images.

## Decision

v1 checks structurally and automatically on every render; the visual judgement is left to the operator.

The structural check guarantees:

- Every style name the renderer uses exists in the base document.
- Every role occurring in the block tree (AST) is mapped in the style profile.
- No paragraph carries direct formatting.
- The headers, footers and section properties (sectPr) of the base document are unchanged.

A failed check aborts the render; it does not merely warn.

## Rationale

The structural check is cheap and catches exactly the failure that occurs in practice: a style profile refers to `"Heading 1"` while the template calls the style `"Titel 1"`, Word falls back to the default paragraph style (`Normal`), and the document renders flat. That failure is visually catastrophic on sight and trivial to detect structurally.

The visual comparison, by contrast, addresses finer deviations whose frequency is still unknown, and it costs both setup and maintenance.

Rejected alternative: **no automatic check at all.** Accepted by the operator for v1; the structural check was nevertheless taken up here, because its cost is negligible against the risk.

## Consequences

Easier: no rendering dependency in the test chain, and the most common total failure is ruled out.

Harder: fine deviations (wrong list indentation, a different table border, a shifted figure spacing) will only be noticed by a human.

**Accepted risk:** the promise of visual indistinguishability is not enforced in v1. It rests on care during profile acceptance and on the operator's own visual inspection.

Follow-up work: a checklist for the visual inspection at profile acceptance; reassess the visual comparison once several client profiles are in productive use.

## References

- `SPEC.md`
- ADR-0001
