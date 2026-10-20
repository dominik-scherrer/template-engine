"""The MCP service: profile store, validation, format guide and the tools.

Skipped when the optional ``server`` extra (the ``mcp`` package) is absent.
"""

from __future__ import annotations

import io
import os
import time
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("mcp")

from docx import Document  # noqa: E402
from mcp import Client  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

import template_engine as te  # noqa: E402
from template_engine_server.app import build_server  # noqa: E402
from template_engine_server.files import RenderedFiles, safe_filename  # noqa: E402
from template_engine_server.guide import format_guide  # noqa: E402
from template_engine_server.store import (  # noqa: E402
    DirectoryProfileStore,
    ProfileNotFound,
    ProfileUnavailable,
    validate_name,
)
from template_engine_server.validation import ProfileInvalid, check_profile  # noqa: E402
from tests.basis import alle_basen  # noqa: E402

BASIS = alle_basen()[0]
PROFIL = te.StyleProfile(dict(BASIS.rollen))

INHALT = """# Initial situation

The current system reaches the end of its support period.

## Objectives

- Replace the system
- Keep migration effort low

1. Analyse
2. Procure
"""


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def store(tmp_path: Path) -> DirectoryProfileStore:
    return DirectoryProfileStore(tmp_path / "profiles")


@pytest.fixture
def files(tmp_path: Path) -> RenderedFiles:
    return RenderedFiles(tmp_path / "rendered")


def _veroeffentliche(store: DirectoryProfileStore, name: str = "acme/report", **kw: Any) -> int:
    return store.publish(name, PROFIL, BASIS.docx, source="test", **kw).version


# -- store -------------------------------------------------------------------


def test_versions_count_up_and_latest_is_default(store: DirectoryProfileStore) -> None:
    assert _veroeffentliche(store) == 1
    assert _veroeffentliche(store) == 2
    assert store.get("acme/report").info.version == 2
    assert store.get("acme/report", 1).info.version == 1


def test_new_versions_are_unapproved_and_approval_is_per_version(
    store: DirectoryProfileStore,
) -> None:
    _veroeffentliche(store)
    assert store.get("acme/report").info.status == "unapproved"
    store.set_status("acme/report", 1, "approved")
    _veroeffentliche(store)
    assert store.get("acme/report", 1).info.status == "approved"
    assert store.get("acme/report").info.status == "unapproved"


def test_approval_does_not_touch_the_profile_itself(store: DirectoryProfileStore) -> None:
    _veroeffentliche(store)
    pfad = store.root / "acme" / "report" / "v1" / "profile.json"
    vorher = pfad.read_bytes()
    store.set_status("acme/report", 1, "approved")
    assert pfad.read_bytes() == vorher


def test_latest_skips_deactivated_and_pinning_a_deactivated_version_fails(
    store: DirectoryProfileStore,
) -> None:
    _veroeffentliche(store)
    _veroeffentliche(store)
    store.set_status("acme/report", 2, "deactivated")
    assert store.get("acme/report").info.version == 1
    with pytest.raises(ProfileUnavailable):
        store.get("acme/report", 2)
    store.set_status("acme/report", 1, "deactivated")
    with pytest.raises(ProfileUnavailable):
        store.get("acme/report")


def test_unknown_profile_and_version(store: DirectoryProfileStore) -> None:
    with pytest.raises(ProfileNotFound):
        store.get("acme/report")
    _veroeffentliche(store)
    with pytest.raises(ProfileNotFound):
        store.get("acme/report", 7)


@pytest.mark.parametrize("name", ["acme", "acme/report/x", "../etc", "Acme/Report", "a/b c", "/x"])
def test_names_are_validated(name: str) -> None:
    with pytest.raises(ValueError):
        validate_name(name)


def test_listing(store: DirectoryProfileStore) -> None:
    _veroeffentliche(store, "acme/report")
    _veroeffentliche(store, "acme/letter")
    _veroeffentliche(store, "zeta/report")
    assert [p.name for p in store.profiles()] == ["acme/letter", "acme/report", "zeta/report"]


# -- validation and guide ----------------------------------------------------


@pytest.mark.parametrize("basis", alle_basen(), ids=lambda b: b.name)
def test_every_synthetic_base_validates(basis: Any) -> None:
    check_profile(te.StyleProfile(dict(basis.rollen)), basis.docx)


def test_validation_rejects_a_style_the_base_lacks() -> None:
    kaputt = te.StyleProfile({**BASIS.rollen, "ueberschrift_1": "No Such Style"})
    with pytest.raises(ProfileInvalid, match="No Such Style"):
        check_profile(kaputt, BASIS.docx)


def test_validation_requires_body_text() -> None:
    ohne = {k: v for k, v in BASIS.rollen.items() if k != "fliesstext"}
    with pytest.raises(ProfileInvalid, match="fliesstext"):
        check_profile(te.StyleProfile(ohne), BASIS.docx)


