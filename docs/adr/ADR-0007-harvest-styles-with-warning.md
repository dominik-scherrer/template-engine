# ADR-0007: Harvest styles, but with a warning and a way back

**Status:** proposed
**Date:** 2026-09-07

## Context

Many real Word files supplied by clients contain no named styles at all: headings are bold 14 pt text, tables are framed by hand. The role mapping from ADR-0001 then has nothing to map onto.

## Decision

Ingest derives roles from the formatting patterns and creates matching named styles in the base document, coupled with an explicit warning to the operator: that the template carried no styles, what was derived from it, and that a `.dotx` correctly formatted in Word can be ingested again.

## Rationale

Refusing such files would be cleaner, but it renders the library unusable in a very common situation and shifts all of the work onto the operator. Harvesting silently is the opposite failure: it yields a mapping that may well be wrong, and it conceals the fact that the basis was weak.

The warning holds both concerns together. Work can start immediately, the quality gap stays visible, and there is a clear route to a better basis. It is also the moment at which the operator decides whether it is worth asking the client for the `.dotx`.

Rejected alternatives:

- **Refuse with a diagnosis.** Honest, but blocking.
- **Fall back to direct formatting** (the profile stores font and size instead of style names). This always works, but it produces documents that cannot be maintained in Word, and it undermines both ADR-0001 and the conformance check from ADR-0006.

## Consequences

Easier: no client template is ruled out from the start.

Harder: in this case the library alters the base document by inserting style definitions. The unmodified original has to be retained as an artefact so that it remains traceable what was added; the library hands both documents back and the caller persists them. Derived roles must be flagged as derived in the profile, because they deserve more attention at sign-off than detected ones.

Follow-up work: an `origin: detected | derived` marker per role mapping; warning text and recommended action returned by ingest so that the host application can present them; ingesting the same template a second time must produce a new profile version (ADR-0004).

## References

- `SPEC.md`
- ADR-0001, ADR-0004, ADR-0006
