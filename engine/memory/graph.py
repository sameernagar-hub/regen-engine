"""The engine's memory as a graph, built from evidence on disk (schema.cypher is the same model for Neo4j).

  (:You)-[:WRITES_AS]->(:Lane)-[:SENT]->(:Application)-[:AT]->(:Company)
  (:Application)-[:INCLUDES]->(:Fact)        which Fact Bank entries the resume used (shared facts = reused knowledge)
  (:Application)-[:ANSWERED {value}]->(:Question)
  (:Application)-[:RESULTED_IN]->(:Outcome)  confirmation / rejection / oa / interview / offer
  (:Application)-[:HOSTED_ON]->(:ATS)

Read-only and derived: nothing here is a new fact. Used by the API (/api/graph) and the MCP server.
"""
import json, os, re

from engine.config import WORKSPACE, profile_file

ATS = (("greenhouse", "Greenhouse"), ("ashbyhq", "Ashby"), ("lever.co", "Lever"), ("workable", "Workable"))


def _events():
    p = os.path.join(WORKSPACE, "events.jsonl")
    if not os.path.exists(p):
        return
    for line in open(p, encoding="utf-8"):
        try:
            yield json.loads(line)
        except ValueError:
            continue


def _fact_text():
    try:
        fb = json.load(open(os.environ.get("REGEN_FACTS") or profile_file("fact_bank.json"), encoding="utf-8"))
        return {k: re.sub(r"<[^>]+>", "", v) for k, v in fb.get("facts", {}).items()}
    except (OSError, ValueError):
        return {}


def build(submitted_only=True, questions=True):
    resumes, latest, outcomes = {}, {}, []
    for e in _events():
        k = e.get("kind")
        if k == "resume" and e.get("job"):
            resumes[e["job"]] = e
        elif k == "application" and not e.get("dry") and e.get("job"):
            latest[e["job"]] = e
        elif k == "outcome":
            outcomes.append(e)
    facts = _fact_text()
    nodes, edges = {}, []

    def node(i, t, label, **data):
        nodes.setdefault(i, {"id": i, "type": t, "label": label, "data": data})
        return i

    def edge(a, b, t, **data):
        edges.append({"source": a, "target": b, "type": t, **({"data": data} if data else {})})

    you = node("you", "You", "You")
    for job, e in latest.items():
        st = (e.get("status") or "").split(":")[0]
        if submitted_only and st != "SUBMITTED":
            continue
        r = resumes.get(job, {})
        lane = node("lane:" + (r.get("lane") or "earlier"), "Lane", r.get("lane") or "earlier")
        if not any(x["source"] == you and x["target"] == lane for x in edges):
            edge(you, lane, "WRITES_AS")
        co, _, role = job.partition(" - ")
        app = node("app:" + job, "Application", role.strip() or job, company=co.strip(), status=st, ts=e.get("ts"),
                   proof=os.path.basename(e.get("proof") or "") or None)
        edge(lane, app, "SENT")
        edge(app, node("co:" + co.strip().lower(), "Company", co.strip()), "AT")
        url = e.get("url") or ""
        for key, name in ATS:
            if key in url:
                edge(app, node("ats:" + name, "ATS", name), "HOSTED_ON")
        for _, fids in r.get("facts") or []:
            for f in fids:
                edge(app, node("fact:" + f, "Fact", f, text=facts.get(f, "")), "INCLUDES")
        if questions:
            for q, a in e.get("answers") or []:
                if not isinstance(q, str) or a is None:
                    continue
                qn = node("q:" + q.lower()[:80], "Question", q[:90])
                shown = {"__DECLINE__": "declined", "__ACK__": "acknowledged"}.get(str(a), str(a))
                edge(app, qn, "ANSWERED", value=shown[:120])
    for o in outcomes:
        for job in o.get("jobs") or []:
            if "app:" + job in nodes:
                on = node(f"out:{o.get('msg_id') or o.get('ts')}:{job}", "Outcome", o.get("outcome", "?"),
                          at=o.get("date") or o.get("ts"), subject=o.get("subject"))
                edge("app:" + job, on, "RESULTED_IN")
    return {"nodes": list(nodes.values()), "edges": edges}


def neighbors(node_id, graph=None):
    g = graph or build()
    ids = {e["target"] for e in g["edges"] if e["source"] == node_id} | {e["source"] for e in g["edges"] if e["target"] == node_id}
    return {"node": next((n for n in g["nodes"] if n["id"] == node_id), None),
            "neighbors": [n for n in g["nodes"] if n["id"] in ids],
            "edges": [e for e in g["edges"] if node_id in (e["source"], e["target"])]}
