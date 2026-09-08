# Glossary

Terms used throughout this project. Domain types in the block tree are named in German, a project preference explained in ADR-0012; the surrounding documentation is English.

---

**Base document**
The client's Word file, opened as the carrier document at render time. It supplies `styles.xml`, `numbering.xml`, the theme, headers and footers, and section properties. Only the generated zone is cleared; retained zones stay. The source of visual fidelity. Rendering always uses the *prepared* base document.

**Binding site** (Jinja tag)
A substitution point in a retained zone: `{{ kunde_name }}` or `{% if vertraulich %}`. Written once during preparation and substituted deterministically at render time. Value substitution and conditionals are permitted; loops are not (ADR-0010).

**Block**
A node of the block tree with a type: `ueberschrift`, `absatz`, `aufzaehlung`, `tabelle`, `abbildung`, `seitenumbruch`, `querverweis`. Carries content and semantic role, never formatting.

**Block tree** (AST)
The canonical form of a content document: a tree of typed blocks describing what the document means without describing how it looks. `ueberschrift(ebene=1)` says "top-level heading", not "14pt Arial bold".

**Body boundary**
The boundary between the retained front and the generated body. Written into the prepared base document as a Word bookmark during preparation, and recorded as a paragraph range in the style profile as well; the bookmark takes precedence.

**Capability profile**
Part of the style profile. Records what a template can do: available heading levels, list and table styles, whether a table-of-contents style exists, and which `SEQ` labels its figure and table lists count. Makes it possible to warn that a block cannot be represented in this template.

**Conformance check**
An automatic check before output: every style name the renderer uses exists in the base document, every role occurring in the block tree is mapped, no paragraph carries direct formatting, and the base document's headers, footers and section properties are intact. A failure aborts rendering rather than warning.

**Content document**
The content of one document, independent of any template. Canonically a block tree; edited as Markdown with directive blocks.

**Direct formatting**
Formatting applied straight to a paragraph or run instead of coming from a named style. Unwanted in generated output: the conformance check flags it.

**Field**
A value computed by Word inside the document: `TOC`, `SEQ`, `REF`, `STYLEREF`. The library emits fields and leaves resolution to the recipient's word processor (ADR-0003). Only `SEQ` in captions is generated; the rest are inherited from the retained zone or follow from styles.

**Generated zone**
The region cleared at render time and rebuilt from the block tree: the document body. The only place where content of variable length may arise.

**Ingest**
The one-off process of deriving a style profile from a client template. Deterministic where the template carries named styles; assisted by a caller-supplied proposer where roles must be guessed. Always ends with human confirmation, which the caller collects.

**Markdown with directives**
The editing surface for a content document. Prose stays ordinary Markdown; tables, figures, captions and cross-references use `:::` blocks. A projection of the block tree, never a source of truth of its own.

**Prepared base document**
The client file after preparation: with Jinja tags, bookmarks at the zone boundaries, and any harvested styles. Immutable per profile version. **Never delivered to the client**; only the rendered result is.

**Preparation**
The part of ingest that modifies the client file: setting tags, writing bookmarks, harvesting styles. A caller-supplied proposer suggests the locations, a person confirms. Redone completely for every template change, with no carry-over (ADR-0009).

**Proposer**
An interface the caller supplies so that ingest can suggest role mappings, binding sites and boundaries. Usually backed by a language model. Optional: without one, ingest falls back to what it can determine deterministically. The library never calls a model itself (ADR-0013).

**Rendering**
Block tree plus style profile to `.docx`. Fully deterministic, no model involved.

**Retained zone**
A region copied unchanged from the prepared base document: title page, version table, tables of contents and figures. Jinja tags within it are substituted and Word fields stay fields. Nothing else is touched.

**Role**
The semantic meaning of a block, independent of any client: `ueberschrift_1`, `legende`, `leistungstabelle`, `aufzaehlung_standard`. The link between content document and style profile.

**Role mapping**
Part of the style profile. Maps a role to the client's actual style, recording for each entry whether its origin was `erkannt` (detected) or `abgeleitet` (inferred, see ADR-0007). The critical path of the whole library: if it points at nothing, Word falls back to the default paragraph style and the entire document renders flat.

**Round-trip rule**
The binding constraint from ADR-0002: every construct in the block tree has a Markdown spelling, and block tree to Markdown and back is the identity. Holds for a defined profile of block types, not universally, and is enforced by property-based tests rather than assumed.

**Style harvesting**
Deriving roles from formatting patterns and generating named styles when a client template carries none. Always accompanied by a warning and by the note that a properly formatted `.dotx` can be ingested again (ADR-0007).

**Style ID** (`styleId`)
A Word style's internal, language-independent identifier, as opposed to its display name, which reads `"Überschrift 1"`, `"Heading 1"` or `"Titre 1"` depending on the installation language. The role mapping must resolve to the style ID. See open question 1 in `SPEC.md`.

**Style profile**
The result of ingest and the library's central data structure: prepared base document, zone sequence, role mapping, capability profile. Serialisable in full; the caller persists and versions it (ADR-0004, ADR-0013).

**Template**
What the client supplies: an empty `.dotx` or `.docx` carrying the house layout, completed example documents, or a PDF.

**Zone**
A contiguous region of the document, either retained or generated. The zone sequence is part of the style profile. The founding insight of the model: a document is not homogeneous, and retained and generated regions require different treatment (ADR-0008).
