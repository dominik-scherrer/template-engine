"""Ingest: read a template and propose how to map it.

This is the extract-and-propose half of the ingest step (ADR-0009). It does the
deterministic reading, opening a ``.dotx`` despite its template content type,
pulling the style inventory keyed by ``styleId`` and the paragraph sequence, and
it defines the *proposer* seam: the deterministic part hands a proposer a
:class:`VorlageKontext` and gets back a :class:`Vorschlag`.

Per ADR-0013 the library never calls a model on its own initiative. It offers a
:class:`HeuristischerProposer` (no network) and an :class:`LLMProposer` that the
caller configures, via explicit :class:`LLMKonfig` or from the environment. The
render path stays deterministic; only a proposer may use a model, and only to
suggest, for a human to confirm.
"""

from __future__ import annotations

import io
import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import dataclass, field
from typing import Any, Protocol

from template_engine import zonen

__all__ = [
    "ROLLEN",
    "als_dokument_bytes",
    "stil_inventar",
    "absatzfolge",
    "kontext_aus_bytes",
    "Vorschlag",
    "VorlageKontext",
    "Proposer",
    "HeuristischerProposer",
    "LLMKonfig",
    "LLMProposer",
    "LLMFehler",
    "heuristischer_vorschlag",
]

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
CT_TEMPLATE = "application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml"
CT_DOCUMENT = "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"

# The fixed role vocabulary the block catalogue targets, with a human hint used
# both by the heuristic and in the LLM prompt.
ROLLEN: dict[str, str] = {
    "ueberschrift_1": "top-level heading / section title",
    "ueberschrift_2": "second-level heading / subheading",
    "fliesstext": "body text / running paragraph",
    "aufzaehlung": "bullet list item",
    "nummerierte_liste": "numbered list item",
}


# -- deterministic reading ---------------------------------------------------


def als_dokument_bytes(daten: bytes) -> bytes:
    """Return docx bytes a document reader can open: swap the template content type."""
    zin = zipfile.ZipFile(io.BytesIO(daten))
    ct = zin.read("[Content_Types].xml").decode("utf-8")
    if CT_TEMPLATE in ct:
        ct = ct.replace(CT_TEMPLATE, CT_DOCUMENT)
    out = io.BytesIO()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            data = (
                ct.encode("utf-8")
                if item.filename == "[Content_Types].xml"
                else zin.read(item.filename)
            )
            zout.writestr(item, data)
    return out.getvalue()


def stil_inventar(daten: bytes) -> list[dict[str, Any]]:
    """Style inventory from styles.xml: styleId, display name, type, custom flag."""
    z = zipfile.ZipFile(io.BytesIO(daten))
    if "word/styles.xml" not in z.namelist():
        return []
    root = ET.fromstring(z.read("word/styles.xml"))
    stile: list[dict[str, Any]] = []
    for s in root.findall(f"{_W}style"):
        sid = s.get(f"{_W}styleId") or ""
        nm_el = s.find(f"{_W}name")
        nm = nm_el.get(f"{_W}val") if nm_el is not None else sid
        stile.append(
            {
                "styleId": sid,
                "name": nm,
                "type": s.get(f"{_W}type") or "",
                "custom": s.get(f"{_W}customStyle") == "1",
            }
        )
    return stile


def absatzfolge(daten: bytes, limit: int = 60) -> list[dict[str, Any]]:
    """The first ``limit`` body paragraphs as {index, styleId, text}.

    Enough for a proposer to spot title-page slots and the body boundary without
    being handed the whole document.
    """
    z = zipfile.ZipFile(io.BytesIO(daten))
    if "word/document.xml" not in z.namelist():
        return []
    root = ET.fromstring(z.read("word/document.xml"))
    body = root.find(f"{_W}body")
    if body is None:
        return []
    folge: list[dict[str, Any]] = []
    for i, p in enumerate(body.findall(f"{_W}p")):
        if i >= limit:
            break
        ppr = p.find(f"{_W}pPr")
        sid = ""
        if ppr is not None:
            ps = ppr.find(f"{_W}pStyle")
            if ps is not None:
                sid = ps.get(f"{_W}val") or ""
        text = "".join(t.text or "" for t in p.iter(f"{_W}t"))
        folge.append({"index": i, "styleId": sid, "text": text})
    return folge


