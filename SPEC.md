# Template Engine: Specification

**Date:** 2026-09-07 · **Version:** 0.4 · **Status:** design draft, no implementation yet

## Purpose

The library ingests a client's document template and derives a reusable **style profile** from it. Using that profile it renders arbitrary, freely structured content documents as `.docx` files that look as though they had been written in the client's own template, without the document's structure having to be laid out in the template in advance.

## Scope and boundaries

This is a library. A host application imports it (ADR-0013). The division of labour is fixed:

| The library does | The caller does |
|---|---|
| Parse a template's styles, numbering, section properties, headers and footers | Decide which template to ingest and where it came from |
| Derive a role mapping and a capability profile | Present proposals to a person and collect confirmation |
| Locate zone boundaries and write binding sites | Supply a proposer, if any, and choose the model behind it |
| Produce a prepared base document and a serialisable style profile | Persist and version profiles and documents |
| Render a content document against a profile | Store, deliver and display the resulting file |
| Validate structural conformance before emitting | Present warnings and errors |

The library opens no database connections, calls no model, renders no interface, and keeps no state between calls.

## Architecture

### 1. Ingest, once per client template

Input: an empty `.dotx` or `.docx` carrying the house layout, or several completed example documents, or a PDF.

Output: a **style profile** with four parts.

- **Prepared base document.** The client file, augmented with Jinja tags at the binding sites, bookmarks at each zone boundary, and, where necessary, harvested style definitions (ADR-0009). It carries `styles.xml`, `numbering.xml`, the theme, headers and footers, section properties and the letterhead. The unmodified original is returned alongside it. Visual fidelity comes from the client file itself, not from reconstructed formatting.
- **Zone sequence.** The ordered list of retained and generated regions with their boundaries (ADR-0008).
- **Role mapping.** Semantic role to the client's actual style, for example `ueberschrift_1` to `"Titel 1"`, `legende` to `"Beschriftung"`, `tabelle_standard` to `"Tabellenraster hell"`. Each entry records its origin as detected or inferred.
- **Capability profile.** What this template can do: available heading levels, list formats, table styles, whether a table-of-contents style exists, and which `SEQ` labels the template's figure and table lists count.

Ingest returns proposals; it applies nothing until the caller passes back a confirmed result. Templates without named styles are processed, but with a visible warning (ADR-0007).

An updated client template is prepared again from scratch, with no carry-over from the previous version (ADR-0009). The result is a new profile version (ADR-0004).

### 2. Zones

A document is not homogeneous. It is a sequence of **zones**, each retained or generated (ADR-0008):

| Zone | Treatment | Typical content |
|---|---|---|
| Retained | copied through unchanged, Jinja tags substituted, Word fields left as fields | title page, version and change table, table of contents, list of figures and tables |
| Generated | cleared and rebuilt from the block tree | the document body proper |

Version 1 uses the sequence retained (front) then generated (body). The model permits any number of zones so that a retained back section, a signature block, terms and conditions, appendices, can be added later without changing the model.

Retained zones allow value substitution and conditionals, but not loops (ADR-0010). Variable length is the defining property of the generated region.

The table of contents in the retained front picks up the generated body's headings automatically when fields are updated. The two zones interlock rather than interfering.

### 3. Content document

The content of one document, independent of any template. A **block tree** (an AST) of typed nodes carrying no formatting whatsoever:

```yaml
dokument:
  metadaten:
    titel: "Migration assessment"
    stilprofil_version: 3
  bloecke:
    - typ: ueberschrift
      ebene: 1
      text: "Background"
    - typ: absatz
      text: "Acme Corp plans to consolidate ..."
    - typ: tabelle
      rolle: leistungstabelle
      kopfzeile: ["Item", "Result", "Days"]
      zeilen: [["...", "...", "12"]]
    - typ: abbildung
      quelle: "asset://scope-diagram"
      legende: "Project scope"
```

The tree is canonical. People and language models edit it as Markdown with directive blocks; conversion in both directions is lossless within a defined profile and enforced by tests (ADR-0002, ADR-0012).

Because structure lives in the content document rather than in the template, sections may be omitted, added or reordered per document.

### 4. Rendering

Technical substrate: `python-docx`. Pandoc is used only for the Markdown surface, never to render (ADR-0011, ADR-0012).

