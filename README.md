# Template Engine

A library that ingests a client's Word template and renders freely structured content as `.docx` files that look as though they had been written in that template.

**Status: early working prototype.** The library renders Markdown into a client template, keeping the template's front pages, and an MCP server with an admin page lets agents use stored templates by name. Interfaces will still change. The design (specification, ADRs, glossary) was written before the code and is kept in `SPEC.md` and `docs/`.

## The problem

A client hands over an empty `.dotx` carrying their house layout. You have to deliver documents in it that are indistinguishable from ones written in that template, while the structure varies freely: sections are dropped, added or reordered, and the number of team members, line items or milestones is not known in advance.

The usual approach, a skeleton with `{{PLACEHOLDER}}` holes, cannot do this. Placeholder substitution presupposes a fixed structure. Here there is none.

## The approach

**Visual fidelity comes from the template's style definitions, not from a reconstructed layout.** Rendering opens the client's file, leaves retained regions standing, clears the generated region and writes new paragraphs referring to the client's own named styles. Structure and appearance are fully decoupled, so one content document renders correctly for any client.

A document is a sequence of **zones**:

| Zone | Treatment | Content |
|---|---|---|
| Retained | copied through, Word fields left as fields (Jinja tag substitution planned) | title page, version table, tables of contents and figures |
| Generated | cleared and rebuilt from the block tree | the document body |

Placeholders still exist, but only in the retained zone, where the structure genuinely is fixed.

## How it runs

**Ingest, once per client template.** A caller-supplied proposer suggests where the binding sites are and which style corresponds to which semantic role; a person confirms; the result is a serialisable **style profile** made of a prepared base document, a zone sequence, a role mapping and a capability profile.

**Render, per document.** Fully deterministic, no model involved: block tree plus style profile to `.docx`.

## Boundaries

This is a library, not a service or an application (ADR-0013). It owns no database, calls no model, renders no interface and keeps no state between calls. It returns serialisable values and proposals; the caller persists, versions, and collects human confirmation.

A separate package in this repository, `template_engine_server`, is such a caller: an MCP service with a profile store, so agents can render by profile name (ADR-0014, `docs/server.md`). The library never imports it.

```python
import template_engine as te
from template_engine import ingest

raw = open("template.dotx", "rb").read()

# Ingest, once: propose a mapping and body boundary, have a person confirm them.
proposal = ingest.heuristischer_vorschlag(ingest.kontext_aus_bytes(raw))
profile = te.StyleProfile(
    {role: style for role, style in proposal.rollen.items() if style},
    koerpergrenze=proposal.koerpergrenze,
)
base = te.bereite_vor(ingest.als_dokument_bytes(raw), profile.koerpergrenze or 0)

# Render, per document: deterministic.
docx = te.render(te.from_markdown(open("content.md").read()), profile, base)
```

To run it as a service for agents instead, see `docs/server.md`:

```
uv sync --extra server --extra pandoc
uv run template-engine-server import acme/report template.dotx
uv run template-engine-server serve      # MCP at :8765/mcp, admin page at :8765/admin
```

## Layout

```
SPEC.md                     specification: scope, architecture, data flow, open questions
docs/
  adr/ADR-0001 ... 0014     architecture decision records
  GLOSSARY.md               terms
  server.md                 running the MCP server
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
| 0014 | An MCP service with a server-side profile store; agents onboard, admins approve |

## Prior art

The closest existing implementation is [docxbuilder](https://github.com/amedama41/docxbuilder), a Sphinx extension which already does arbitrary base document as style source, configurable role to style-name mapping, and cover page retention with a three-tier fallback. It is unmaintained since 2020 and coupled to reStructuredText, so it is a source of patterns rather than a dependency.

Pandoc's `--reference-doc` proves the underlying concept, resolving styles by name from a reference document, but it discards the reference document's body entirely, emits a single `sectPr`, hardcodes one table style name and generates no figure numbering. Those four limits are why it cannot serve as the renderer here.

## Current state

The first thing built is the **round-trip gate** from the addendum to ADR-0002, before any renderer code, so that the round-trip rule constrains the block type catalogue as it grows rather than being checked after the fact.

Implemented so far:

- the canonical block tree (`src/template_engine/baum.py`), with a catalogue of document, heading, paragraph, and single-level bullet and numbered lists;
- the Markdown surface (`markdown_surface.py`), a lossless projection of the tree, with pandoc used only as the Markdown parser and serialiser (ADR-0012);
- the gate itself (`tests/`): a property-based round-trip test over a hostile alphabet, plus anchored examples and a loud-failure check;
- a first renderer (`render.py`, `stilprofil.py`): a block tree rendered into a base document against that document's own named styles, clearing the generated region while preserving section properties and headers (ADR-0011); list items render as one styled paragraph each. A minimal `StyleProfile` (role to style-name) drives it, and a structural conformance check refuses a mapping that points at a style the base document does not define (ADR-0006).

- the MCP server (`src/template_engine_server/`): a versioned profile store on disk with approval status, the tools `list_profiles`, `format_guide` and `render`, expiring download links, an admin page at `/admin` with mapping editor and browser preview, and a command line to import and approve templates (ADR-0014, `docs/server.md`).

- the zone model (`zonen.py`, ADR-0008): a retained front (cover page, imprint, version table, table of contents, with their images) is kept verbatim and only the body after a boundary is regenerated. The boundary is a hidden bookmark written into the prepared base document (ADR-0009), with the block index in the profile as fallback; ingest proposes it, a person confirms it in the admin page. A kept table of contents makes Word update fields on opening.

Not yet built: the agent onboarding tools and MCP authentication of the server, filling title-page fields (binding sites, ADR-0009/0010), tables in the generated body, the capability profile, and the `SEQ`/figure work (ADR-0003 addendum). See `docs/round-trip-gate.md` for the definition of done that governs every new block type.

## Development

```
python -m pip install -e ".[dev,server,pandoc]"   # or: uv sync --all-extras
pytest -q --hypothesis-show-statistics            # the gate and all other tests
ruff check src tests && mypy                      # lint and types
```

The `pandoc` extra bundles a pandoc binary. A pandoc on the PATH works too (any reasonably recent version; the mapping detects its API version at runtime), and `TEMPLATE_ENGINE_PANDOC` points at a specific one.

Real client templates are confidential and never part of this repository: `*.docx`/`*.dotx` outside `tests/fixtures` and the server's `data/` directory are gitignored. Tests use synthetic templates.

## Licence

Not yet chosen. This repository is not licensed for reuse until one is added.

The bundled preview libraries keep their own licences: docx-preview (Apache-2.0) and JSZip (MIT), see `src/template_engine_server/static/vendor/`.
