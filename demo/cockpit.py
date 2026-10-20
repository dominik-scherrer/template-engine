"""A little local cockpit for the demo.

    python demo/cockpit.py            # or: uv run python demo/cockpit.py

Opens http://127.0.0.1:8000. Drop a Word template (.dotx / .docx): the engine
extracts its style inventory (keyed by styleId), a proposer suggests how to map
roles to the template's styles, and you render sample content into it and
download the .docx.

Two proposers: a zero-config heuristic (string matching), and an LLM proposer
you configure in the settings panel (an OpenAI-compatible base URL, model and
key). The LLM additionally proposes title-page binding sites and the body
boundary; those are shown but not yet applied at render (the zone model,
ADR-0008, is not built). Nothing is uploaded: the server runs on your machine,
and your key is sent only to the endpoint you configure.
"""

from __future__ import annotations

import base64
import io
import json
import sys
import webbrowser
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

import template_engine as te  # noqa: E402
from template_engine import ingest  # noqa: E402

BEISPIEL = ROOT / "demo" / "content.md"
BEISPIEL_INHALT = (
    BEISPIEL.read_text(encoding="utf-8")
    if BEISPIEL.exists()
    else "# Titel\n\nEin Absatz.\n\n- Punkt eins\n- Punkt zwei\n"
)


def _meta(daten: bytes) -> dict:
    z = zipfile.ZipFile(io.BytesIO(daten))
    namen = z.namelist()
    ist_vorlage = ingest.CT_TEMPLATE.encode() in z.read("[Content_Types].xml")
    sektionen = (
        z.read("word/document.xml").count(b"<w:sectPr") if "word/document.xml" in namen else 0
    )
    kopf = sum(1 for n in namen if n.startswith("word/header"))
    return {"istVorlage": ist_vorlage, "sektionen": sektionen, "kopfzeilen": kopf}


