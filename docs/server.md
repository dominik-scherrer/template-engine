# The MCP server

`template_engine_server` wraps the library as an MCP service (ADR-0014). Agents call three tools and only ever pass a profile name and Markdown. The stored client template decides the look.

| Tool | Returns |
|---|---|
| `list_profiles()` | Profiles with versions and approval status |
| `format_guide(profile, version?)` | Which Markdown this profile accepts, with an example |
| `render(profile, markdown, filename?, version?)` | A download link (HTTP) or a local path (stdio) to the `.docx` |

Results for a profile version that no admin has approved yet carry a `warnings` entry. The document itself is never marked.

Not built yet: the agent onboarding tools (`start_onboarding`, `submit_proposal`, `propose`, `publish_profile`) and authentication for MCP clients. Until that exists, keep the server on `127.0.0.1`.

## Install

```
uv sync --extra server --extra pandoc
```

or `pip install -e ".[server,pandoc]"`. The `pandoc` extra bundles a pandoc binary, so nothing else is needed.

## Admin interface

`serve` (HTTP) also serves an admin page at `http://127.0.0.1:8765/admin`:

- the profiles with their versions and approval status; approve, revoke, deactivate;
- per version: the mapping, the format guide agents receive, and a test render with preview;
- new profile or new version: drop a template, adjust the proposed mapping (heuristic, or the model if `TEMPLATE_ENGINE_LLM_*` is set on the server), pick where the generated body begins, test-render, publish.

### Kept front pages

A template's opening pages (cover, imprint, version table, table of contents) are kept exactly as they are, images included; only the body after them is replaced by the agent's content (ADR-0008). The admin page lists the template's top-level blocks and proposes where the body begins: the first top-level heading on a later page than the start. Click another block to change it. Publishing writes a hidden bookmark (`_TE_Body`) at that position into the stored base document. Boundary `0` means the whole body is generated, which suits letters and other templates without front matter.

Title-page values (client name, date, version) are not filled in yet; the kept pages show the template's own text.

The preview is drawn in the browser by [docx-preview](https://github.com/VolodymyrBaydalka/docxjs), vendored in `src/template_engine_server/static/vendor`, so the page makes no third-party requests. It gives a rough idea; Word's own layout (page breaks, fields such as the table of contents) can differ.

Access: without an admin token the admin page and API only answer requests from the same machine. With `--admin-token` (or `TEMPLATE_ENGINE_ADMIN_TOKEN`) they answer anywhere, and the page asks for the token once per browser session.

## Store a template from the command line

Profiles live in `./data/profiles` (change with `--data` or `TEMPLATE_ENGINE_DATA`). The directory is gitignored: it holds client templates.

```
uv run template-engine-server import acme/report path/to/template.dotx
uv run template-engine-server import acme/report template.dotx --mapping mapping.json --approve
uv run template-engine-server import acme/report template.dotx --boundary 12
uv run template-engine-server list
uv run template-engine-server approve acme/report 1
uv run template-engine-server deactivate acme/report 1
```

The import prints which blocks are kept before the body boundary; `--boundary N` sets it explicitly (`0` = whole body generated). Without `--mapping`, the heuristic proposer suggests a mapping and a boundary (`--propose llm` uses the `TEMPLATE_ENGINE_LLM_*` settings instead). A mapping file is a JSON object of role to style name or styleId, or a whole profile (`{"rollen": {...}, "koerpergrenze": 12}`):

```json
{
  "ueberschrift_1": "Heading1",
  "ueberschrift_2": "Heading2",
  "fliesstext": "Normal",
  "aufzaehlung": "ListBullet",
  "nummerierte_liste": "ListNumber"
}
```

Every import is checked with a trial render before it is stored, so a mapping that points at a missing style is refused. Check the proposed mapping before approving: the heuristic is a starting point, not a decision. The demo cockpit (`demo/cockpit.py`) shows the template's styles if you need to pick them by hand.

## Run

Over HTTP (for MCP Inspector, Copilot Studio and other remote clients):

```
uv run template-engine-server serve                      # http://127.0.0.1:8765/mcp
uv run template-engine-server serve --public-url https://te.example.org
```

`--public-url` is the address clients reach the server under; download links are built from it. Links expire after 24 hours (`--ttl-hours`).

Over stdio (a desktop client on the same machine). `render` then returns a local file path:

```json
{
  "mcpServers": {
    "template-engine": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/template-engine",
               "template-engine-server", "--data", "/path/to/data", "serve", "--transport", "stdio"]
    }
  }
}
```

## Try it with MCP Inspector

```
uv run template-engine-server serve
npx @modelcontextprotocol/inspector
```

In the Inspector, choose transport "Streamable HTTP", URL `http://127.0.0.1:8765/mcp`, connect, then call `list_profiles`, `format_guide` and `render`.
