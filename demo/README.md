# Demo

A small, runnable illustration of what the library does today. Nothing here
needs an install or any client data.

## Render the same content into two house styles

```
python demo/run_demo.py
```

It reads `content.md`, parses it into the canonical block tree, shows that the
tree survives a Markdown round trip unchanged, then renders that one tree into
two different base documents whose style names differ. The output `.docx` land
in `demo/out/` (gitignored).

The takeaway is the design's central bet (ADR-0001): the content document
carries no formatting, so the same structure renders correctly into whatever
named styles a client's template happens to use. Structure is decoupled from
look.

## Preview the ingest step on a real template

```
python demo/inspect_template.py path/to/some_template.dotx
```

It opens a real `.dotx` (working around the template content type that document
readers reject) and prints the style inventory keyed by `styleId`, with display
names and which styles are custom. This is the extract half of ingest
(ADR-0009); it renders nothing, because retaining a real title page needs the
zone model, which is not built yet. Run with no argument to scan
`tests/example documents` if that (gitignored, confidential) folder is present.

## What this demo does not show yet

Tables, the zone model (retaining a title page and table of contents while
regenerating the body), and mapping roles by `styleId` rather than display name.
Those are the next increments; see `docs/ingest-notes.md`.
