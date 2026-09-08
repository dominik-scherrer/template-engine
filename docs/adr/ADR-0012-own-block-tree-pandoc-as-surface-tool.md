# ADR-0012: Our own block tree, Pandoc only as a surface tool

**Status:** proposed
**Date:** 2026-09-07

## Context

There is a serious case for adopting the Pandoc AST (`pandoc-types` 1.23) as the canonical structure and storing the domain semantics as a profile in its `Attr` fields, instead of inventing a tree of our own. The argument: a mature typed core, a Markdown surface with a parser and a serialiser, and a proven round-trip tool chain, all for free.

Against it stands ADR-0011, which decided that Pandoc is not the renderer. That removes the single largest benefit of adopting it.

## Decision

The canonical block tree (AST) stays **our own and typed**. Pandoc is used as a library for the **Markdown surface**, not as the data model:

```
Markdown  ⇄  Pandoc AST  ⇄  own block tree  →  python-docx  →  .docx
          ↑              ↑                     ↑
       pandoc         mapping                ADR-0011
                    (our own code)
```

Only our own tree is stored and versioned.

## Rationale

The decisive point is the **version stability of the stored data**. The Pandoc AST carries a `pandoc-api-version`, refuses input that does not match, and undergoes a breaking change roughly every one to two years (1.20 Text, 1.21 Underline and cell spans, 1.22 untagged JSON, 1.23 removed `Null` and added `Figure`). If the Pandoc AST were the canonical form, every one of those changes would touch **every stored document**. As a transit format only, such a change touches nothing but the mapping layer: a few hundred lines, migratable in a day.

The Pandoc dependency therefore sits at the edge of the system rather than in its core, and it can be replaced without touching stored data.

Second, validation. In the Pandoc AST, `leistungstabelle` would be a `Div` class: a string that the AST does not check. A typo would surface only at render time, and possibly not at all. In our own tree it is a type with a schema. For a library whose output goes to clients, that is the difference between a schema error and a silently incorrect deliverable.

Third, and much more weakly, a project preference: the project names its domain types in the language of its authors (German), whereas the Pandoc node types are English. This is a preference, not a justification on its own, and it would not carry the decision without the two arguments above.

What is adopted regardless, because it is the actual work: **parsing and serialising Markdown.** Escaping, context dependence, table syntax, attribute syntax. Writing that ourselves would be the worst investment of time in the whole project. Pandoc does it, in both directions, with `--standalone --wrap=none`.

Rejected alternatives:

- **The Pandoc AST as the canonical form.** Saves the mapping layer, but couples the entire body of stored data to someone else's versioning and gives up schema validation of the domain roles.
- **Fully our own, including the surface.** That means our own Markdown parser and serialiser. Not justifiable.

## Consequences

Easier: the stored data is immune to Pandoc version changes. Domain roles are typed and validatable. Pandoc is interchangeable.

Harder: two mapping directions have to be written and maintained. They are also an additional place where information can be lost, which is why the round-trip test harness from the ADR-0002 addendum must run **across the entire chain**: own tree, Pandoc AST, Markdown, Pandoc AST, own tree, with identity as the condition. Not just across the Markdown half.

The block type catalogue is thereby constrained from two sides: whatever our own tree can express must be representable in the Pandoc AST and must also survive the Markdown round trip. Row and column spans drop out on those grounds anyway (pandoc#8990).

**As the editing surface**, Pandoc Markdown is used with `+fenced_divs +bracketed_spans +grid_tables +table_captions +header_attributes`, measured byte-identical across the round trip on a realistic proposal document. Djot would be easier for a language model to emit without errors, but it stands at version 0.3.2; to be re-evaluated once 1.0 is available.

## References

- ADR-0002 including its addendum, ADR-0011
- [pandoc#8990](https://github.com/jgm/pandoc/issues/8990)
