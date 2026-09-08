# ADR-0002: Block tree canonical, Markdown as the editing surface

**Status:** proposed · Addendum 2026-09-07
**Date:** 2026-09-07

## Context

The content has to exist in a format that can be converted to `.docx` but is not itself `.docx`. Two groups of users pull in opposite directions. Operators and language models draft and correct prose, and they want a readable text format. The calling tools in the host application already hold structured data, and they should not have to serialise it into text first only for the library to parse it back.

## Decision

The canonical form is a typed **block tree** (an AST) with German domain keys. Markdown with directive blocks is a full projection of that tree, not a second source of truth.

The binding rule: **every construction in the block tree must have a Markdown spelling, and the conversion tree to Markdown and back to tree must be the identity.** A test checks this for each block type. Whatever does not survive the round trip is not admitted to the tree.

## Rationale

The tree can be validated against a schema and can be produced directly by the calling tools, which is what makes it a workable contract on the machine side. It uses German domain keys because the project names its domain types in the language of its authors; that is a project preference, not a load-bearing part of the design.

Markdown remains the surface, because language models write it most reliably and operators can correct it without any training.

The round-trip rule is the price of having two formats. Without it, every edit made in Markdown silently destroys tree detail that Markdown cannot express, and a lossy canonical format is worse than a restricted one.

Rejected alternatives:

- **Markdown alone as the contract.** Git-friendly and free of the round-trip problem, but it forces every calling tool into text serialisation and leaves schema validation weak.
- **YAML or JSON alone.** Perfect for machines, but editing prose in YAML is unreasonable to ask of anyone, and model output in YAML is more error-prone than in Markdown.
- **A subset of HTML.** The tooling exists, but it invites people to smuggle formatting into the content, which is precisely the separation ADR-0001 establishes.
- **Tree canonical with extra data in a sidecar.** This breaks the rule open and reintroduces the risk of loss through the back door.

## Consequences

Easier: one content document renders for every client; calling tools deliver structured input; validation before rendering becomes possible.

Harder: every new block type costs two implementations plus a round-trip test. The expressive power of the tree is permanently bounded by Markdown, and that is accepted deliberately.

Follow-up work: block type catalogue and schema; fix the directive syntax; round-trip test suite as part of the definition of done for every block type.

## References

- `SPEC.md`
- ADR-0001

---

## Addendum 2026-09-07: the round-trip rule only holds profile-wide

A closer look at the field refutes the rule in the absolute form given above.

John MacFarlane, author of CommonMark, Pandoc and Djot, was asked directly whether AST to Markdown to AST always reproduces the original: **"For all ASTs… certainly not."** The reasons are the context dependence of Markdown, nested emphasis, line breaks that accidentally create block structure, and inconsistent escaping. No formally proven bijection exists in any ecosystem: not in Pandoc, Djot, MyST, remark, ProseMirror, Tiptap, Portable Text or the AsciiDoc ASG.

Measured against Pandoc 3.1.3: a realistic proposal document survived the round trip **byte-identically** with `--standalone --wrap=none`. A deliberately hostile document lost 4 of 228 leaves (column widths, `Plain` becoming `Para`, an alignment specification), all cosmetic. A **`rowspan=2` row span was silently reduced to 1** and was unrecoverable (pandoc#8990, still open).

**Refined decision.** The bijection does not hold for "every conceivable construction" but for **the profile**: the conclusively defined set of permitted block types and attributes. It is not assumed, it is enforced.

1. Only the tree is stored canonically. Markdown is never the recorded truth.
2. **Property-based round-trip tests in CI**: tree to Markdown to tree, structural comparison, failure on any deviation outside an explicit allow list (column widths, `Plain` versus `Para`, alignment specification). A new block type only counts as finished once that test is green for it.
3. **Row spans and column spans are excluded from the profile** for as long as pandoc#8990 remains open. A table that needs them is not a table for this library.
4. Column widths are normalised rather than carried in the tree.
5. Serialisation always uses `--standalone --wrap=none`; without `--standalone`, metadata is lost silently.

The effort for this test harness is estimated at roughly one day, and it is the single most effective measure in the whole design: it turns a hope into a guarantee.

**Consequence for the block type catalogue:** it is designed not around what Word can display but around what demonstrably survives the round trip. That is narrower than originally assumed.
