# ADR-0010: Tags with substitution and conditionals only, no loops

**Status:** proposed
**Date:** 2026-09-07

## Context

The Jinja tags in the retained zones (ADR-0009) could be arbitrarily powerful. Plain value substitution is the smallest surface; full Jinja with loops would be the most powerful and would place arbitrary logic inside a client's document.

## Decision

Value substitution (`{{ kunde_name }}`) and conditionals (`{% if vertraulich %}…{% endif %}`) are permitted. Loops are not.

## Rationale

Conditionals cover the real need that plain substitution cannot meet: a classification banner only on confidential documents, a subtitle line only when one exists, a logo only for certain document types. Without conditionals the only remaining option would be to maintain a separate style profile for every variant.

Loops stay out because variable length is the defining property of the generated area. Anything that needs a loop belongs, by definition, in the body and not on the title page. The boundary therefore runs in the same place as the zone model does, which is what makes the rule explainable.

There is a second reason: a human has to sign off the tags at ingest. Value substitutions and conditionals can be read off a document; nested loops in someone else's Word XML cannot.

Rejected alternatives:

- **Substitution only.** The smallest surface, but it forces a separate profile per document variant.
- **Full Jinja with loops.** More powerful, but unreviewable at sign-off, and it undermines the zone separation because variable length could then arise in two places.

## Consequences

Easier: signing off a profile remains a task an operator can carry out without programming knowledge. The rule "variable length belongs in the body" holds without exception.

Harder: a template whose title page genuinely lists N authors or N client logos is not covered. Such cases must either be mapped onto a fixed maximum via conditionals (three author lines, each conditional), or the zone boundary is placed so that the part in question falls inside the generated area.

Follow-up work: enforce the permitted tag surface during ingest; reject disallowed constructs with a comprehensible message; document the workaround patterns (conditional repetition, moving the boundary).

## References

- `SPEC.md`
- ADR-0008, ADR-0009
