# ADR-0009: Prepared base document, we modify the client file

**Status:** proposed
**Date:** 2026-09-07

## Context

The title page sits in a retained zone (ADR-0008): its structure is fixed, its values differ per document. Inserting values requires binding sites. The client file brings none, unless it already uses `DOCPROPERTY` fields, which is not something one can rely on.

Beyond that, ADR-0007 may require named styles to be written into the template, and ADR-0008 requires a bookmark at each zone boundary.

## Decision

Ingest produces a **prepared base document**: the client file with Jinja tags at the binding sites of the retained zones, a bookmark at every zone boundary, and, where applicable, harvested style definitions. This prepared document is the carrier document for rendering.

The unmodified original file is retained alongside it as an artefact.

Where the tags belong is *proposed*, not decided, inside the library. The library defines a **proposer** interface, and the caller supplies an implementation, typically one backed by a language model. The proposer reads the title page and recognises that "Acme Corp" is the client name and that "Version 1.2 / 14.03.2026" are the version and the date. **The library itself calls no model.** It returns the proposals as data, the caller presents them, a human confirms them, and only then does the library write the tags for the confirmed proposals.

**Rendering needs no proposer at all**: it inserts values that are already available as metadata.

If a changed client template is delivered, preparation is redone from scratch. Nothing is carried over from the previous version.

## Rationale

Without modifying the client file, the only option would be text replacement on sample text, searching for "Acme Corp" and replacing it, which guesses afresh for every client and gets it wrong wherever an occurrence is ambiguous. Explicit tags make the binding sites visible, reviewable and fixed once and for all.

On the division of labour between human, caller and library: mapping sample text to meaning is unstructured extraction, and that is where a model belongs, on the caller's side of the boundary. Inserting a known value into a known tag is not extraction; a model there would be slower, more expensive, not reproducible and not testable. This follows the project principle "deterministic before model".

Keeping the proposer outside the library is what makes that principle enforceable rather than merely intended. The library is deterministic end to end: the same inputs produce the same prepared document and the same rendered output, and no model is called anywhere in its own code. The single non-deterministic element in the whole workflow is the caller's proposer, and it runs once, before human confirmation, entirely outside the rendering path.

On redoing preparation in full: a difference-aware carry-over would be more convenient, but it would have to judge whether a binding site is still the same site after a layout change. When it judges wrongly, a tag silently migrates to the wrong place and the error reaches the client. Full re-preparation is blunter, and in exchange it has no silent failures.

## Consequences

Easier: binding sites are unambiguous and visible in the document. Rendering is fully deterministic, hence testable, and it incurs no model cost.

Harder: the library modifies a client file. The prepared document must never reach the client; only the rendered result is handed on. Preparation must be guaranteeably invisible: tags only at places that are substituted during rendering, and no change to layout, styles or headers and footers beyond what ADR-0007 explicitly permits.

Re-preparation is recurring effort. A client who revises their template every quarter causes work every quarter. That is the price knowingly paid, and accordingly the ingest path has to be built for speed. Older profile versions remain intact, and documents already pinned to them are unaffected (ADR-0004).

Follow-up work: keeping the original and the prepared document as separate artefacts; a check that preparation changes nothing outside the tags; a rule that the prepared document is never delivered.

## References

- `SPEC.md`
- ADR-0004, ADR-0007, ADR-0008, ADR-0010