def _proposer(llm: dict | None) -> ingest.Proposer:
    if llm and llm.get("baseUrl") and llm.get("apiKey") and llm.get("model"):
        return ingest.LLMProposer(
            ingest.LLMKonfig(llm["baseUrl"].rstrip("/"), llm["apiKey"], llm["model"])
        )
    return ingest.HeuristischerProposer()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_a):
        pass

    def _json(self, obj, code=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path not in ("/", "/index.html"):
            self.send_error(404)
            return
        body = HTML.encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        laenge = int(self.headers.get("Content-Length", 0))
        roh = self.rfile.read(laenge)
        try:
            if self.path == "/ingest":
                inv = ingest.stil_inventar(roh)
                paragraph = sorted(
                    [
                        {"id": s["styleId"], "name": s["name"]}
                        for s in inv
                        if s["type"] == "paragraph"
                    ],
                    key=lambda x: x["name"].lower(),
                )
                auto = ingest.heuristischer_vorschlag(ingest.kontext_aus_bytes(roh)).rollen
                self._json({**_meta(roh), "stile": inv, "absatzStile": paragraph, "auto": auto})
            elif self.path == "/propose":
                anfrage = json.loads(roh)
                daten = base64.b64decode(anfrage["templateB64"])
                proposer = _proposer(anfrage.get("llm"))
                quelle = "llm" if isinstance(proposer, ingest.LLMProposer) else "heuristik"
                v = proposer.vorschlag(ingest.kontext_aus_bytes(daten))
                self._json(
                    {
                        "ok": True,
                        "quelle": quelle,
                        "rollen": v.rollen,
                        "bindestellen": v.bindestellen,
                        "koerpergrenze": v.koerpergrenze,
                    }
                )
            elif self.path == "/render":
                anfrage = json.loads(roh)
                vorlage = base64.b64decode(anfrage["templateB64"])
                dok = te.from_markdown(anfrage["markdown"])
                profil = te.StyleProfile({k: v for k, v in anfrage["rollen"].items() if v})
                docx = te.render(dok, profil, ingest.als_dokument_bytes(vorlage))
                self._json({"ok": True, "docxB64": base64.b64encode(docx).decode("ascii")})
            else:
                self.send_error(404)
        except Exception as e:
            self._json({"ok": False, "fehler": f"{type(e).__name__}: {e}"}, code=200)


HTML = r"""<!doctype html><html lang="de"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Template Engine — Cockpit</title>
<style>
:root{--bg:#0f1115;--card:#171a21;--line:#2a2f3a;--fg:#e6e9ef;--muted:#9aa4b2;--accent:#6ea8fe;--warn:#f0a860;--ok:#7bd88f}
@media(prefers-color-scheme:light){:root{--bg:#f5f6f8;--card:#fff;--line:#e2e5ea;--fg:#1b1f27;--muted:#5b6470;--accent:#2f6fed;--warn:#b56b12;--ok:#227a3b}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,Segoe UI,Roboto,sans-serif}
header{padding:16px 24px;border-bottom:1px solid var(--line);display:flex;justify-content:space-between;align-items:center}
h1{font-size:16px;margin:0}.sub{color:var(--muted);font-size:12px;margin-top:2px}
main{display:grid;grid-template-columns:1fr 1fr;gap:16px;padding:20px;max-width:1200px;margin:0 auto}
@media(max-width:860px){main{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px}
.card h2{font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:0 0 10px}
#drop{border:2px dashed var(--line);border-radius:12px;padding:30px;text-align:center;color:var(--muted);cursor:pointer;transition:.15s}
#drop.hot{border-color:var(--accent);color:var(--fg);background:rgba(110,168,254,.08)}
.pill{display:inline-block;padding:2px 8px;border:1px solid var(--line);border-radius:999px;font-size:12px;margin:2px 4px 2px 0}
table{width:100%;border-collapse:collapse;font-size:12px}th,td{text-align:left;padding:5px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{color:var(--muted);font-weight:600}code{font-family:ui-monospace,Consolas,monospace}
.flag{color:var(--warn)}.scroll{max-height:260px;overflow:auto;border:1px solid var(--line);border-radius:8px}
label{display:block;font-size:12px;color:var(--muted);margin:8px 0 3px}
select,textarea,input{width:100%;background:transparent;color:var(--fg);border:1px solid var(--line);border-radius:8px;padding:8px;font:inherit}
textarea{min-height:150px;font-family:ui-monospace,Consolas,monospace;font-size:12px}
button{background:var(--accent);color:#fff;border:0;border-radius:8px;padding:9px 14px;font-weight:600;cursor:pointer}
button.ghost{background:transparent;color:var(--fg);border:1px solid var(--line)}
button:disabled{opacity:.5;cursor:default}
.row{display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:10px}
.msg{margin-top:10px;font-size:12px}.msg.err{color:var(--warn)}.msg.ok{color:var(--ok)}
.hint{color:var(--muted);font-size:12px;margin-top:6px}
#settings{display:none;background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin:0 20px}
#settings.open{display:block}
.grid3{display:grid;grid-template-columns:2fr 1fr 2fr;gap:8px}@media(max-width:700px){.grid3{grid-template-columns:1fr}}
</style></head><body>
<header><div><h1>Template Engine — Cockpit</h1>
<div class="sub">Drop a Word template. It stays on your machine. Extract styles &rarr; propose a mapping &rarr; render into it.</div></div>
<button class="ghost" id="gear">LLM settings</button></header>
<section id="settings">
  <h2 style="font-size:13px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:0 0 8px">LLM proposer (OpenAI-compatible)</h2>
  <div class="grid3">
    <div><label>Base URL</label><input id="baseUrl" placeholder="https://api.openai.com/v1"></div>
    <div><label>Model</label><input id="model" placeholder="gpt-4o-mini"></div>
    <div><label>API key</label><input id="apiKey" type="password" placeholder="sk-..."></div>
  </div>
  <div class="row"><button id="saveCfg">Save</button><span class="hint" id="cfgState"></span></div>
  <div class="hint">Stored in your browser only, sent to the local server per request, which forwards it to the endpoint you name. Leave empty to use the heuristic proposer.</div>
</section>
<main>
  <section class="card">
    <h2>1 &middot; Drop a template</h2>
    <div id="drop">Drop a .dotx or .docx here, or click to choose</div>
    <input id="file" type="file" accept=".dotx,.docx" hidden>
    <div id="meta"></div><div id="inv"></div>
  </section>
  <section class="card">
    <h2>2 &middot; Propose &amp; render</h2>
    <div class="row"><button id="propose" disabled>Propose mapping</button><span class="hint" id="pquelle"></span></div>
    <div id="mapping"><div class="hint">Drop a template first.</div></div>
    <div id="extra"></div>
    <label>Content (Markdown)</label>
    <textarea id="content"></textarea>
    <div class="row"><button id="go" disabled>Render &rarr; download .docx</button><span id="rmsg" class="msg"></span></div>
    <div class="hint">The role mapping is applied at render; the header/footer/letterhead are kept. Binding sites and the body boundary are proposed but not yet applied (zones pending).</div>
  </section>
</main>
<script>
const $=s=>document.querySelector(s);
function toB64(buf){const b=new Uint8Array(buf);let s="";const C=0x8000;for(let i=0;i<b.length;i+=C){s+=String.fromCharCode.apply(null,b.subarray(i,i+C));}return btoa(s);}
let templateB64=null, absatzStile=[], auto={};
const ROLLEN=["ueberschrift_1","ueberschrift_2","fliesstext","aufzaehlung","nummerierte_liste"];
$("#content").value=%%CONTENT%%;

function loadCfg(){try{return JSON.parse(localStorage.getItem("te_llm")||"{}")}catch(e){return {}}}
function cfgState(){const c=loadCfg();$("#cfgState").textContent=(c.baseUrl&&c.model&&c.apiKey)?"configured - LLM proposer active":"empty - heuristic proposer";}
$("#gear").onclick=()=>{const c=loadCfg();$("#baseUrl").value=c.baseUrl||"";$("#model").value=c.model||"";$("#apiKey").value=c.apiKey||"";$("#settings").classList.toggle("open");};
$("#saveCfg").onclick=()=>{localStorage.setItem("te_llm",JSON.stringify({baseUrl:$("#baseUrl").value.trim(),model:$("#model").value.trim(),apiKey:$("#apiKey").value.trim()}));cfgState();$("#settings").classList.remove("open");};
cfgState();

const drop=$("#drop"), fileInput=$("#file");
drop.onclick=()=>fileInput.click();
["dragenter","dragover"].forEach(e=>drop.addEventListener(e,ev=>{ev.preventDefault();drop.classList.add("hot")}));
["dragleave","drop"].forEach(e=>drop.addEventListener(e,ev=>{ev.preventDefault();drop.classList.remove("hot")}));
drop.addEventListener("drop",ev=>handle(ev.dataTransfer.files[0]));
fileInput.addEventListener("change",ev=>handle(ev.target.files[0]));

async function handle(file){
  if(!file)return; drop.textContent="Reading "+file.name+" ...";
  const buf=await file.arrayBuffer(); templateB64=toB64(buf);
  const inv=await (await fetch("/ingest",{method:"POST",body:buf})).json();
  drop.textContent=file.name+" - drop another to replace";
  absatzStile=inv.absatzStile; auto=inv.auto;
  renderMeta(file.name,inv); renderInventory(inv); renderMapping(auto); $("#extra").innerHTML="";
  $("#propose").disabled=false; $("#go").disabled=false; $("#pquelle").textContent="heuristic guess shown - Propose to refine";
}
function renderMeta(name,inv){
  const cust=inv.stile.filter(s=>s.custom).length;
  $("#meta").innerHTML='<div style="margin:12px 0">'+
    '<span class="pill">'+(inv.istVorlage?".dotx template":".docx")+'</span>'+
    '<span class="pill">'+inv.sektionen+' section(s)</span>'+
    '<span class="pill">'+inv.kopfzeilen+' header part(s)'+(inv.kopfzeilen>=2?" &middot; first-page-different":"")+'</span>'+
    '<span class="pill">'+inv.stile.length+' styles &middot; '+cust+' custom</span></div>';
}
function renderInventory(inv){
  const rows=inv.stile.filter(s=>s.custom).map(s=>{
    const neq=s.styleId!==s.name.replace(/ /g,"");
    return '<tr><td><code>'+s.styleId+'</code></td><td>'+s.name+(neq?' <span class="flag">*</span>':'')+'</td><td>'+s.type+'</td></tr>';}).join("");
  $("#inv").innerHTML='<div class="scroll"><table><thead><tr><th>styleId</th><th>display name</th><th>type</th></tr></thead>'+
    '<tbody>'+(rows||'<tr><td colspan=3>No custom styles.</td></tr>')+'</tbody></table></div>'+
    '<div class="hint"><span class="flag">*</span> styleId differs from the display name - why the mapping keys on styleId.</div>';
}
function renderMapping(sel){
  const opts=v=>['<option value="">- none -</option>'].concat(
    absatzStile.map(s=>'<option value="'+s.id+'" '+(s.id===v?"selected":"")+'>'+s.name+' &middot; '+s.id+'</option>')).join("");
  $("#mapping").innerHTML=ROLLEN.map(r=>'<label>'+r+'</label><select data-role="'+r+'">'+opts((sel||{})[r]||"")+'</select>').join("");
}
$("#propose").onclick=async()=>{
  $("#propose").disabled=true;$("#pquelle").textContent="proposing ...";
  const out=await (await fetch("/propose",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({templateB64,llm:loadCfg()})})).json();
  $("#propose").disabled=false;
  if(!out.ok){$("#pquelle").innerHTML='<span class="flag">x '+out.fehler+'</span>';return;}
  renderMapping(out.rollen); $("#pquelle").textContent="source: "+out.quelle;
  const bs=(out.bindestellen||[]).map(b=>'<tr><td>&para;'+b.absatz+'</td><td><code>'+(b.feld||"")+'</code></td><td>'+((b.text||"").slice(0,50))+'</td></tr>').join("");
  $("#extra").innerHTML = (bs||out.koerpergrenze!=null) ? '<div class="hint" style="margin-top:12px">Proposed (not applied at render yet):</div>'+
    '<div class="scroll"><table><thead><tr><th>&para;</th><th>field</th><th>text</th></tr></thead><tbody>'+(bs||'<tr><td colspan=3>no binding sites</td></tr>')+'</tbody></table></div>'+
    '<div class="hint">body boundary: '+(out.koerpergrenze==null?"-":"after &para;"+out.koerpergrenze)+'</div>' : "";
};
$("#go").onclick=async()=>{
  const rollen={};document.querySelectorAll("#mapping select").forEach(s=>rollen[s.dataset.role]=s.value);
  $("#go").disabled=true;$("#rmsg").className="msg";$("#rmsg").textContent="Rendering ...";
  const out=await (await fetch("/render",{method:"POST",headers:{"Content-Type":"application/json"},
    body:JSON.stringify({markdown:$("#content").value,rollen,templateB64})})).json();
  $("#go").disabled=false;
  if(!out.ok){$("#rmsg").className="msg err";$("#rmsg").textContent="x "+out.fehler;return;}
  const bin=Uint8Array.from(atob(out.docxB64),c=>c.charCodeAt(0));
  const url=URL.createObjectURL(new Blob([bin],{type:"application/vnd.openxmlformats-officedocument.wordprocessingml.document"}));
  const a=document.createElement("a");a.href=url;a.download="gerendert.docx";a.click();URL.revokeObjectURL(url);
  $("#rmsg").className="msg ok";$("#rmsg").textContent="Rendered - check your downloads.";
};
</script></body></html>"""

HTML = HTML.replace("%%CONTENT%%", json.dumps(BEISPIEL_INHALT))


def main() -> None:
    port = 8000
    srv = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://127.0.0.1:{port}"
    print(f"Cockpit running at {url}  (Ctrl+C to stop)")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")


if __name__ == "__main__":
    main()