Open the prepared base document, leave retained zones standing and substitute their tags, clear the generated zone while preserving headers, footers and section properties, walk the block tree, apply for each block the style resolved through the role mapping, set `SEQ` fields in captions so the front matter's lists collect them (the only field the library generates: table of contents, chapter numbering and page numbers all follow from the retained zone and from styles, see ADR-0003), run the structural conformance check, emit `.docx`.

## Interface sketch

Illustrative, not final. It exists to make the library boundary concrete.

```python
# Ingest: propose, then apply what the caller confirmed.
proposals = ingest.analyse(template_bytes, proposer=my_proposer)   # proposer optional
profile   = ingest.apply(template_bytes, confirmed=reviewed_proposals)

profile_json  = profile.to_json()        # caller persists this
prepared_docx = profile.prepared_bytes   # and this

# Render: pure function, no I/O the caller did not ask for.
profile  = StyleProfile.from_json(profile_json, prepared_bytes=prepared_docx)
document = ContentDocument.from_markdown(md_text)   # or .from_tree(tree)
docx     = render(document, profile)                # raises on conformance failure
```

## Data flow

| What | From | To |
|---|---|---|
| Client template (original) | caller | returned unchanged, caller stores it |
| Prepared base document | ingest, after confirmation | returned as bytes, caller stores per profile version. Never delivered to the client. |
| Style profile | ingest, after confirmation | returned as a serialisable value |
| Content document | caller, or authored as Markdown | serialisable as JSON and as Markdown |
| Rendered document | render | returned as bytes |

Everything the library produces round-trips through export and import. No artifact exists only inside the library.

## Where a model is used

Deterministic, no model involved: parsing `styles.xml`, `numbering.xml`, `sectPr`, headers and footers; the entire rendering path; the conformance check; the Markdown and block tree conversions.

A caller-supplied **proposer** may be used at ingest, where structure is genuinely absent:

1. **Role recognition for ambiguous style names.** A style called `Corp_H1_Blue` has to be matched to the role `ueberschrift_1`.
2. **Structure recognition in example documents** that carry no named styles: deriving heading levels from formatting patterns.
3. **Binding site recognition on the title page.** Recognising that `Acme Corp` is the client-name slot and `Version 1.2 / 14.03.2026` are version and date, and proposing where the tags belong.
4. **Boundary proposal** from the template's structure.

All four return proposals for human review. None of them run at render time, and the library itself never calls a model: it invokes whatever proposer the caller passes, or none.

## Document properties

The renderer sets title, author and company cleanly and leaves no tooling traces (no `python-docx` in the author field). The values are supplied by the caller.

## Assumptions

- The client permits their template to be used this way, and a copy to be kept.
- Templates are predominantly `.dotx` or `.docx`. A PDF-only template is a special case requiring manual reconstruction, not an automated path.
- The recipient has Word or LibreOffice available to update fields.

## Open questions

1. **Language-dependent style names.** Word's built-in styles are named per installation language: `"Überschrift 1"`, `"Heading 1"`, `"Titre 1"`. The role mapping must resolve to the internal `styleId`, not the display name, or the same profile breaks on a differently localised Word installation. To settle before implementation.
2. **Section properties at the zone boundary.** Front matter and body often use different page numbering (roman, then arabic) and the section break sits exactly on the boundary. Clearing the generated zone must not take the section structure with it. The most delicate part of the implementation; it needs its own test.
3. **`SEQ` labels.** The retained front's list of figures counts `SEQ` fields carrying a particular label. Captions generated in the body must use the same one: `Abbildung` and `Figure` produce two separate sequences. The label has to be harvested into the capability profile.
4. **Image handling.** How the block tree references figures, and who is responsible for resolution and scaling.
5. **Field-bound headers and footers.** Client templates often carry placeholders in the footer (document number, classification). These sit outside the body and therefore outside the zone model; whether tags are set there too is open.
6. **Section breaks inside the body.** Landscape pages, differing margins: how far must the block tree be able to express section changes?
7. **Proving the preparation invisible.** How is it guaranteed that inserting tags and bookmarks changes nothing about appearance outside the substitution sites?
8. **Conformance evidence.** Version 1 relies on structural checking plus human review (ADR-0006). At what point does volume justify a visual comparison?

## References

- `docs/adr/` : ADR-0001 to ADR-0013
- `docs/GLOSSARY.md`
