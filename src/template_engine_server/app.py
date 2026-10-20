"""The MCP server: three tools for agents, plus a download route.

Agents only ever pass a profile name and Markdown (ADR-0014). Everything about
appearance comes from the stored profile.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import anyio
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from starlette.requests import Request
from starlette.responses import FileResponse, JSONResponse, Response

import template_engine as te
from template_engine_server.drafts import DraftStore
from template_engine_server.files import RenderedFiles
from template_engine_server.guide import format_guide as build_guide
from template_engine_server.store import (
    ProfileNotFound,
    ProfileStore,
    ProfileUnavailable,
    StoredProfile,
    VersionInfo,
)

__all__ = ["build_server", "unapproved_warning"]

INSTRUCTIONS = """\
Renders documents in a client's Word template. You write content, the template decides the look.

1. list_profiles: find the profile for the client and document type.
2. format_guide(profile): read which Markdown that profile accepts. Read it before writing.
3. render(profile, markdown): returns a download link to the .docx.

Write only the document body as plain Markdown; never try to style it. If a result carries a
warning, tell the user.
"""


def unapproved_warning(info: VersionInfo) -> str:
    return (
        f"Profile '{info.name}' v{info.version} has not been approved by an admin yet. "
        "Tell the user that this template mapping is unreviewed."
    )


def _warnings(info: VersionInfo) -> list[str]:
    return [unapproved_warning(info)] if info.status == "unapproved" else []


def build_server(
    store: ProfileStore,
    files: RenderedFiles,
    public_url: str | None = None,
    drafts: DraftStore | None = None,
    admin_token: str | None = None,
) -> MCPServer:
    """``public_url`` is the externally reachable base of this server (used for
    download links). Without it, ``render`` returns a local file path instead,
    which is what a stdio client on the same machine wants.

    With ``drafts``, the admin interface is mounted at ``/admin`` (HTTP only).
    """
    server = MCPServer(name="template-engine", instructions=INSTRUCTIONS)
    basis_url = public_url.rstrip("/") if public_url else None

    def laden(profile: str, version: int | None) -> StoredProfile:
        try:
            return store.get(profile, version)
        except ProfileNotFound as e:
            raise ToolError(f"{e}. Call list_profiles to see the available profiles.") from e
        except ProfileUnavailable as e:
            raise ToolError(str(e)) from e
        except ValueError as e:  # malformed name
            raise ToolError(str(e)) from e

    @server.tool()
    def list_profiles() -> dict[str, Any]:
        """List the available client template profiles with their versions and approval status."""
        out = []
        for p in store.profiles():
            neueste = p.latest
            eintrag: dict[str, Any] = {
                "name": p.name,
                "latest_version": neueste.version if neueste else None,
                "status": neueste.status if neueste else "deactivated",
                "versions": [
                    {"version": v.version, "status": v.status, "created_at": v.created_at}
                    for v in p.versions
                ],
            }
            if neueste and neueste.status == "unapproved":
                eintrag["warning"] = unapproved_warning(neueste)
            out.append(eintrag)
        return {"profiles": out}

    @server.tool()
    def format_guide(profile: str, version: int | None = None) -> str:
        """Describe which Markdown a profile accepts. Read this before writing content for it.

        Args:
            profile: profile name as '<client>/<template>', from list_profiles.
            version: pin a specific version; omit for the newest.
        """
        gespeichert = laden(profile, version)
        text = build_guide(gespeichert.info.name, gespeichert.info.version, gespeichert.profile)
        warnungen = _warnings(gespeichert.info)
        return ("Warning: " + warnungen[0] + "\n\n" + text) if warnungen else text

    def _render_sync(
        profile: str, markdown: str, version: int | None, filename: str | None
    ) -> dict[str, Any]:
        gespeichert = laden(profile, version)
        try:
            dok = te.from_markdown(markdown)
        except ValueError as e:
            raise ToolError(
                f"The Markdown uses something this profile does not support: {e}. "
                f"Call format_guide('{profile}') and rewrite accordingly."
            ) from e
        try:
            docx = te.render(dok, gespeichert.profile, gespeichert.base_docx)
        except te.UnbekannteRolle as e:
            raise ToolError(
                f"{e}. The content uses an element this profile has no style for. "
                f"Call format_guide('{profile}') to see what is allowed."
            ) from e
        except te.FehlenderStil as e:
            raise ToolError(f"The stored profile is broken: {e}. Ask an admin to fix it.") from e

        abgelegt = files.put(docx, filename or gespeichert.info.name.replace("/", "-"))
        ergebnis: dict[str, Any] = {
            "filename": abgelegt.filename,
            "profile": gespeichert.info.name,
            "version": gespeichert.info.version,
            "status": gespeichert.info.status,
            "expires_at": datetime.fromtimestamp(abgelegt.expires_at, timezone.utc).isoformat(
                timespec="seconds"
            ),
            "warnings": _warnings(gespeichert.info),
        }
        if basis_url:
            ergebnis["download_url"] = f"{basis_url}/files/{abgelegt.token}/{abgelegt.filename}"
        else:
            ergebnis["path"] = str(abgelegt.path.resolve())
        return ergebnis

    @server.tool()
    async def render(
        profile: str,
        markdown: str,
        filename: str | None = None,
        version: int | None = None,
    ) -> dict[str, Any]:
        """Render Markdown into the client's Word template and return a link to the .docx.

        Args:
            profile: profile name as '<client>/<template>', from list_profiles.
            markdown: the document body, following format_guide for this profile.
            filename: optional name for the file, without path.
            version: pin a specific profile version; omit for the newest.
        """
        return await anyio.to_thread.run_sync(_render_sync, profile, markdown, version, filename)

    async def download(request: Request) -> Response:
        pfad = files.resolve(request.path_params["token"], request.path_params["filename"])
        if pfad is None:
            return JSONResponse({"error": "not found or expired"}, status_code=404)
        return FileResponse(
            pfad,
            filename=pfad.name,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

    async def health(request: Request) -> Response:
        return JSONResponse({"status": "ok"})

    # Registered without decorator syntax: the SDK's decorator is untyped.
    server.custom_route("/files/{token}/{filename}", methods=["GET"], include_in_schema=False)(
        download
    )
    server.custom_route("/health", methods=["GET"], include_in_schema=False)(health)

    if drafts is not None:
        from template_engine_server.admin import mount_admin

        mount_admin(server, store, drafts, admin_token)

    return server
