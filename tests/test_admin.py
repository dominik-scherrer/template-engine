"""The admin API behind /admin. Skipped without the ``server`` extra."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

pytest.importorskip("mcp")

from docx import Document  # noqa: E402
from starlette.testclient import TestClient  # noqa: E402

from template_engine_server.app import build_server  # noqa: E402
from template_engine_server.drafts import DraftStore  # noqa: E402
from template_engine_server.files import RenderedFiles  # noqa: E402
from template_engine_server.store import DirectoryProfileStore  # noqa: E402
from tests.basis import alle_basen  # noqa: E402

BASIS = alle_basen()[0]
TOKEN = "s3cret-token"
H = {"X-Admin-Token": TOKEN}


@pytest.fixture
def setup(tmp_path: Path) -> tuple[TestClient, DirectoryProfileStore]:
    store = DirectoryProfileStore(tmp_path / "profiles")
    server = build_server(
        store,
        RenderedFiles(tmp_path / "rendered"),
        public_url="http://t",
        drafts=DraftStore(tmp_path / "drafts"),
        admin_token=TOKEN,
    )
    return TestClient(server.streamable_http_app()), store


def test_api_requires_the_token(setup: tuple[TestClient, DirectoryProfileStore]) -> None:
    http, _ = setup
    assert http.get("/admin/api/profiles").status_code == 401
    assert http.get("/admin/api/profiles", headers={"X-Admin-Token": "wrong"}).status_code == 401
    assert http.get("/admin/api/profiles", headers=H).json() == {"profiles": []}


def test_page_and_vendored_scripts_are_served(
    setup: tuple[TestClient, DirectoryProfileStore],
) -> None:
    http, _ = setup
    assert "Template Engine" in http.get("/admin").text
    js = http.get("/admin/vendor/docx-preview.min.js")
    assert js.status_code == 200 and "renderAsync" in js.text
    assert http.get("/admin/vendor/../app.py").status_code == 404


def test_without_a_token_only_loopback_clients_are_served(tmp_path: Path) -> None:
    server = build_server(
        DirectoryProfileStore(tmp_path / "p"),
        RenderedFiles(tmp_path / "r"),
        drafts=DraftStore(tmp_path / "d"),
    )
    remote = TestClient(server.streamable_http_app(), client=("203.0.113.7", 5000))
    assert remote.get("/admin").status_code == 403
    assert remote.get("/admin/api/profiles").status_code == 401
    lokal = TestClient(server.streamable_http_app(), client=("127.0.0.1", 5000))
    assert lokal.get("/admin/api/profiles").status_code == 200


def test_upload_preview_publish_approve(setup: tuple[TestClient, DirectoryProfileStore]) -> None:
    http, store = setup
    d = http.post(
        "/admin/api/drafts", content=BASIS.docx, headers={**H, "X-Filename": "client.dotx"}
    ).json()
    assert d["filename"] == "client.dotx"
    assert {s["name"] for s in d["styles"]} >= set(BASIS.rollen.values())

    mapping = dict(BASIS.rollen)
    sample = http.post(
        f"/admin/api/drafts/{d['draft_id']}/sample", json={"mapping": mapping}, headers=H
    ).json()["markdown"]
    pv = http.post(
        f"/admin/api/drafts/{d['draft_id']}/preview",
        json={"mapping": mapping, "markdown": sample},
        headers=H,
    )
    assert pv.status_code == 200
    stile = {p.style.name for p in Document(io.BytesIO(pv.content)).paragraphs}
    assert set(mapping.values()) <= stile

    pub = http.post(
        f"/admin/api/drafts/{d['draft_id']}/publish",
        json={"name": "acme/report", "mapping": mapping, "approve": False},
        headers=H,
    ).json()
    assert pub["info"]["version"] == 1 and pub["info"]["status"] == "unapproved"
    assert store.get("acme/report").info.source == "admin-ui"
    # the draft is consumed
    again = http.post(
        f"/admin/api/drafts/{d['draft_id']}/publish",
        json={"name": "acme/report", "mapping": mapping},
        headers=H,
    )
    assert again.status_code == 404

    r = http.post(
        "/admin/api/profiles/acme/report/1/status", json={"status": "approved"}, headers=H
    )
    assert r.json()["info"]["status"] == "approved"
    detail = http.get("/admin/api/profiles/acme/report/1", headers=H).json()
    assert detail["mapping"] == mapping and "Format guide" in detail["guide"]
    assert (
        http.post(
            "/admin/api/profiles/acme/report/1/preview", json={"markdown": sample}, headers=H
        ).status_code
        == 200
    )


def test_errors_are_reported_not_raised(setup: tuple[TestClient, DirectoryProfileStore]) -> None:
    http, _ = setup
    assert http.post("/admin/api/drafts", content=b"not a zip", headers=H).status_code == 400
    d = http.post("/admin/api/drafts", content=BASIS.docx, headers=H).json()
    kaputt = {**BASIS.rollen, "ueberschrift_1": "No Such Style"}
    r = http.post(
        f"/admin/api/drafts/{d['draft_id']}/publish",
        json={"name": "acme/report", "mapping": kaputt},
        headers=H,
    )
    assert r.status_code == 400 and "No Such Style" in r.json()["error"]
    r = http.post(
        f"/admin/api/drafts/{d['draft_id']}/publish",
        json={"name": "Not Valid", "mapping": dict(BASIS.rollen)},
        headers=H,
    )
    assert r.status_code == 400
    r = http.post(
        f"/admin/api/drafts/{d['draft_id']}/preview",
        json={"mapping": dict(BASIS.rollen), "markdown": "| a |\n|---|\n| 1 |\n"},
        headers=H,
    )
    assert r.status_code == 400 and "Table" in r.json()["error"]
    assert http.get("/admin/api/profiles/acme/none/1", headers=H).status_code == 404


def test_boundary_is_proposed_previewed_and_stored(
    setup: tuple[TestClient, DirectoryProfileStore],
) -> None:
    import template_engine as te
    from tests.test_zonen import vorlage

    http, store = setup
    d = http.post("/admin/api/drafts", content=vorlage(), headers=H).json()
    assert d["boundary"] == 5
    assert d["blocks"][3]["toc"] and d["blocks"][5]["text"] == "Old chapter"

    mapping = {k: v for k, v in d["mapping"].items() if v}
    pv = http.post(
        f"/admin/api/drafts/{d['draft_id']}/preview",
        json={"mapping": mapping, "boundary": 5, "markdown": "# New\n\nText.\n"},
        headers=H,
    )
    assert pv.status_code == 200
    assert [b["text"] for b in te.bloecke(pv.content)][5:] == ["New", "Text."]
    assert te.bloecke(pv.content)[0]["text"] == "Project report"

    zu_weit = http.post(
        f"/admin/api/drafts/{d['draft_id']}/publish",
        json={"name": "acme/report", "mapping": mapping, "boundary": 99},
        headers=H,
    )
    assert zu_weit.status_code == 400

    http.post(
        f"/admin/api/drafts/{d['draft_id']}/publish",
        json={"name": "acme/report", "mapping": mapping, "boundary": 5},
        headers=H,
    )
    gespeichert = store.get("acme/report")
    assert gespeichert.profile.koerpergrenze == 5
    assert [b["bookmark"] for b in te.bloecke(gespeichert.base_docx)].index(True) == 5
    detail = http.get("/admin/api/profiles/acme/report/1", headers=H).json()
    assert detail["boundary"] == 5 and len(detail["blocks"]) == len(d["blocks"])
