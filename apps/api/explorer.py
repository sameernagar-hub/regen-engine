"""What is going on inside the API and the ledger, at http://127.0.0.1:8787/ (and /db).

  GET /                       the API's own page: live request tracker + the database browser, one HTML file
  GET /db                     the same page opened on the database browser
  GET /api/track              per-route hits, errors, mean and last latency, last seen (in memory since start)
  GET /api/db/tables          the ledger's relations (allowlist) with row counts
  GET /api/db/rows/{name}     rows, newest first: ?q= (text anywhere in the row), ?col=&val= (one column contains),
                              ?after_id= (only newer: the page's live refresh), ?limit= (<= 1000), ?format=csv|json
                              (download)

Read-only by construction: the relation name must be in RELATIONS, column names must belong to that relation, and
every value goes in as a bound parameter. Postgres itself (127.0.0.1:5433) speaks its own protocol, not HTTP, so its
browser lives here. Without Postgres (local jsonl mode) the browser reads `events` from the event log.
"""
import csv, io, json, time

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response

from apps.api import store

router = APIRouter()
RELATIONS = ("events", "applications", "answers", "codes", "outcomes", "resumes", "discoveries", "supervisor_audit",
             "fleet_heartbeats")
TRACK = {}  # route -> {"hits", "errors", "ms_total", "ms_last", "last"}


async def track(request: Request, call_next):
    """Middleware: count every request by route (the page's tracker). O(1) per request."""
    t0 = time.perf_counter()
    status = 500
    try:
        resp = await call_next(request)
        status = resp.status_code
        return resp
    finally:
        route = request.scope.get("route")
        key = f"{request.method} {getattr(route, 'path', request.url.path)}"
        if not key.endswith(("/api/track", "/favicon.ico")):
            ms = (time.perf_counter() - t0) * 1000
            s = TRACK.setdefault(key, {"hits": 0, "errors": 0, "ms_total": 0.0, "ms_last": 0.0, "last": 0.0})
            s["hits"] += 1
            s["errors"] += status >= 400
            s["ms_total"] += ms
            s["ms_last"] = round(ms, 1)
            s["last"] = time.time()


@router.get("/api/track")
def track_view():
    return sorted(({"route": k, "hits": v["hits"], "errors": v["errors"], "ms_mean": round(v["ms_total"] / v["hits"], 1),
                    "ms_last": v["ms_last"], "ago_s": round(time.time() - v["last"])} for k, v in TRACK.items()),
                  key=lambda r: r["ago_s"])


def _con():
    if store.backend() != "postgres":
        return None
    import psycopg
    return psycopg.connect(store.DSN)


def _columns(con, name):
    rows = con.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s ORDER BY ordinal_position",
                       (name,)).fetchall()
    return [r[0] for r in rows]


@router.get("/api/db/tables")
def tables():
    con = _con()
    if con is None:
        return [{"name": "events", "rows": len(store.read()), "backend": "jsonl"}]
    with con:
        out = []
        for name in RELATIONS:
            try:
                n = con.execute(f'SELECT count(*) FROM "{name}"').fetchone()[0]  # name is from the allowlist
                out.append({"name": name, "rows": n, "backend": "postgres", "columns": _columns(con, name)})
            except Exception:
                con.rollback()
        return out


@router.get("/api/db/rows/{name}")
def rows(name: str, q: str = "", col: str = "", val: str = "", after_id: int = 0, limit: int = Query(200, le=1000),
         format: str = "json"):
    if name not in RELATIONS:
        raise HTTPException(404, "unknown relation")
    con = _con()
    if con is None:  # jsonl mode: events only
        if name != "events":
            raise HTTPException(404, "only events without Postgres")
        data = [{"id": i, **e} for i, e in store.read(after_id)]
        data = [r for r in data if not q or q.lower() in json.dumps(r, default=str).lower()][-limit:][::-1]
        return _out(data, list(data[0].keys()) if data else [], name, format)
    with con:
        cols = _columns(con, name)
        where, args = [], []
        if after_id and "id" in cols:
            where.append("id > %s"); args.append(after_id)
        if q:
            where.append(f'"{name}"::text ILIKE %s'); args.append(f"%{q}%")
        if col:
            if col not in cols:
                raise HTTPException(400, "unknown column")
            where.append(f'"{col}"::text ILIKE %s'); args.append(f"%{val}%")
        order = "id DESC" if "id" in cols else ("seen DESC" if "seen" in cols else "1")
        sql = f'SELECT * FROM "{name}"' + (" WHERE " + " AND ".join(where) if where else "") + f" ORDER BY {order} LIMIT %s"
        cur = con.execute(sql, (*args, limit))
        names = [d.name for d in cur.description]
        # events carry local wall-clock times without a zone; the ledger stored them as UTC instants, so the digits are
        # right and the "+00:00" is not: show them as the local times they are (rows are append-only, never rewritten)
        data = [{k: (v.replace(tzinfo=None).isoformat(sep=" ") if hasattr(v, "tzinfo") and getattr(v, "tzinfo", None) else v)
                 for k, v in zip(names, r)} for r in cur.fetchall()]
    return _out(data, names, name, format)


