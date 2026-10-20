# ADR-0014: An MCP service with a server-side profile store

**Status:** proposed
**Date:** 2026-10-20

## Context

The library (ADR-0013) turns a block tree and a style profile into a `.docx`. It deliberately leaves persistence, versioning, model calls and human review to its caller.

The callers that matter are agents: assistants built in low-code agent platforms, general-purpose chat assistants, and in-house applications. They should only produce Markdown content. How a document looks is settled by the client template. The Model Context Protocol (MCP) is the integration surface these agents share, so a service exposing the library over MCP is the natural caller.

That service has to answer three questions the library leaves open:

1. Where do profiles live?
2. How does a profile get created?
3. Who vouches for a profile before it is used?

## Decision

### A separate service wraps the library

The service lives beside the library and imports it. The library never imports the service, and keeps its ADR-0013 guarantees: no storage, no model calls, no interface.

### Profiles are stored server-side; agents pass a name

A profile consists of two parts that are stored together, as one immutable version:

- the mapping (`profile.json`): which style each role uses, the binding sites, and where the generated body starts;
- the base document, which carries the styles, headers, footers and retained front pages.

```
profiles/<client>/<template>/v<n>/{profile.json, base.docx, original.dotx, meta.json}
```

Agents reference a profile by name. They get the newest version by default and can pin an older one (ADR-0004). The store sits behind a small `ProfileStore` interface. The first implementation is a directory on disk; a database or an object store can replace it later.

### Tools

| Tool | Purpose |
|---|---|
| `list_profiles()` | Names, versions and approval status |
| `format_guide(profile)` | What Markdown this profile accepts (roles, binding sites) |
| `render(profile, markdown, values?)` | Renders a `.docx` and returns a download link |
| `start_onboarding()` | Opens a draft and returns a one-time upload link for the template file |
| `get_onboarding_context(draft_id)` | Returns the extracted context, the proposing instructions and the proposal's JSON schema |
| `submit_proposal(draft_id, proposal)` | Validates a proposal and returns warnings plus a test-render link |
| `propose(draft_id)` | Fallback: the server proposes, using its own configured model or the heuristic proposer |
| `publish_profile(draft_id, name)` | Stores the draft as a new profile version |

### Onboarding through the calling agent, with the server as fallback

The proposing step is a prompt plus context. The server delivers both as an ordinary tool result: the style inventory, the paragraph sequence, the instructions and the JSON schema. The calling agent's own model writes the proposal and submits it. The server validates it against the base document (ADR-0006) before anything is stored.

If the agent cannot or should not propose, `propose` runs the same step on the server. It uses an OpenAI-compatible endpoint when one is configured, and the deterministic heuristic proposer otherwise.

The calling agent is treated as one more implementation of the library's proposer seam. Proposals stay data: nothing is applied until the profile is published.

### Template files travel by upload link, not as tool arguments

A template is often several megabytes of binary data. Passing it through a tool argument would require the model to reproduce it token by token. Instead, `start_onboarding` returns a short-lived, one-time upload link. A fetch from a document library URL is a possible later addition.

### Allow and warn until an admin approves

Every profile version has an approval status, `unapproved` or `approved`.

- A version published by an agent is `unapproved`, and it can be used immediately.
- `render` and `list_profiles` carry a warning for unapproved versions, so that the agent can relay it.
- The warning appears **only in the tool response, never in the document**. The output stays exactly what the template defines.
- An admin approves or deactivates a version in the admin interface.
- Approval belongs to one version. A new version starts as `unapproved` again, and the previously approved version stays available to pin.

### Admin interface

A web interface for upload, proposal review, test rendering, approval and version history. It grows out of the demo cockpit and talks to the same store as the MCP tools.

## Rationale

**Name, not payload.** The base document is binary and large. Agent platforms pass tool inputs as model-generated text, and a template copied through a model is slow at best and corrupted at worst. Storing the profile once and referencing it by name also means agents never need access to the client template.

**Agent-side proposing.** The onboarding step needs a capable model and a person in the loop. Both are already present in the conversation with the agent, so the server does not have to own a model to be useful. Returning the instructions in a tool result, rather than relying on optional protocol features such as prompts or sampling, keeps the flow independent of the client.

**Allow and warn.** Blocking unapproved profiles would make an agent-driven onboarding unusable until an admin acts. Silently accepting them would make the human review step meaningless. Warning in the response keeps both: work continues, and the agent tells the person that the template has not been reviewed. Stamping the warning into the document was rejected because the document then no longer looks the way the client template defines.

Rejected alternatives:

- **The agent passes the full profile on every call.** Stateless, but it fails on the binary base document and spreads client templates across every agent.
- **Creation through the admin interface only.** Simpler governance, but onboarding then always needs a separate tool and a separate person.
- **Unapproved profiles stay drafts.** Safe, but it blocks the user who just onboarded a template until someone else reviews it.
- **Upload as a base64 tool argument.** Works for small files in some clients and fails unpredictably for real templates.

## Consequences

Easier: agents only ever deal with a profile name and Markdown. A template is uploaded once and reused by every agent. The service needs no model of its own to support onboarding.

Harder:

- The service now has state, which brings backups, a retention rule for superseded versions (ADR-0004) and deployment.
- Approval status is mutable metadata beside an immutable version. It is kept in `meta.json`, never in `profile.json`, so that a version's identity does not change when it is approved.
- An agent can publish a poor profile and use it at once. The warning makes this visible but does not prevent it.
- Upload links and download links need expiry and must not be guessable.

Open, to be decided before the service is exposed beyond a local machine:

- authentication for MCP clients and for the admin interface;
- whether rendered documents are delivered as a link or written to the caller's document library;
- hosting per client, given data classification of client templates.

## References

- `SPEC.md`
- ADR-0004, ADR-0006, ADR-0009, ADR-0013
