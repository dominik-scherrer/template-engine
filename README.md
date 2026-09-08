# Template Engine

A library that ingests a client's Word template and renders freely structured content as `.docx` files that look as though they had been written in that template.

**Status: design, no implementation yet.** This repository currently holds a specification, thirteen architecture decision records and a glossary, deliberately written before any code.

## The problem

A client hands over an empty `.dotx` carrying their house layout. You have to deliver documents in it that are indistinguishable from ones written in that template, while the structure varies freely: sections are dropped, added or reordered, and the number of team members, line items or milestones is not known in advance.

The usual approach, a skeleton with `{{PLACEHOLDER}}` holes, cannot do this. Placeholder substitution presupposes a fixed structure. Here there is none.

## The approach

**Visual fidelity comes from the template's style definitions, not from a reconstructed layout.** Rendering opens the client's file, leaves retained regions standing, clears the generated region and writes new paragraphs referring to the client's own named styles. Structure and appearance are fully decoupled, so one content document renders correctly for any client.

A document is a sequence of **zones**:

| Zone | Treatment | Content |
|---|---|---|
| Retained | copied through, Jinja tags substituted, Word fields left as fields | title page, version table, tables of contents and figures |
| Generated | cleared and rebuilt from the block tree | the document body |

Placeholders still exist, but only in the retained zone, where the structure genuinely is fixed.

## How it runs

**Ingest, once per client template.** A caller-supplied proposer suggests where the binding sites are and which style corresponds to which semantic role; a person confirms; the result is a serialisable **style profile** made of a prepared base document, a zone sequence, a role mapping and a capability profile.

**Render, per document.** Fully deterministic, no model involved: block tree plus style profile to `.docx`.

## Boundaries

This is a library, not a service or an application (ADR-0013). It owns no database, calls no model, renders no interface and keeps no state between calls. It returns serialisable values and proposals; the caller persists, versions, and collects human confirmation.

```python
proposals = ingest.analyse(template_bytes, proposer=my_proposer)
profile   = ingest.apply(template_bytes, confirmed=reviewed_proposals)

document = ContentDocument.from_markdown(md_text)
docx     = render(document, profile)
```

## Layout

```
SPEC.md                     specification: scope, architecture, data flow, open questions
docs/
  adr/ADR-0001 ... 0013     architecture decision records
  GLOSSARY.md               terms
```

## The decisions in brief

| ADR | Decision |
|---|---|
| 0001 | Style profile instead of a placeholder template |
| 0002 | Block tree canonical, Markdown as the editing surface; round-trip rule enforced by tests |
| 0003 | Real Word fields, resolved by the recipient's word processor |
| 0004 | Style profiles carry a version identity; the caller persists them |
| 0005 | One-way rendering in v1, reading documents back deliberately left possible |
| 0006 | Structural conformance check, no visual verification in v1 |
| 0007 | Harvest styles when a template has none, but warn and offer a way back |
| 0008 | Zone model: retained and generated regions |
| 0009 | Prepared base document; a proposer runs at ingest, never at render |
| 0010 | Tags allow substitution and conditionals, not loops |
| 0011 | `python-docx` as the renderer, with a minimal field surface |
| 0012 | Own block tree; Pandoc used only as a surface tool |
| 0013 | A standalone library, not a component of a host |

## Prior art

The closest existing implementation is [docxbuilder](https://github.com/amedama41/docxbuilder), a Sphinx extension which already does arbitrary base document as style source, configurable role to style-name mapping, and cover page retention with a three-tier fallback. It is unmaintained since 2020 and coupled to reStructuredText, so it is a source of patterns rather than a dependency.

Pandoc's `--reference-doc` proves the underlying concept, resolving styles by name from a reference document, but it discards the reference document's body entirely, emits a single `sectPr`, hardcodes one table style name and generates no figure numbering. Those four limits are why it cannot serve as the renderer here.

## Current state

The first thing built is the **round-trip gate** from the addendum to ADR-0002, before any renderer code, so that the round-trip rule constrains the block type catalogue as it grows rather than being checked after the fact.

Implemented so far:

- the canonical block tree (`src/template_engine/baum.py`), with a minimal catalogue: document, heading, paragraph;
- the Markdown surface (`markdown_surface.py`), a lossless projection of the tree, with pandoc used only as the Markdown parser and serialiser (ADR-0012);
- the gate itself (`tests/`): a property-based round-trip test over a hostile alphabet, plus anchored examples and a loud-failure check.

Not yet built: the renderer (ADR-0011), ingest and the zone model (ADR-0008, ADR-0009), style profiles (ADR-0004). See `docs/round-trip-gate.md` for the definition of done that governs every new block type.

## Development

```
python -m pip install -e ".[dev]"
pytest -q --hypothesis-show-statistics   # the gate
ruff check src tests && mypy             # lint and types
```

Pandoc must be on the PATH; any reasonably recent version works (the mapping detects its API version at runtime).

## Licence

Not yet chosen. This repository is not licensed for reuse until one is added.