def _out(data, names, name, format):
    if format == "csv":
        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=names, extrasaction="ignore")
        w.writeheader()
        for r in data:
            w.writerow({k: json.dumps(v, default=str) if isinstance(v, (dict, list)) else v for k, v in r.items()})
        return Response(buf.getvalue(), media_type="text/csv",
                        headers={"Content-Disposition": f'attachment; filename="{name}_{time.strftime("%Y%m%d_%H%M")}.csv"'})
    body = json.dumps(data, default=str)
    if format == "download":
        return Response(body, media_type="application/json",
                        headers={"Content-Disposition": f'attachment; filename="{name}_{time.strftime("%Y%m%d_%H%M")}.json"'})
    return Response(body, media_type="application/json")


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
@router.get("/db", response_class=HTMLResponse, include_in_schema=False)
def page():
    return PAGE


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>REGEN API</title><style>
:root{--bg:#0b0f14;--card:#121821;--line:#223041;--ink:#e6edf3;--dim:#8b98a8;--calm:#7ef0c1;--amber:#f2c14e;--alarm:#ff6b6b;--accent:#6fb7ff}
@media (prefers-color-scheme: light){:root:not([data-theme=dark]){--bg:#f7f9fb;--card:#fff;--line:#dbe3ea;--ink:#0f1720;--dim:#5b6878}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:14px/1.45 system-ui,sans-serif}
header{display:flex;gap:16px;align-items:baseline;padding:14px 16px;border-bottom:1px solid var(--line);flex-wrap:wrap}
h1{font-size:16px;margin:0;letter-spacing:.08em}a{color:var(--accent)}nav a{margin-right:12px}
main{padding:16px;display:grid;gap:16px;max-width:1400px;margin:0 auto}.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;min-width:0}
h2{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--dim);margin:0 0 10px}
.bar{display:flex;gap:8px;flex-wrap:wrap;align-items:center;margin-bottom:10px}
input,select,button{background:var(--bg);color:var(--ink);border:1px solid var(--line);border-radius:6px;padding:6px 8px;font:inherit}
button{cursor:pointer}.live{color:var(--calm)}.dim{color:var(--dim)}.err{color:var(--alarm)}
.wrap{overflow:auto;max-height:62vh;border:1px solid var(--line);border-radius:8px}
table{border-collapse:collapse;width:100%;font:12px/1.4 ui-monospace,monospace}th,td{text-align:left;padding:5px 8px;border-bottom:1px solid var(--line);white-space:nowrap;max-width:420px;overflow:hidden;text-overflow:ellipsis}
th{position:sticky;top:0;background:var(--card);cursor:pointer}tr.new td{animation:fl 2s}@keyframes fl{from{background:rgba(126,240,193,.25)}to{background:transparent}}
.chips{display:flex;gap:6px;flex-wrap:wrap}.chip{border:1px solid var(--line);border-radius:999px;padding:2px 10px;cursor:pointer}.chip.on{border-color:var(--accent);color:var(--accent)}
</style></head><body>
<header><h1>REGEN · API 127.0.0.1:8787</h1><nav><a href="#db">Database</a><a href="#tracker">Request tracker</a><a href="/docs">API docs</a><a href="http://127.0.0.1:3000/control">Control room</a></nav>
<span id="bus" class="dim">connecting to the data bus…</span></header>
<main>
<section class="card" id="db"><h2>Ledger database (Postgres, live)</h2>
<div class="chips" id="tables"></div>
<div class="bar" style="margin-top:10px">
<input id="q" placeholder="search any field (e.g. a company or a job title)" size="38">
<select id="col"><option value="">any column</option></select><input id="val" placeholder="column contains" size="18">
<label><input type="checkbox" id="auto" checked> auto-refresh</label>
<select id="limit"><option>100</option><option selected>200</option><option>500</option><option>1000</option></select>
<button id="csv">Download CSV</button><button id="json">Download JSON</button><span id="count" class="dim"></span></div>
<div class="wrap"><table id="grid"></table></div></section>
<section class="card" id="tracker"><h2>Request tracker (since the API started)</h2><div class="wrap"><table id="track"></table></div></section>
</main><script>
const $=s=>document.querySelector(s);let cur="applications",cols=[],last=0,sortK=null,sortD=-1,rows=[];
const esc=v=>String(v??"").replace(/[&<>]/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;"}[c]));
const fmt=v=>v===null||v===undefined?"":typeof v==="object"?JSON.stringify(v):v;
function qs(extra){const p=new URLSearchParams({q:$("#q").value,col:$("#col").value,val:$("#val").value,limit:$("#limit").value,...extra});return p.toString()}
async function loadTables(){const t=await (await fetch("/api/db/tables")).json();$("#tables").innerHTML=t.map(x=>`<span class="chip ${x.name===cur?"on":""}" data-n="${x.name}">${x.name} <b>${x.rows}</b></span>`).join("");
 const me=t.find(x=>x.name===cur);if(me&&me.columns&&me.columns.join()!==cols.join()){cols=me.columns;$("#col").innerHTML='<option value="">any column</option>'+cols.map(c=>`<option>${c}</option>`).join("")}}
async function load(fresh){const r=await fetch(`/api/db/rows/${cur}?`+qs({}));if(!r.ok){$("#grid").innerHTML=`<tr><td class=err>${r.status}</td></tr>`;return}
 const data=await r.json();const seen=new Set(rows.map(x=>x.id));rows=data;draw(fresh?new Set():seen)}
function draw(seen){let d=rows.slice();if(sortK)d.sort((a,b)=>(fmt(a[sortK])>fmt(b[sortK])?1:-1)*sortD);
 const ks=d.length?Object.keys(d[0]):cols;$("#count").textContent=`${d.length} rows`+(d.length>=+$("#limit").value?" (limit)":"");
 $("#grid").innerHTML="<tr>"+ks.map(k=>`<th data-k="${k}">${k}${sortK===k?(sortD>0?" ▲":" ▼"):""}</th>`).join("")+"</tr>"+d.map(r=>`<tr class="${seen.size&&r.id!==undefined&&!seen.has(r.id)?"new":""}">`+ks.map(k=>`<td title="${esc(fmt(r[k]))}">${esc(fmt(r[k]))}</td>`).join("")+"</tr>").join("")}
async function loadTrack(){const t=await (await fetch("/api/track")).json();$("#track").innerHTML="<tr><th>route</th><th>hits</th><th>errors</th><th>mean ms</th><th>last ms</th><th>last seen</th></tr>"+t.map(x=>`<tr><td>${esc(x.route)}</td><td>${x.hits}</td><td class="${x.errors?"err":""}">${x.errors}</td><td>${x.ms_mean}</td><td>${x.ms_last}</td><td>${x.ago_s}s ago</td></tr>`).join("")}
$("#tables").onclick=e=>{const n=e.target.closest(".chip")?.dataset.n;if(n){cur=n;sortK=null;cols=[];loadTables().then(()=>load(true))}};
$("#grid").onclick=e=>{const k=e.target.closest("th")?.dataset.k;if(k){sortD=sortK===k?-sortD:-1;sortK=k;draw(new Set())}};
let tm;for(const id of ["#q","#val","#col","#limit"])$(id).oninput=()=>{clearTimeout(tm);tm=setTimeout(()=>load(true),250)};
$("#csv").onclick=()=>location.href=`/api/db/rows/${cur}?`+qs({format:"csv",limit:1000});
$("#json").onclick=()=>location.href=`/api/db/rows/${cur}?`+qs({format:"download",limit:1000});
const es=new EventSource("/api/stream?after=999999999");let pend=false;
es.onopen=()=>{$("#bus").textContent="● live (Postgres NOTIFY)";$("#bus").className="live"};es.onerror=()=>{$("#bus").textContent="○ reconnecting";$("#bus").className="dim"};
es.addEventListener("narration",()=>{if($("#auto").checked&&!pend){pend=true;setTimeout(()=>{pend=false;loadTables();load(false)},400)}});
setInterval(()=>{loadTrack();if($("#auto").checked){loadTables();load(false)}},10000);
if(location.pathname==="/db")location.hash="db";loadTables().then(()=>load(true));loadTrack();
</script></body></html>"""
