"""The admin interface: a page at ``/admin`` and the JSON API behind it.

It works on the same profile store as the MCP tools. Previews are rendered on
the server and drawn in the browser by docx-preview (vendored, see
``static/vendor``), which gives a rough idea of the result, not Word's exact
layout.

Access: with an admin token configured, every API call must send it in the
``X-Admin-Token`` header. Without one, only clients on the loopback interface
are served, so a server exposed by mistake does not expose its admin API.
"""

from __future__ import annotations

import hmac
import json
from collections.abc import Awaitable, Callable
from importlib import resources
from typing import Any

import anyio
from mcp.server.mcpserver import MCPServer
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response

import template_engine as te
from template_engine import ingest
from template_engine_server.drafts import DraftNotFound, DraftStore
from template_engine_server.guide import format_guide, sample_markdown
from template_engine_server.store import (
    STATUSES,
    ProfileNotFound,
    ProfileStore,
    ProfileUnavailable,
)
from template_engine_server.validation import ProfileInvalid, prepare

__all__ = ["mount_admin"]

DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
MAX_UPLOAD = 30 * 1024 * 1024
LOOPBACK = {"127.0.0.1", "::1", "localhost"}
_STATIC = {
    "docx-preview.min.js": "application/javascript",
    "jszip.min.js": "application/javascript",
}

Handler = Callable[[Request], Awaitable[Response]]


class ApiError(Exception):
    def __init__(self, status: int, message: str) -> None:
        super().__init__(message)
        self.status = status


def _static(name: str) -> bytes:
    return resources.files("template_engine_server").joinpath("static").joinpath(name).read_bytes()


def _vendor(name: str) -> bytes:
    statisch = resources.files("template_engine_server").joinpath("static")
    return statisch.joinpath("vendor").joinpath(name).read_bytes()


def _absatzstile(base_docx: bytes) -> list[dict[str, str]]:
    return [
        {"styleId": s["styleId"], "name": s["name"]}
        for s in ingest.stil_inventar(base_docx)
        if s["type"] == "paragraph"
    ]


def _profil_aus(mapping: Any, boundary: Any = None) -> te.StyleProfile:
    if not isinstance(mapping, dict):
        raise ApiError(400, "mapping must be an object of role -> style")
    if boundary is not None and (
        isinstance(boundary, bool) or not isinstance(boundary, int) or boundary < 0
    ):
        raise ApiError(400, "boundary must be a non-negative integer or null")
    return te.StyleProfile(
        {str(k): str(v) for k, v in mapping.items() if v}, koerpergrenze=boundary
    )


def _vorbereitet(profil: te.StyleProfile, base_docx: bytes) -> bytes:
    if profil.koerpergrenze is None:
        return base_docx
    try:
        return te.bereite_vor(base_docx, profil.koerpergrenze)
    except te.ZonenFehler as e:
        raise ApiError(400, str(e)) from e


def _render(markdown: str, profil: te.StyleProfile, base_docx: bytes) -> bytes:
    try:
        return te.render(te.from_markdown(markdown), profil, base_docx)
    except (ValueError, te.RenderFehler) as e:
        raise ApiError(400, str(e)) from e


