"""Command line for running the server and administering profiles.

    template-engine-server serve [--transport stdio|http] [--host H] [--port P] [--public-url U]
    template-engine-server import NAME TEMPLATE [--mapping FILE | --propose heuristic|llm]
                                  [--boundary N] [--approve]
    template-engine-server list
    template-engine-server approve NAME VERSION
    template-engine-server deactivate NAME VERSION

The store location comes from ``--data`` or ``TEMPLATE_ENGINE_DATA`` (default
``./data``): profiles live in ``<data>/profiles``, rendered files in
``<data>/rendered``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import template_engine as te
from template_engine import ingest
from template_engine_server.drafts import DraftStore
from template_engine_server.files import RenderedFiles
from template_engine_server.store import DirectoryProfileStore
from template_engine_server.validation import ProfileInvalid, prepare


def _store(data: Path) -> DirectoryProfileStore:
    return DirectoryProfileStore(data / "profiles")


def _cmd_serve(a: argparse.Namespace) -> int:
    from template_engine_server.app import build_server

    files = RenderedFiles(a.data / "rendered", ttl_seconds=a.ttl_hours * 3600)
    if a.transport == "stdio":
        build_server(_store(a.data), files, public_url=None).run("stdio")
        return 0
    public = a.public_url or f"http://{a.host}:{a.port}"
    token = a.admin_token or os.environ.get("TEMPLATE_ENGINE_ADMIN_TOKEN") or None
    server = build_server(
        _store(a.data),
        files,
        public_url=public,
        drafts=DraftStore(a.data / "drafts"),
        admin_token=token,
    )
    print(f"MCP endpoint: {public}/mcp", file=sys.stderr)
    zugang = "token required" if token else "localhost only"
    print(f"Admin:        {public}/admin   ({zugang})", file=sys.stderr)
    server.run("streamable-http", host=a.host, port=a.port)
    return 0


def _cmd_import(a: argparse.Namespace) -> int:
    roh = Path(a.template).read_bytes()
    basis = ingest.als_dokument_bytes(roh)
    grenze: int | None = None
    if a.mapping:
        geladen = json.loads(Path(a.mapping).read_text(encoding="utf-8"))
        rollen = geladen.get("rollen", geladen)
        grenze = geladen.get("koerpergrenze") if "rollen" in geladen else None
    else:
        kontext = ingest.kontext_aus_bytes(roh)
        if a.propose == "llm":
            proposer = ingest.LLMProposer.from_env()
            if proposer is None:
                print("error: set TEMPLATE_ENGINE_LLM_* to use --propose llm", file=sys.stderr)
                return 2
            vorschlag = proposer.vorschlag(kontext)
        else:
            vorschlag = ingest.heuristischer_vorschlag(kontext)
        rollen, grenze = vorschlag.rollen, vorschlag.koerpergrenze
    if a.boundary is not None:
        grenze = a.boundary
    profil = te.StyleProfile({k: v for k, v in rollen.items() if v}, koerpergrenze=grenze)
    try:
        basis = prepare(profil, basis)
    except ProfileInvalid as e:
        zuordnung = json.dumps(profil.rollen, ensure_ascii=False)
        print(f"error: {e}\nmapping was: {zuordnung}", file=sys.stderr)
        return 1
    info = _store(a.data).publish(
        a.name,
        profil,
        basis,
        source="admin-cli",
        original=roh,
        original_filename=Path(a.template).name,
        status="approved" if a.approve else "unapproved",
    )
    print(f"stored {info.name} v{info.version} ({info.status})")
    print(profil.to_json())
    _zeige_grenze(basis)
    return 0


def _zeige_grenze(basis: bytes) -> None:
    folge = te.bloecke(basis)
    grenze = next((b["index"] for b in folge if b["bookmark"]), None)
    if grenze is None:
        print("body boundary: none, the whole body is generated")
        return
    print(f"body boundary: block {grenze} of {len(folge)}; kept before it:")
    for b in folge[:grenze]:
        print(f"  {b['index']:3} {b['kind']:9} {b['styleId'][:20]:20} {b['text'][:50]!r}")
    if grenze < len(folge):
        b = folge[grenze]
        print(f"  generated from: {b['styleId']} {b['text'][:50]!r}")


def _cmd_list(a: argparse.Namespace) -> int:
    profile = _store(a.data).profiles()
    if not profile:
        print("no profiles")
    for p in profile:
        for v in p.versions:
            neu = "  <- latest" if p.latest and p.latest.version == v.version else ""
            print(f"{p.name:40} v{v.version:<4} {v.status:12} {v.created_at}{neu}")
    return 0


def _cmd_status(a: argparse.Namespace, status: str) -> int:
    info = _store(a.data).set_status(a.name, a.version, status)  # type: ignore[arg-type]
    print(f"{info.name} v{info.version}: {info.status}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="template-engine-server")
    p.add_argument(
        "--data",
        type=Path,
        default=Path(os.environ.get("TEMPLATE_ENGINE_DATA", "data")),
        help="data directory (default: $TEMPLATE_ENGINE_DATA or ./data)",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("serve", help="run the MCP server")
    s.add_argument("--transport", choices=["stdio", "http"], default="http")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8765)
    s.add_argument("--public-url", help="externally reachable base URL, for download links")
    s.add_argument("--ttl-hours", type=int, default=24, help="how long download links live")
    s.add_argument(
        "--admin-token",
        help="require this token for the admin API (or TEMPLATE_ENGINE_ADMIN_TOKEN); "
        "without one, the admin interface only answers on localhost",
    )

    i = sub.add_parser("import", help="store a template as a new profile version")
    i.add_argument("name", help="<client>/<template>")
    i.add_argument("template", help=".docx or .dotx")
    g = i.add_mutually_exclusive_group()
    g.add_argument("--mapping", help="JSON file: role -> style name or styleId")
    g.add_argument("--propose", choices=["heuristic", "llm"], default="heuristic")
    i.add_argument(
        "--boundary",
        type=int,
        help="index of the first generated block (0 = whole body); default: proposed",
    )
    i.add_argument("--approve", action="store_true", help="store as approved")

    sub.add_parser("list", help="list profiles and versions")
    for cmd in ("approve", "deactivate"):
        c = sub.add_parser(cmd, help=f"{cmd} a profile version")
        c.add_argument("name")
        c.add_argument("version", type=int)

    a = p.parse_args(argv)
    if a.cmd == "serve":
        return _cmd_serve(a)
    if a.cmd == "import":
        return _cmd_import(a)
    if a.cmd == "list":
        return _cmd_list(a)
    return _cmd_status(a, "approved" if a.cmd == "approve" else "deactivated")


if __name__ == "__main__":
    raise SystemExit(main())