def test_guide_lists_only_mapped_heading_levels() -> None:
    nur_eins = te.StyleProfile({"ueberschrift_1": "Titel 1", "fliesstext": "Fliesstext"})
    text = format_guide("acme/report", 1, nur_eins)
    assert "# (level 1)" in text
    assert "## (level 2)" not in text
    assert "No heading levels other than 1" in text
    assert "Bullet lists" not in text


def test_guide_example_renders_with_the_profile() -> None:
    text = format_guide("acme/report", 1, PROFIL)
    beispiel = text.split("```markdown\n", 1)[1].split("\n```", 1)[0]
    te.render(te.from_markdown(beispiel), PROFIL, BASIS.docx)


# -- rendered files ----------------------------------------------------------


@pytest.mark.parametrize(
    "token,name", [("short", "a.docx"), ("A" * 32, "../x.docx"), ("A" * 32, "x.exe")]
)
def test_files_reject_malformed_links(files: RenderedFiles, token: str, name: str) -> None:
    assert files.resolve(token, name) is None


def test_files_expire(tmp_path: Path) -> None:
    f = RenderedFiles(tmp_path / "r", ttl_seconds=60)
    gespeichert = f.put(b"x", "a")
    assert f.resolve(gespeichert.token, gespeichert.filename) is not None
    alt = time.time() - 120
    os.utime(gespeichert.path.parent, (alt, alt))
    assert f.resolve(gespeichert.token, gespeichert.filename) is None
    f.put(b"y", "b")  # triggers cleanup
    assert not gespeichert.path.parent.exists()


def test_safe_filename() -> None:
    assert safe_filename("../../Report: Q3?.pdf") == "Report-Q3.docx"
    assert safe_filename(None) == "document.docx"


# -- MCP tools ---------------------------------------------------------------


@pytest.mark.anyio
async def test_list_profiles_warns_about_unapproved(
    store: DirectoryProfileStore, files: RenderedFiles
) -> None:
    _veroeffentliche(store)
    async with Client(build_server(store, files)) as c:
        r = await c.call_tool("list_profiles", {})
    assert not r.is_error
    eintrag = r.structured_content["profiles"][0]
    assert eintrag["name"] == "acme/report" and eintrag["status"] == "unapproved"
    assert "not been approved" in eintrag["warning"]


@pytest.mark.anyio
async def test_render_returns_a_file_in_the_template_styles(
    store: DirectoryProfileStore, files: RenderedFiles
) -> None:
    _veroeffentliche(store)
    store.set_status("acme/report", 1, "approved")
    async with Client(build_server(store, files)) as c:
        r = await c.call_tool("render", {"profile": "acme/report", "markdown": INHALT})
    assert not r.is_error, r.content
    out = r.structured_content
    assert out["warnings"] == [] and out["version"] == 1
    doc = Document(io.BytesIO(Path(out["path"]).read_bytes()))
    stile = {p.style.name for p in doc.paragraphs}
    assert {BASIS.rollen["ueberschrift_1"], BASIS.rollen["aufzaehlung"]} <= stile


@pytest.mark.anyio
async def test_render_of_unapproved_profile_works_but_warns(
    store: DirectoryProfileStore, files: RenderedFiles
) -> None:
    _veroeffentliche(store)
    async with Client(build_server(store, files, public_url="https://te.example")) as c:
        r = await c.call_tool("render", {"profile": "acme/report", "markdown": INHALT})
    out = r.structured_content
    assert not r.is_error
    assert out["download_url"].startswith("https://te.example/files/")
    assert "not been approved" in out["warnings"][0]


@pytest.mark.anyio
async def test_unsupported_markdown_points_the_agent_to_the_guide(
    store: DirectoryProfileStore, files: RenderedFiles
) -> None:
    _veroeffentliche(store)
    async with Client(build_server(store, files)) as c:
        r = await c.call_tool(
            "render", {"profile": "acme/report", "markdown": "Some **bold** text.\n"}
        )
    assert r.is_error
    assert "format_guide" in r.content[0].text


@pytest.mark.anyio
async def test_unknown_profile_points_the_agent_to_the_list(
    store: DirectoryProfileStore, files: RenderedFiles
) -> None:
    async with Client(build_server(store, files)) as c:
        r = await c.call_tool("format_guide", {"profile": "acme/nothing"})
    assert r.is_error
    assert "list_profiles" in r.content[0].text


def test_download_route_serves_the_file_and_404s_otherwise(
    store: DirectoryProfileStore, files: RenderedFiles
) -> None:
    gespeichert = files.put(b"PK-fake", "report")
    app = build_server(store, files, public_url="http://t").streamable_http_app()
    with TestClient(app) as http:
        ok = http.get(f"/files/{gespeichert.token}/{gespeichert.filename}")
        assert ok.status_code == 200 and ok.content == b"PK-fake"
        assert http.get(f"/files/{'B' * 32}/report.docx").status_code == 404
        assert http.get("/health").json() == {"status": "ok"}
