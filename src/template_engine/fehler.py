"""Errors raised by the renderer.

Kept in their own module so both the style profile and the renderer can raise
them without importing each other.
"""

from __future__ import annotations

__all__ = ["RenderFehler", "UnbekannteRolle", "FehlenderStil"]


class RenderFehler(Exception):
    """Base class for every render-time failure."""


class UnbekannteRolle(RenderFehler):
    """A block needs a role the style profile does not map."""


class FehlenderStil(RenderFehler):
    """The profile maps a role to a style the base document does not define.

    This is the failure the structural conformance check exists to catch
    (ADR-0006): a role mapping that points at a style name absent from the base
    document would otherwise render as the default paragraph style, flattening
    the whole document silently.
    """