@dataclass(frozen=True)
class VorlageKontext:
    """What a proposer is given: the style inventory and the first top-level
    blocks of the body (paragraphs, tables, content controls; see
    :func:`template_engine.zonen.bloecke`). Block indices are what
    ``koerpergrenze`` and binding sites refer to."""

    inventar: list[dict[str, Any]]
    bloecke: list[dict[str, Any]]


def kontext_aus_bytes(daten: bytes, limit: int = 80) -> VorlageKontext:
    return VorlageKontext(inventar=stil_inventar(daten), bloecke=zonen.bloecke(daten)[:limit])


# -- proposals ---------------------------------------------------------------


@dataclass(frozen=True)
class Vorschlag:
    """A proposer's suggestions, for a human to confirm before anything is saved.

    ``rollen`` maps a role to a styleId. ``koerpergrenze`` is the index of the
    first generated top-level block: the retained front (ADR-0008) is everything
    before it. ``bindestellen`` are title-page slots ({block, feld, text}); they
    are proposed but not yet applied by the renderer.
    """

    rollen: dict[str, str] = field(default_factory=dict)
    bindestellen: list[dict[str, Any]] = field(default_factory=list)
    koerpergrenze: int | None = None


class Proposer(Protocol):
    def vorschlag(self, kontext: VorlageKontext) -> Vorschlag: ...


def heuristischer_vorschlag(kontext: VorlageKontext) -> Vorschlag:
    """Role mapping by string matching; no binding sites or boundary. No network."""
    paragraph_styles = [s for s in kontext.inventar if s["type"] == "paragraph"]

    def finde(*schluessel: str) -> str:
        # Prefer body styles: a "Table Bullet" style also matches "bullet", but
        # belongs inside table cells. Table-cell styles are a fallback only.
        def tabellarisch(ps: dict[str, Any]) -> bool:
            n = f"{ps['name']} {ps['styleId']}".lower()
            return "tabelle" in n or "table" in n

        for erlaube_tabelle in (False, True):
            for k in schluessel:
                for ps in paragraph_styles:
                    if tabellarisch(ps) and not erlaube_tabelle:
                        continue
                    if k in ps["name"].lower() or k in ps["styleId"].lower():
                        return str(ps["styleId"])
        return ""

    rollen = {
        "ueberschrift_1": finde(
            "überschrift 1", "uberschrift 1", "heading 1", "titel 1", "titelseite kunde"
        ),
        "ueberschrift_2": finde(
            "überschrift 2", "uberschrift 2", "heading 2", "titel 2", "zwischentitel"
        ),
        "fliesstext": finde("fliesstext (einzug)", "fliesstext", "standard", "body text", "normal"),
        "aufzaehlung": finde("aufzähl", "aufzaehl", "list bullet", "bullet", "liste"),
        "nummerierte_liste": finde("nummer", "list number", "number", "aufzähl", "liste"),
    }
    grenze = zonen.vorschlag_koerpergrenze(kontext.bloecke, rollen["ueberschrift_1"])
    return Vorschlag(rollen=rollen, koerpergrenze=grenze)


class HeuristischerProposer:
    """The zero-config default proposer."""

    def vorschlag(self, kontext: VorlageKontext) -> Vorschlag:
        return heuristischer_vorschlag(kontext)


# -- LLM proposer (OpenAI-compatible) ----------------------------------------


class LLMFehler(RuntimeError):
    """The LLM proposer could not produce a usable proposal."""


