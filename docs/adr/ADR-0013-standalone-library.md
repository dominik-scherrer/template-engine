# ADR-0013: A standalone library, not a component of a host

**Status:** proposed
**Date:** 2026-09-07

## Context

The module was originally conceived as a component inside a larger application: it would read and write that application's database, use its model gateway, present its own screens, and inherit its conventions for storage, versioning and human confirmation.

That framing decides a great deal by accident. It makes the module untestable without the host, unusable by any second caller, and it spreads the module's own concerns (what a style profile is, when a profile is valid) across a codebase that has no particular reason to care.

## Decision

The module is a **standalone library**. A host application imports it. It never reaches back.

Concretely, the library:

- owns no database and opens no connections;
- calls no language model;
- renders no user interface;
- reads and writes files only where the caller hands it paths or file objects;
- returns serialisable values for everything a caller might want to keep.

Everything stateful or interactive belongs to the caller: persisting style profiles, versioning them, showing proposals to a person, collecting that person's confirmation, and choosing which model (if any) proposes anything in the first place.

## Rationale

The split follows the shape of the problem. The valuable and difficult part of this module is deterministic: parsing a template's styles, deriving a role mapping, locating zone boundaries, clearing a paragraph range without destroying section properties, emitting content against named styles. None of that needs a database, a model or a screen. Binding it to infrastructure would make the hard part hostage to the easy part.

Three consequences follow that are worth having on their own:

**Testability.** A deterministic library with file inputs and value outputs can be tested exhaustively against real client templates in ordinary test runs. The round-trip harness required by ADR-0002 becomes an ordinary test suite rather than an integration environment.

**Reusability.** A second caller, a command line tool, a batch job, a different application, costs nothing. Had the module been built into one host, each of those would be a port.

**Honest boundaries.** Forcing every artifact to be serialisable means the library cannot quietly keep state that only it understands. A style profile has to be fully expressible as data, which is what makes ADR-0004's version identity and the export and import requirement possible at all.

Rejected alternatives:

- **Component inside a host application.** Faster to a first working screen, because nothing has to be designed as an interface. Pays for it permanently in testability and in the impossibility of a second caller.
- **A service with its own API and storage.** Solves reuse, but adds deployment, authentication and an upgrade cycle to something that is fundamentally a pure function from (profile, content) to document. Any caller that wants a service can wrap the library in one.

## Consequences

Easier: the library can be developed and tested with no infrastructure at all. Its correctness is decidable from its own test suite.

Harder: everything interactive needs a designed interface rather than an inline call. Two in particular:

1. **Proposals instead of actions.** Ingest cannot pop up a confirmation dialog. It returns proposals as data (a suggested role mapping, suggested binding sites, a suggested boundary), each carrying enough context for the caller to render a review screen, and applies nothing until the caller passes the confirmed result back. See ADR-0009.
2. **Serialisation instead of persistence.** The library produces a style profile as a value plus a prepared base document as bytes. Storing them, versioning them and retrieving the right version is the caller's job. See ADR-0004.

A caller can therefore misuse the library in ways it cannot detect: persisting a profile under the wrong identity, skipping the confirmation step, or feeding back a proposal a human never saw. The library validates what it can (ADR-0006) and documents the rest as the caller's contract.

## References

- `SPEC.md`
- ADR-0004, ADR-0006, ADR-0009
