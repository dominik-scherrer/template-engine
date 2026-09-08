# Notes for the ingest increment (from real templates)

Observations from a set of real `.dotx` templates, recorded to steer the ingest
work (ADR-0008, ADR-0009). No template content is reproduced here; the templates
themselves are confidential and are not part of this repository.

## `.dotx` cannot be opened as a document as-is

Real templates arrive as `.dotx`, whose OOXML content type is
`application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml`.
`python-docx`, and any reader expecting a document, rejects that outright. Ingest
must patch `[Content_Types].xml`, swapping the template main-part content type
for the document one, before the base document can be opened. The unmodified
original is still kept as the artifact (ADR-0009); only a working copy is
re-typed.

## Map roles by styleId, not display name

This confirms SPEC open question 1 with real data. A style's display name
(`w:name`) and its `w:styleId` diverge, and the styleId is ASCII-folded: a
display name containing an umlaut yields a styleId with the umlaut dropped (for
example a heading named with "ü" produces a styleId with the "ü" removed).
Worse, two templates from the same family used, for the same visual heading, a
built-in style in one and a custom style of the same display name in the other.

The role mapping must therefore resolve to `w:styleId`, and ingest must record
the `(styleId, display name, custom?)` triple, not the name alone. The current
renderer matches by display name (via python-docx) and will need revisiting when
ingest lands.

## The zone model matches real structure

Real templates carry named styles for a title page, an imprint / legal block,
and a table of contents, i.e. exactly the retained-front content that ADR-0008
anticipates. The front is not separated by a section break: the templates use a
single section with a different first-page header. So the zone boundary is a
paragraph position within one section, and header/footer handling has to cope
with first-page-different layouts rather than assuming one header per section.

## Tables are ubiquitous

Every template used several tables, each with a dedicated table style and its own
set of cell paragraph styles. The table block type is a prerequisite for real
output, not an optional extra.

## Consequence for test fixtures

Because real templates are confidential and gitignored, any test that renders
into one must skip when the file is absent, so CI (which never has them) stays
green. Synthetic base documents (`tests/basis.py`) remain the portable fixtures;
the real templates are a local, opt-in check.
