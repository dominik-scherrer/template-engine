"""MCP service around the template engine library (ADR-0014).

The service owns what the library deliberately does not (ADR-0013): a profile
store, approval status, rendered-file delivery and the MCP surface agents call.
The library never imports this package.
"""

from template_engine_server.store import (
    DirectoryProfileStore,
    ProfileNotFound,
    ProfileStore,
    ProfileSummary,
    StoredProfile,
    VersionInfo,
)

__all__ = [
    "DirectoryProfileStore",
    "ProfileNotFound",
    "ProfileStore",
    "ProfileSummary",
    "StoredProfile",
    "VersionInfo",
]
