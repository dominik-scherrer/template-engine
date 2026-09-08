# ADR-0004: Versioned style profiles, newest version as the default

**Status:** proposed
**Date:** 2026-09-07

## Context

Clients change their templates: a new logo, a new footer, a different house font. A document that has already been delivered must stay reproducible, and a long-running piece of work should not switch its appearance halfway through. At the same time, new documents should not be stuck on an outdated profile because somebody forgot to promote it.

## Decision

Style profiles are immutable, serialisable values, and each one carries its own version identity.

- A profile is never edited in place. A change produces a new profile that supersedes the earlier one and takes a new version identity.
- Every serialised profile is self-identifying: the identity (which template it describes, and which version of it) travels inside the serialised form, so a profile can be recognised without any surrounding bookkeeping.
- Rendering records in the produced document which profile version it was rendered against.
- Given a set of profiles handed to it by the caller, the library resolves the newest version by default, and accepts an explicitly pinned version instead.

Storing, versioning and expiring those profiles is the caller's job. The library owns no database and no storage; it serialises, and the host application persists.

## Rationale

The split covers both cases without a special path: reproducibility comes from the recorded version, currency from the default.

Superseding rather than mutating is what makes the recorded version meaningful in the first place. A version identity whose content can change later says nothing, so immutability and the identity have to come as a pair.

Because the library holds no storage of its own, the guarantee it can actually give is a representational one: profiles are serialisable, self-identifying and immutable in the library's own handling of them. An append-only history is then a policy the caller can implement cheaply on top, rather than something the library enforces.

Rejected alternative: **one mutable profile per client.** A simpler data model, but re-rendering an old document then silently changes its appearance, which is real damage once that document is already with the client.

## Consequences

Easier: a rendering is exactly repeatable at any time from the same content document and the same profile version. Template changes are traceable. The library fits hosts with very different storage (plain files, an object store, a database), because all it does is serialise.

Harder: the base document belongs to the profile, so every version keeps its own copy of it. Storage grows, and someone has to set a retention rule. The library can neither enforce that rule nor see how many versions exist, so both land squarely on the caller.

The host application has to display which version was used, otherwise pinning is invisible to the person doing the work. The library can only expose the version identity in the render result; it cannot make anyone show it.

Nothing stops a caller from editing a serialised profile in place and keeping the old version identity. The library cannot detect that, and the recorded version then lies. The documentation has to state the rule the caller is expected to keep.

Follow-up work: document the expected retention rule for superseded profile versions; expose the version identity in the render result and in the serialised content document; provide a way for the caller to detect that a piece of work is pinned to a version that is no longer the newest, so that it can warn.

## References

- `SPEC.md`
- ADR-0001, ADR-0013