def mount_admin(
    server: MCPServer,
    store: ProfileStore,
    drafts: DraftStore,
    admin_token: str | None = None,
) -> None:
    def zugelassen(request: Request) -> bool:
        if admin_token:
            gesendet = request.headers.get("x-admin-token", "")
            return hmac.compare_digest(gesendet.encode(), admin_token.encode())
        return request.client is not None and request.client.host in LOOPBACK

    def route(path: str, methods: list[str], api: bool = True) -> Callable[[Handler], Handler]:
        def deco(fn: Handler) -> Handler:
            async def wrapped(request: Request) -> Response:
                if api and not zugelassen(request):
                    return JSONResponse({"error": "admin token required"}, status_code=401)
                if not api and not admin_token and not zugelassen(request):
                    return JSONResponse(
                        {
                            "error": "the admin interface is only served on localhost "
                            "unless an admin token is configured"
                        },
                        status_code=403,
                    )
                try:
                    return await fn(request)
                except ApiError as e:
                    return JSONResponse({"error": str(e)}, status_code=e.status)
                except (ProfileNotFound, DraftNotFound) as e:
                    return JSONResponse({"error": f"not found: {e}"}, status_code=404)
                except ProfileUnavailable as e:
                    return JSONResponse({"error": str(e)}, status_code=409)

            server.custom_route(path, methods=methods, include_in_schema=False)(wrapped)
            return fn

        return deco

    async def body_json(request: Request) -> dict[str, Any]:
        try:
            d = json.loads(await request.body() or b"{}")
        except json.JSONDecodeError as e:
            raise ApiError(400, "request body is not JSON") from e
        if not isinstance(d, dict):
            raise ApiError(400, "request body must be a JSON object")
        return d

    def name_aus(request: Request) -> str:
        p = request.path_params
        return f"{p['client']}/{p['template']}"

    # -- page and assets ------------------------------------------------------

    @route("/admin", ["GET"], api=False)
    async def page(request: Request) -> Response:
        return HTMLResponse(_static("admin.html").decode("utf-8"))

    @route("/admin/vendor/{name}", ["GET"], api=False)
    async def vendor(request: Request) -> Response:
        name = request.path_params["name"]
        if name not in _STATIC:
            raise ApiError(404, "no such file")
        return Response(
            _vendor(name), media_type=_STATIC[name], headers={"Cache-Control": "max-age=86400"}
        )

    # -- profiles -------------------------------------------------------------

    @route("/admin/api/info", ["GET"])
    async def info(request: Request) -> Response:
        return JSONResponse(
            {
                "roles": ingest.ROLLEN,
                "llm": ingest.LLMKonfig.from_env() is not None,
                "statuses": list(STATUSES),
            }
        )

    @route("/admin/api/profiles", ["GET"])
    async def profiles(request: Request) -> Response:
        out = []
        for p in store.profiles():
            out.append(
                {
                    "name": p.name,
                    "latest": p.latest.version if p.latest else None,
                    "versions": [v.to_dict() for v in p.versions],
                }
            )
        return JSONResponse({"profiles": out})

    @route("/admin/api/profiles/{client}/{template}/{version:int}", ["GET"])
    async def version_detail(request: Request) -> Response:
        name, version = name_aus(request), request.path_params["version"]
        summary = next((p for p in store.profiles() if p.name == name), None)
        if summary is None or all(v.version != version for v in summary.versions):
            raise ProfileNotFound(f"{name} v{version}")
        info = next(v for v in summary.versions if v.version == version)
        # A deactivated version is listed but not loaded: it may not be rendered.
        gespeichert = store.get(name, version) if info.status != "deactivated" else None
        if gespeichert is None:
            return JSONResponse({"info": info.to_dict(), "mapping": None, "deactivated": True})
        return JSONResponse(
            {
                "info": info.to_dict(),
                "mapping": gespeichert.profile.rollen,
                "boundary": gespeichert.profile.koerpergrenze,
                "blocks": te.bloecke(gespeichert.base_docx),
                "styles": _absatzstile(gespeichert.base_docx),
                "guide": format_guide(name, version, gespeichert.profile),
                "sample": sample_markdown(gespeichert.profile),
            }
        )

    @route("/admin/api/profiles/{client}/{template}/{version:int}/status", ["POST"])
    async def set_status(request: Request) -> Response:
        status = (await body_json(request)).get("status")
        if status not in STATUSES:
            raise ApiError(400, f"status must be one of {', '.join(STATUSES)}")
        info = store.set_status(name_aus(request), request.path_params["version"], status)
        return JSONResponse({"info": info.to_dict()})

    @route("/admin/api/profiles/{client}/{template}/{version:int}/preview", ["POST"])
    async def profile_preview(request: Request) -> Response:
        markdown = str((await body_json(request)).get("markdown", ""))
        gespeichert = store.get(name_aus(request), request.path_params["version"])
        docx = await anyio.to_thread.run_sync(
            _render, markdown, gespeichert.profile, gespeichert.base_docx
        )
        return Response(docx, media_type=DOCX)

    # -- drafts (new profiles and new versions) ---------------------------------

    @route("/admin/api/drafts", ["POST"])
    async def upload(request: Request) -> Response:
        daten = await request.body()
        if not daten:
            raise ApiError(400, "empty upload")
        if len(daten) > MAX_UPLOAD:
            raise ApiError(413, "template larger than 30 MB")
        try:
            entwurf = drafts.create(daten, request.headers.get("x-filename", "template.docx"))
        except ValueError as e:
            raise ApiError(400, str(e)) from e
        kontext = ingest.kontext_aus_bytes(entwurf.original)
        vorschlag = ingest.heuristischer_vorschlag(kontext)
        return JSONResponse(
            {
                "draft_id": entwurf.id,
                "filename": entwurf.filename,
                "styles": _absatzstile(entwurf.base_docx),
                "blocks": te.bloecke(entwurf.base_docx),
                "mapping": {k: v for k, v in vorschlag.rollen.items() if v},
                "boundary": vorschlag.koerpergrenze,
                "source": "heuristic",
            }
        )

    @route("/admin/api/drafts/{draft_id}/propose", ["POST"])
    async def propose(request: Request) -> Response:
        art = (await body_json(request)).get("proposer", "heuristic")
        entwurf = drafts.get(request.path_params["draft_id"])
        kontext = ingest.kontext_aus_bytes(entwurf.original)
        if art == "llm":
            proposer = ingest.LLMProposer.from_env()
            if proposer is None:
                raise ApiError(400, "no model configured (TEMPLATE_ENGINE_LLM_*)")
            try:
                v = await anyio.to_thread.run_sync(proposer.vorschlag, kontext)
            except ingest.LLMFehler as e:
                raise ApiError(502, f"model call failed: {e}") from e
        else:
            v = ingest.heuristischer_vorschlag(kontext)
        return JSONResponse(
            {
                "mapping": {k: x for k, x in v.rollen.items() if x},
                "binding_sites": v.bindestellen,
                "boundary": v.koerpergrenze,
                "source": "llm" if art == "llm" else "heuristic",
            }
        )

    @route("/admin/api/drafts/{draft_id}/preview", ["POST"])
    async def draft_preview(request: Request) -> Response:
        d = await body_json(request)
        entwurf = drafts.get(request.path_params["draft_id"])
        profil = _profil_aus(d.get("mapping"), d.get("boundary"))
        markdown = str(d.get("markdown") or sample_markdown(profil))
        basis = _vorbereitet(profil, entwurf.base_docx)
        docx = await anyio.to_thread.run_sync(_render, markdown, profil, basis)
        return Response(docx, media_type=DOCX)

    @route("/admin/api/drafts/{draft_id}/sample", ["POST"])
    async def draft_sample(request: Request) -> Response:
        profil = _profil_aus((await body_json(request)).get("mapping"))
        return JSONResponse({"markdown": sample_markdown(profil)})

    @route("/admin/api/drafts/{draft_id}/publish", ["POST"])
    async def publish(request: Request) -> Response:
        d = await body_json(request)
        entwurf = drafts.get(request.path_params["draft_id"])
        profil = _profil_aus(d.get("mapping"), d.get("boundary"))
        try:
            vorbereitet = prepare(profil, entwurf.base_docx)
        except ProfileInvalid as e:
            raise ApiError(400, str(e)) from e
        try:
            info = store.publish(
                str(d.get("name", "")),
                profil,
                vorbereitet,
                source="admin-ui",
                original=entwurf.original,
                original_filename=entwurf.filename,
                status="approved" if d.get("approve") else "unapproved",
            )
        except ValueError as e:
            raise ApiError(400, str(e)) from e
        drafts.delete(entwurf.id)
        return JSONResponse({"info": info.to_dict()})