@dataclass(frozen=True)
class LLMKonfig:
    """Config for an OpenAI-compatible chat-completions endpoint."""

    base_url: str
    api_key: str
    model: str

    @classmethod
    def from_env(cls) -> LLMKonfig | None:
        base = os.environ.get("TEMPLATE_ENGINE_LLM_BASE_URL")
        key = os.environ.get("TEMPLATE_ENGINE_LLM_API_KEY")
        model = os.environ.get("TEMPLATE_ENGINE_LLM_MODEL")
        if base and key and model:
            return cls(base_url=base.rstrip("/"), api_key=key, model=model)
        return None


def _chat(konfig: LLMKonfig, messages: list[dict[str, str]], timeout: float = 60.0) -> str:
    """POST to an OpenAI-compatible /chat/completions and return the message text.

    Isolated so tests can substitute it without a network call.
    """
    payload = {
        "model": konfig.model,
        "messages": messages,
        "temperature": 0,
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        konfig.base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {konfig.api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        antwort = json.loads(resp.read().decode("utf-8"))
    return str(antwort["choices"][0]["message"]["content"])


def _extrahiere_json(text: str) -> dict[str, Any]:
    try:
        return dict(json.loads(text))
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if not m:
            raise LLMFehler("the model did not return JSON") from None
        return dict(json.loads(m.group(0)))


def _prompt(kontext: VorlageKontext) -> list[dict[str, str]]:
    rollen_zeilen = "\n".join(f"  - {r}: {d}" for r, d in ROLLEN.items())
    stile = [
        {"styleId": s["styleId"], "name": s["name"], "type": s["type"], "custom": s["custom"]}
        for s in kontext.inventar
        if s["type"] in ("paragraph", "table")
    ]
    system = (
        "You analyse a Microsoft Word template and return ONLY JSON. You map the "
        "template's paragraph styles to a fixed role vocabulary (by styleId), "
        "identify title-page fields that should become fill-in slots, and find "
        "the block index where the front matter (cover page, imprint, version "
        "table, table of contents) ends and the document body begins. Blocks are "
        "the body's top-level paragraphs, tables and content controls, in order.\n"
        "Return an object with exactly these keys:\n"
        '  "rollen": object mapping each role to a styleId from the inventory '
        "(or empty string if none fits),\n"
        '  "bindestellen": array of {"block": int, "feld": string, "text": string} '
        "for title-page slots (e.g. client name, date, version),\n"
        '  "koerpergrenze": index of the first block of the body (typically the first '
        "chapter heading after the table of contents), or 0 if there is no front matter."
    )
    user = (
        f"Roles:\n{rollen_zeilen}\n\n"
        f"Style inventory (JSON):\n{json.dumps(stile, ensure_ascii=False)}\n\n"
        f"First blocks (JSON: index, kind, styleId, flags, text):\n"
        f"{json.dumps(kontext.bloecke, ensure_ascii=False)}"
    )
    return [{"role": "system", "content": system}, {"role": "user", "content": user}]


class LLMProposer:
    """Proposer backed by an OpenAI-compatible endpoint. Configured by the caller."""

    def __init__(self, konfig: LLMKonfig) -> None:
        self.konfig = konfig

    @classmethod
    def from_env(cls) -> LLMProposer | None:
        konfig = LLMKonfig.from_env()
        return cls(konfig) if konfig else None

    def vorschlag(self, kontext: VorlageKontext) -> Vorschlag:
        try:
            text = _chat(self.konfig, _prompt(kontext))
        except LLMFehler:
            raise
        except Exception as e:  # network, auth, shape
            raise LLMFehler(f"{type(e).__name__}: {e}") from e
        daten = _extrahiere_json(text)
        rollen_roh = daten.get("rollen", {})
        rollen = (
            {str(k): str(v) for k, v in dict(rollen_roh).items()}
            if isinstance(rollen_roh, dict)
            else {}
        )
        binde_roh = daten.get("bindestellen", [])
        bindestellen = [dict(b) for b in binde_roh] if isinstance(binde_roh, list) else []
        grenze = daten.get("koerpergrenze")
        koerpergrenze = int(grenze) if isinstance(grenze, int) else None
        return Vorschlag(rollen=rollen, bindestellen=bindestellen, koerpergrenze=koerpergrenze)
