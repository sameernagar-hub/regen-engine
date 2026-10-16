"""Proxy dataset for the public site: every page of the control room, working on Render with zero private data.

    py scripts/proxy_dataset.py            (writes apps/web/public/proxy/)

The hosted site cannot reach the engine on your machine (it runs in Docker on 127.0.0.1, and Render's free tier has
no volumes, no Docker socket and no browsers). So this script builds a fully synthetic engine state (a fictional
candidate "Jane Doe", made-up companies on made-up boards, a week of events of every kind, fleet heartbeats, reach
list, evals, outreach drafts), points the REAL API (apps/api) at it through REGEN_PROFILE / REGEN_WORKSPACE, and
saves every GET response the web app makes. The shapes are therefore exactly what your machine returns; only the
values are invented. The web app (lib/proxy.ts) serves these files in public mode and simulates the writes in the
browser. Nothing here reads profile/ or workspace/: the privacy gate scans the output like any other file.
"""
import hashlib, json, os, random, shutil, sys, tempfile, time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "apps", "web", "public", "proxy")
R = random.Random(20261016)  # seeded: the dataset is reproducible, so a rebuild only changes what the code changed

COMPANIES = ["Lumenfold", "Kestrel Health", "Brightwater Labs", "Halcyon Pay", "Tidewire Data", "Orbitfreight",
             "Quarrystone Security", "Fernleaf Bio", "Cobaltmesh", "Sundial Learning", "Harborledger", "Vantor Robotics",
             "Mossgate Energy", "Pebblestack", "Northvane Analytics", "Glasswing Cloud", "Ridgeline Maps", "Copperfox Games",
             "Driftwood Insurance", "Saltmarsh AI", "Emberline Media", "Quillworks", "Starling Logistics", "Bluefin Climate",
             "Opaline Retail", "Thistle Payments", "Granite Peak Systems", "Wavelet Audio", "Junebug Health", "Ironbark Devtools",
             "Larkspur Finance", "Meridian Kite", "Nimbuspoint", "Oxbow Search", "Parsec Labs", "Riverglass", "Silvertide Ops",
             "Tamarack Mobility", "Umbra Vision", "Willowbrook Edu"]
ROLES = [("Software Engineer, Backend", "backend"), ("Full Stack Engineer", "fullstack"), ("AI Engineer", "ai"),
         ("Software Engineer I", "backend"), ("Product Engineer", "fullstack"), ("Machine Learning Engineer", "ai"),
         ("Data Engineer", "data"), ("Software Engineer, Platform", "backend"), ("Applied AI Engineer", "ai"),
         ("New Grad Software Engineer", "fullstack"), ("Software Engineer, Payments", "backend"), ("Data Platform Engineer", "data"),
         ("Forward Deployed Engineer", "ai"), ("Software Engineer, Developer Tools", "fullstack")]
ATS = ["greenhouse", "greenhouse", "greenhouse", "ashby", "ashby", "lever", "workable", "rippling"]
QUESTIONS = ["Why do you want to work here?", "Describe a system you designed end to end.",
             "What is your expected start date?", "Link to a project you are proud of",
             "Have you used our product before?", "Which time zone do you prefer to work in?"]
LEGAL = ["Please read the arbitration agreement below", "I confirm the information above is accurate"]

FACTS = {  # the fictional candidate's Fact Bank: ids the resumes cite, like a real one
    "a_api": "Built 9 REST and GraphQL APIs serving 40k daily requests at p95 under 120 ms",
    "a_pg": "Cut a reporting query from 14 s to 600 ms with partial indexes and a materialized view in PostgreSQL",
    "a_kafka": "Moved order events onto Kafka, removing 3 polling jobs and a nightly batch",
    "a_ci": "Wrote the CI pipeline (GitHub Actions, Docker) that runs 1,100 tests in 6 minutes",
    "a_oncall": "Led the on-call rotation for 4 services; wrote the runbooks that halved time to mitigate",
    "b_react": "Shipped a React + TypeScript dashboard used by 300 support agents every day",
    "b_a11y": "Raised the app's Lighthouse accessibility score from 71 to 98",
    "b_next": "Rebuilt the marketing site in Next.js with ISR; time to first byte fell from 900 ms to 140 ms",
    "c_rag": "Built a retrieval pipeline over 60k support articles with pgvector; answer acceptance rose 22%",
    "c_eval": "Wrote an LLM evaluation harness (240 graded cases) that gates every prompt change in CI",
    "c_agent": "Built a tool-calling agent that drafts refunds for human approval, with every action logged",
    "c_mcp": "Exposed an internal search API as an MCP server used by 3 teams' AI clients",
    "d_etl": "Wrote Airflow DAGs that load 2 TB a day from 14 sources into the warehouse with data contracts",
    "d_dbt": "Modeled 80 dbt tables with tests; broken dashboards per month went from 9 to 1",
    "d_stream": "Built a streaming dedupe job (Flink) over 5M events an hour",
    "e_ta": "Teaching assistant for Distributed Systems: ran labs for 60 students",
    "e_hack": "Won 2nd place at a 36-hour campus hackathon with a voice-first study planner",
    "p_engine": "Open-source job engine: source-first discovery, per-job resumes, Docker workers, MCP control",
    "p_vision": "Shelf-scanning app: on-device detection at 24 fps on a mid-range phone",
    "p_ledger": "Double-entry ledger library with property-based tests (Hypothesis)",
}
FACT_ROLE = {"a_": "northbeam", "b_": "northbeam", "c_": "copperline", "d_": "copperline", "e_": "uni", "p_": "projects"}
LANE_FACTS = {"backend": ["a_api", "a_pg", "a_kafka", "a_ci", "a_oncall", "p_ledger"],
              "fullstack": ["b_react", "b_a11y", "b_next", "a_api", "a_ci", "p_vision"],
              "ai": ["c_rag", "c_eval", "c_agent", "c_mcp", "a_api", "p_engine"],
              "data": ["d_etl", "d_dbt", "d_stream", "a_pg", "a_kafka", "p_ledger"]}
TERMS = ["python", "typescript", "react", "postgresql", "kafka", "aws", "docker", "kubernetes", "api", "ci", "llm",
         "rag", "airflow", "dbt", "graphql", "system design", "distributed systems", "observability"]


def profile(d):
    """A complete fictional profile in the real file formats (profile.example shows the same keys)."""
    os.makedirs(d, exist_ok=True)
    w = lambda n, o: json.dump(o, open(os.path.join(d, n), "w", encoding="utf-8"), indent=1)
    w("fact_bank.json", {
        "contact": {"name": "JANE DOE", "line": "Example City, CA | jane@example.com | github.com/janedoe-demo"},
        "facts": {k: v for k, v in FACTS.items()},
        "roles": {"northbeam": ["Northbeam Software (fictional)", "Software Engineer", "Example City, CA", "Jul 2024 - Present"],
                  "copperline": ["Copperline AI (fictional)", "AI Engineering Intern", "Remote", "May 2023 - Dec 2023"],
                  "uni": ["Example State University", "Teaching Assistant", "Example City, CA", "Aug 2022 - May 2024"]},
        "projects": {"engine": ["Open job engine", "2026", [FACTS["p_engine"]]],
                     "vision": ["ShelfSight", "2025", [FACTS["p_vision"]]],
                     "ledger": ["tinyledger", "2024", [FACTS["p_ledger"]]]},
        "skills": {"lang": ["Languages", "Python, TypeScript, Go, SQL"],
                   "web": ["Web", "React, Next.js, FastAPI, Node.js, GraphQL"],
                   "data": ["Data", "PostgreSQL, pgvector, Kafka, Airflow, dbt"],
                   "ai": ["AI", "RAG, LLM evaluation, tool calling, MCP"],
                   "ops": ["Ops", "Docker, Kubernetes, AWS, GitHub Actions"]},
        "education": [["M.S. Computer Science -- Example State University", "2022 - 2024"],
                      ["B.S. Computer Engineering -- Example Institute of Technology", "2018 - 2022"]],
        "awards": ["2nd place, 36-hour campus hackathon (2023)"],
        "publications": [],
        "_sources": [{"date": "2026-10-01", "file": "resume_master.pdf", "added": ["a_api", "a_pg", "b_react"]},
                     {"date": "2026-10-04", "file": "project_notes.md", "added": ["c_mcp", "p_engine"]}],
        "_overlaps": [["a_api", "c_mcp", 0.41]],
    })
    w("presets.json", {"first_name": "Jane", "last_name": "Doe", "email": "jane@example.com", "phone": "555-DEMO",
                       "location": "Example City, CA", "city": "Example City", "state": "CA", "zip": "00000",
                       "address_line1": "100 Example Street", "country": "United States",
                       "linkedin": "https://www.linkedin.com/in/janedoe-demo", "github": "https://github.com/janedoe-demo",
                       "current_employer": "Northbeam Software", "current_title": "Software Engineer",
                       "work_authorized_us": "Yes", "needs_sponsorship_now_or_future": "No", "authorized_without_sponsorship": "Yes",
                       "work_auth_status": "US citizen (demo)", "citizenship_country": "United States",
                       "us_citizen_or_us_person_itar": "Yes", "security_clearance": "None",
                       "school": "Example State University", "degree": "Master's", "major": "Computer Science", "gpa": "3.8",
                       "grad_year": "2024", "years_experience": 2, "start_date": "Two weeks after offer",
                       "open_to_onsite_or_relocation": "Yes", "needs_relocation_assistance": "No",
                       "willing_background_check": "Yes", "over_18": "Yes", "how_heard": "Company careers page",
                       "market_salary": "$135,000", "eeo": "decline", "submit_policy": "auto",
                       "edu_start_month": "August", "edu_start_year": "2022", "edu_end_month": "May", "edu_end_year": "2024"})
    w("lanes.json", {"lanes": {k: {"headline": f"Software Engineer | {k}", "summary": "Demo lane.",
                                   "roles": [["northbeam", v[:3]], ["copperline", v[3:5]]], "projects": ["engine"], "skills": ["lang", "web"]}
                               for k, v in LANE_FACTS.items()},
                     "routing": [["ai", "ai|machine learning|ml|llm", "title"], ["data", "data", "title"],
                                 ["fullstack", "full.?stack|front|product", "title"]], "default": "backend"})
    shutil.copy(os.path.join(ROOT, "profile.example", "domains.json"), os.path.join(d, "domains.json"))


def iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(t))


def board_url(co, ats, i):
    slug = co.lower().replace(" ", "")
    return {"greenhouse": f"https://boards.example.com/greenhouse/{slug}/jobs/{4000000 + i}",
            "ashby": f"https://boards.example.com/ashby/{slug}/{i:08x}-demo",
            "lever": f"https://boards.example.com/lever/{slug}/{i:06d}",
            "workable": f"https://boards.example.com/workable/{slug}/j/{i:06X}",
            "rippling": f"https://boards.example.com/rippling/{slug}/jobs/{i}",
            "workday": f"https://{slug}.wd1.example.com/External/job/Remote/{i}",
            "icims": f"https://careers-{slug}.icims.example.com/jobs/{i}/job",
            "smartrecruiters": f"https://jobs.example.com/smartrecruiters/{slug}/{i}"}[ats]


def workspace(d, now):
    """A week of engine activity in the real ledger format, plus the side files the API reads."""
    for sub in ("logs", "out", "proof", "fleet", "bench", "outreach", "batches/inbox", "batches/claimed", "batches/done", "codes"):
        os.makedirs(os.path.join(d, sub), exist_ok=True)
    ev, jobs = [], []
    t0 = now - 7 * 86400
    for i in range(150):
        co = COMPANIES[i % len(COMPANIES)]
        role, lane = ROLES[(i * 5 + i // 14) % len(ROLES)]
        ats = ATS[i % len(ATS)]
        t = t0 + (i / 150) * 7 * 86400 + R.randint(0, 1800)
        jobs.append(dict(job=f"{co} - {role}", url=board_url(co, ats, 1000 + i), lane=lane, ats=ats, t=t, co=co))
    statuses = (["SUBMITTED"] * 9 + ["NEEDS YOU"] * 3 + ["SKIPPED"] * 3 + ["FAILED"] + ["FLAGGED"])
    proofs, resumes = [], []
    for i, j in enumerate(jobs):
        t = j["t"]
        ev.append(dict(ts=iso(t), kind="discovered", job=j["job"], url=j["url"], ats=j["ats"], lag_min=R.randint(1, 55)))
        st = statuses[i % len(statuses)]
        if st == "SKIPPED":
            ev.append(dict(ts=iso(t + 30), kind="application", job=j["job"], url=j["url"], status="SKIPPED", dry=False,
                           detail=R.choice(["JD: 5+ yrs", "JD: US citizenship required", "JD: graduation window 2027", "title excluded: senior"])))
            continue
        lane = j["lane"]
        have = R.sample(TERMS, 9)
        file = f"Resume_{j['co'].replace(' ', '')}_{1000 + i}.pdf"
        resumes.append(file)
        ev.append(dict(ts=iso(t + 60), kind="resume", job=j["job"], url=j["url"], lane=lane, file=file,
                       facts=[[FACT_ROLE[f[:2]], [f]] for f in LANE_FACTS[lane][:5]],
                       coverage={"jd_terms_you_have": have, "on_resume": have[:-1], "missing_from_resume": have[-1:]},
                       skills=["lang", "web"], projects=["engine"]))
        rec = dict(ts=iso(t + 300 + R.randint(0, 900)), kind="application", job=j["job"], url=j["url"], dry=False,
                   resume=f"out\\{file}", answers=[["First Name", "Jane"], ["Last Name", "Doe"], ["Email", "jane@example.com"],
                                                   ["Do you now or in the future require sponsorship?", "No"],
                                                   [QUESTIONS[i % len(QUESTIONS)], "Drafted from Fact Bank: " + FACTS[LANE_FACTS[lane][0]]],
                                                   ["Gender", "__DECLINE__"]])
        if st == "SUBMITTED":
            p = f"proof/{j['co'].replace(' ', '_')}_{1000 + i}.png"
            proofs.append((p, j))
            open(os.path.join(d, p), "wb").write(b"PNG demo")  # the API counts a submission only when its proof exists
            rec.update(status="SUBMITTED", detail=R.choice(["Greenhouse thank-you page", "Ashby success banner", "Lever confirmation"]), proof=p)
        elif st == "NEEDS YOU":
            qs = [QUESTIONS[(i + 1) % len(QUESTIONS)]] + ([LEGAL[i % 2]] if i % 2 else [])
            rec.update(status="NEEDS YOU", detail="NEEDS YOU: " + " | ".join(qs))
        elif st == "FAILED":
            rec.update(status="FAILED", detail="education Degree/Discipline selects not filled")
        else:
            ev.append(dict(ts=iso(t + 280), kind="flag", flag_kind="airbag", job=j["job"], url=j["url"],
                           detail="form asks for sensitive data: Date of birth"))
            rec.update(status="FLAGGED", detail="FLAGGED: FLAG airbag: form asks for sensitive data: Date of birth")
        ev.append(rec)
        if st == "SUBMITTED" and i % 4 == 0:
            ev.append(dict(ts=iso(t + 3600 * R.randint(2, 30)), kind="outcome", msg_id=hashlib.md5(j["url"].encode()).hexdigest()[:16],
                           outcome=R.choice(["confirmation", "confirmation", "rejection", "assessment"]), company=j["co"],
                           subject=f"Your application for {j['job'].split(' - ', 1)[1]} at {j['co']}", sender="no-reply",
                           date=time.strftime("%a, %d %b %Y, %H:%M", time.localtime(t + 7200)), jobs=[j["url"], j["job"]], lanes=[lane]))
        if st == "NEEDS YOU" and i % 3 == 0:
            ev.append(dict(ts=iso(t + 5000), kind="answer", job=j["job"], question=QUESTIONS[i % len(QUESTIONS)],
                           pattern=QUESTIONS[i % len(QUESTIONS)].lower(), source="web app"))
    for k in range(0, 7 * 24, 3):  # pipeline passes and scheduler records, like the loop writes them
        t = t0 + k * 3600
        ev.append(dict(ts=iso(t), kind="pipeline", stage="select", queued=R.randint(380, 620), chosen=R.randint(4, 24), ashby=True))
        ev.append(dict(ts=iso(t + 600), kind="schedule", jobs=R.randint(4, 12), tabs=4, wall_s=R.randint(300, 900),
                       active_s=R.randint(250, 850), switches=R.randint(20, 80), quantum={"ashby": 6.4, "greenhouse": 20.0}, per_job=[]))
    for k in range(3):
        ev.append(dict(ts=iso(now - k * 86400 - 3000), kind="alerts", listings=R.randint(90, 160), leads=R.randint(50, 100),
                       resolved=R.randint(20, 40), unresolved=R.randint(30, 60), dropped={"title": 12, "non-US": 2}))
    for k in range(10):
        ev.append(dict(ts=iso(now - k * 3 * 3600 - 200), kind="supervisor", action=R.choice(["scale", "requeue", "probe", "clean"]),
                       target=R.choice(["applier", "batches", "api", "proof"]), reason=R.choice(["backlog 14 jobs", "idle 10 min", "ok", "retention 90 d"]),
                       jobs=R.randint(0, 20), want=R.randint(1, 5)))
    ev.sort(key=lambda e: e["ts"])
    with open(os.path.join(d, "events.jsonl"), "w", encoding="utf-8") as f:
        f.writelines(json.dumps(e) + "\n" for e in ev)

    w = lambda n, o: json.dump(o, open(os.path.join(d, n), "w", encoding="utf-8"), indent=1)
    w("boards.json", {a: [f"board-{a}-{k}" for k in range(n)] for a, n in
                      (("greenhouse", 2210), ("ashby", 980), ("lever", 640), ("workable", 310), ("workday", 520), ("smartrecruiters", 260), ("icims", 174))})
    open(os.path.join(d, "seen.json"), "w").write("{}")
    w("queue.json", [dict(source="ats", ats=ATS[k % len(ATS)], company=COMPANIES[k % 40], title=ROLES[k % len(ROLES)][0],
                          url=board_url(COMPANIES[k % 40], ATS[k % len(ATS)], 9000 + k), posted=iso(now - k * 600)) for k in range(486)])
    # an applier log per worker, in the runner's line format (control.py APPLIER_LINE)
    for wk in range(1, 4):
        lines = []
        for s in range(4):
            j = jobs[(wk * 11 + s * 5) % len(jobs)]
            slug = f"t{s}"
            lines += [f"[{slug}] == {j['job']}", f"[{slug}] . {QUESTIONS[(wk + s) % 6][:60]} -> drafted from Fact Bank",
                      f"[{slug}] . Do you now or in the future require sponsorship? -> No"]
            if s < 3:
                lines.append(f"[{slug}] -> " + ["SUBMITTED", "NEEDS YOU: " + QUESTIONS[s], "SUBMITTED"][s])
        open(os.path.join(d, "logs", f"run_{time.strftime('%Y%m%d_%H%M', time.localtime(now))}_w{wk}.log"), "w").write("\n".join(lines) + "\n")
    w("run_ui.json", {"pid": None, "params": {"days": 3, "max": 60, "appliers": 3, "tabs": 4, "scan": True, "newgrad": True, "feed": True,
                                              "ats": ["greenhouse", "lever", "ashby"], "cap": 60, "dry": False, "loop": 10},
                      "stamp": "demo", "log": "logs/ui_demo.log", "started": now - 1500,
                      "steps": [{"name": "discover", "status": "done", "started": now - 1500, "finished": now - 1240},
                                {"name": "newgrad", "status": "done", "started": now - 1240, "finished": now - 1100},
                                {"name": "feed", "status": "done", "started": now - 1100, "finished": now - 1010},
                                {"name": "apply", "status": "running", "started": now - 1010}], "finished": None})
    open(os.path.join(d, "logs", "ui_demo.log"), "w").write(
        "discover: 5,094 boards polled, 41 new postings in 260 s\nnewgrad: 12 leads resolved to the employer's ATS\n"
        "feed: 7 roles from curated lists\napply: 18 selected, 3 appliers x 4 tabs, round-robin\n"
        "apply: 6 submitted with proof, 2 need you, 1 skipped by the airbag\n")
    beats = [("pipeline", "pipeline-1", dict(state="scanning", **{"pass": 214})), ("relay", "relay-1", dict(state="ok", last_post=now - 30)),
             ("supervisor", "supervisor-1", dict(state="watching", imap=True, services={s: "ok" for s in ("api", "web", "mcp", "ledger", "postgres", "answers", "reposync", "desk")})),
             ("answers", "answers-1", dict(state="watching")), ("desk", "desk-1", dict(state="ready", queue=0))]
    beats += [("applier", f"applier-{k}", dict(state=["applying", "applying", "watching", "applying"][k - 1], batch=f"b{k:04}.json")) for k in range(1, 5)]
    for role, host, st in beats:
        w(f"fleet/{role}_{host}.json", dict(st, role=role, host=host, ts=now - R.randint(2, 25)))
    for k in range(3):
        w(f"batches/inbox/b{100 + k:04}.json", [{}] * 6)
    for k in range(1, 4):
        w(f"batches/claimed/b{k:04}.json", [{}] * 6)
    for k in range(40):
        w(f"batches/done/b{k + 10:04}.json", [])
    svcs = ["api", "web", "mcp", "ledger", "postgres", "pipeline", "relay", "supervisor", "answers", "reposync", "desk"]
    boxes = [dict(id=hashlib.md5(s.encode()).hexdigest()[:12], name=f"deploy-{s}-1", service=s, state="running", status="Up 6 hours",
                  image=f"regen-{s}:latest", created=now - 6 * 3600, scaled=False, managed=False, declared=True,
                  cpu=round(R.uniform(0.2, 9), 1), mem_mb=R.randint(40, 420), mem_limit_mb=1024) for s in svcs]
    boxes += [dict(id=f"applier{k}abcd", name=f"deploy-applier-{k}", service="applier", state="running", status=f"Up {k} hours",
                   image="regen-applier:latest", created=now - k * 3600, scaled=True, managed=True, declared=True,
                   cpu=round(R.uniform(18, 60), 1), mem_mb=R.randint(600, 1100), mem_limit_mb=2048) for k in range(1, 5)]
    w("containers.json", {"ts": now - 20, "project": "deploy", "containers": boxes,
                          "totals": {"running": len(boxes), "all": len(boxes), "cpu": round(sum(b["cpu"] for b in boxes), 1),
                                     "mem_mb": sum(b["mem_mb"] for b in boxes)}})
    reach = []
    for k in range(36):
        co, ats = COMPANIES[(k * 3) % 40], ["workday", "workday", "icims", "smartrecruiters"][k % 4]
        role, lane = ROLES[k % len(ROLES)]
        reach.append(dict(listed=iso(now - k * 4000), ats=ats, company=co, title=role, url=board_url(co, ats, 5000 + k),
                          location=R.choice(["Remote, US", "Example City, CA", "New York, NY", "Austin, TX"]), lane=lane,
                          jd_match=R.randint(72, 100), resume=f"out/Resume_{co.replace(' ', '')}_R{k}.pdf"))
        resumes.append(f"Resume_{co.replace(' ', '')}_R{k}.pdf")
    w("reach.json", reach)
    with open(os.path.join(d, "events.jsonl"), "a", encoding="utf-8") as f:
        for k in range(0, 9, 3):
            f.write(json.dumps(dict(ts=iso(now - 2000 + k), kind="reach_mark", url=reach[k]["url"], status="submitted",
                                    job=f"{reach[k]['company']} - {reach[k]['title']}", ats=reach[k]["ats"])) + "\n")
    # benchmark history: one run every 6 hours, drifting the way real runs do
    for k in range(28):
        t = now - (27 - k) * 6 * 3600
        out = {"B1_select": {"speedup": round(R.uniform(8, 14), 1), "heap_ms": 3.1, "sort_ms": 38.0},
               "B2_answers": {"answerable_pct": round(61 + k * 0.6 + R.uniform(-2, 2), 1), "answerable_now": 140 + k},
               "B3_claims": {"exactly_once": True, "unique": 40, "batches": 40},
               "B4_coverage": {"median_coverage_pct": round(86 + R.uniform(-3, 4), 1), "median_ats_readback": "92%"},
               "B5_rate": {"best_per_h": round(9 + k * 0.15 + R.uniform(-1, 1), 1)},
               "B6_codes": {"median_s": R.randint(14, 30), "p90_s": R.randint(40, 70), "code_timeouts": R.randint(0, 2)},
               "B7_fitgate": {"catch_rate_pct": round(9 + k * 0.35, 1), "would_block_ok_pct": round(1.1 + k * 0.04, 1), "submitted_with_jd": 120 + k},
               "B8_supervisor": {"passed": 9, "total": 9, "failed": []},
               "B9_api": {"p50_ms": R.randint(6, 12), "p95_ms": R.randint(18, 45)},
               "B10_bus": {"ok": True, "latency_ms": R.randint(400, 2100)}}
        from engine.bench import summary
        rec = {"ts": t, "reason": R.choice(["commit", "every 6 h", "operator"]), "sha": hashlib.sha1(str(k).encode()).hexdigest()[:7],
               "summary": summary(out), "results": out}
        w(f"bench/{time.strftime('%Y%m%d_%H%M%S', time.localtime(t))}.json", rec)
        if k == 27:
            w("bench/latest.json", rec)
    sub = [j for j in jobs if any(p[1] is j for p in proofs)][-12:]
    from engine.outreach import draft  # the engine's own composer, over the synthetic Fact Bank
    bank = json.load(open(os.environ["REGEN_PROFILE"] + "/fact_bank.json", encoding="utf-8"))
    w("outreach/drafts.json", [draft(dict(company=j["co"], role=j["job"].split(" - ", 1)[1], url=j["url"], ts=iso(j["t"] + 900),
                                          why=R.choice(["tier 1", "tier 2", "startup"]), lane=j["lane"], facts=LANE_FACTS[j["lane"]][:4]), bank)
                               for j in sub])
    return jobs, proofs, resumes


def proof_svg(j):
    co, role = j["job"].split(" - ", 1)
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="500" viewBox="0 0 800 500">'
            f'<rect width="800" height="500" fill="#f6f7f9"/><rect x="40" y="40" width="720" height="420" rx="14" fill="#fff" stroke="#d8dce3"/>'
            f'<circle cx="400" cy="160" r="38" fill="#16a34a"/><path d="M382 160l12 12 24-26" stroke="#fff" stroke-width="7" fill="none" stroke-linecap="round"/>'
            f'<text x="400" y="250" font-family="Segoe UI,Arial" font-size="28" text-anchor="middle" fill="#111">Application submitted</text>'
            f'<text x="400" y="290" font-family="Segoe UI,Arial" font-size="18" text-anchor="middle" fill="#444">{role} · {co}</text>'
            f'<text x="400" y="330" font-family="Segoe UI,Arial" font-size="14" text-anchor="middle" fill="#888">Thank you for applying. (Synthetic proof for the public demo.)</text>'
            f'</svg>')


def lane_of(file, jobs):
    """Resume_<Co>_<1000+i>.pdf belongs to jobs[i]; Resume_<Co>_R<k>.pdf to reach row k (ROLES[k])."""
    tail = file[:-4].rsplit("_", 1)[-1]
    return ROLES[int(tail[1:]) % len(ROLES)][1] if tail.startswith("R") else jobs[int(tail) - 1000]["lane"]


def resume_html(lane):
    """The resume a lane would produce for the fictional candidate, laid out like the engine's one-page PDF."""
    roles = {"northbeam": ("Northbeam Software (fictional)", "Software Engineer", "Jul 2024 - Present"),
             "copperline": ("Copperline AI (fictional)", "AI Engineering Intern", "May 2023 - Dec 2023")}
    by_role = {}
    for f in LANE_FACTS[lane]:
        by_role.setdefault(FACT_ROLE[f[:2]], []).append(FACTS[f])
    sec = "".join(f"<div class=r><b>{roles[r][1]}</b> · {roles[r][0]}<span>{roles[r][2]}</span></div><ul>"
                  + "".join(f"<li>{x}</li>" for x in xs) + "</ul>" for r, xs in by_role.items() if r in roles)
    proj = "".join(f"<li>{x}</li>" for r, xs in by_role.items() if r not in roles for x in xs)
    return ("<!doctype html><meta charset=utf-8><title>Jane Doe resume (demo)</title><style>"
            "body{margin:0;background:#fff;color:#111;font:13px/1.45 Georgia,serif}main{max-width:720px;margin:0 auto;padding:36px 40px}"
            "h1{margin:0;font:600 24px/1.1 Helvetica,Arial,sans-serif;letter-spacing:.04em}.c{color:#555;margin:4px 0 14px}"
            "h2{font:600 11px Helvetica,Arial,sans-serif;letter-spacing:.14em;text-transform:uppercase;border-bottom:1px solid #ccc;margin:16px 0 6px;padding-bottom:3px}"
            ".r{display:flex;gap:6px}.r span{margin-left:auto;color:#555}ul{margin:4px 0 10px 18px;padding:0}li{margin:2px 0}"
            ".demo{margin-top:22px;color:#888;font-size:11px}</style><main>"
            f"<h1>JANE DOE</h1><div class=c>Example City, CA · jane@example.com · github.com/janedoe-demo · {lane} lane</div>"
            f"<h2>Experience</h2>{sec}" + (f"<h2>Projects</h2><ul>{proj}</ul>" if proj else "")
            + "<h2>Skills</h2><div>Python, TypeScript, Go, SQL · React, Next.js, FastAPI · PostgreSQL, Kafka · Docker, AWS</div>"
            "<h2>Education</h2><div class=r>M.S. Computer Science · Example State University<span>2022 - 2024</span></div>"
            "<p class=demo>Synthetic resume for the public REGEN demo: a fictional candidate. Every line comes from the demo Fact Bank, "
            "the way a real resume comes only from yours.</p></main>")


def pdf(lines):
    """A one-page PDF with plain text lines (no dependencies): enough for the resume viewer to show something real."""
    y, body = 740, []
    for i, l in enumerate(lines):
        size = 18 if i == 0 else 10
        esc = l.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        body.append(f"BT /F1 {size} Tf 56 {y} Td ({esc}) Tj ET")
        y -= 26 if i == 0 else 15
    stream = "\n".join(body).encode("latin-1", "replace")
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>", b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"]
    out, offs = bytearray(b"%PDF-1.4\n"), []
    for n, o in enumerate(objs, 1):
        offs.append(len(out))
        out += f"{n} 0 obj\n".encode() + o + b"\nendobj\n"
    x = len(out)
    out += f"xref\n0 {len(objs) + 1}\n0000000000 65535 f \n".encode() + b"".join(f"{o:010} 00000 n \n".encode() for o in offs)
    out += f"trailer\n<< /Size {len(objs) + 1} /Root 1 0 R >>\nstartxref\n{x}\n%%EOF\n".encode()
    return bytes(out)


def main():
    now = time.time()
    tmp = tempfile.mkdtemp(prefix="regen-proxy-")
    prof, ws = os.path.join(tmp, "profile"), os.path.join(tmp, "workspace")
    os.environ.update(REGEN_PROFILE=prof, REGEN_WORKSPACE=ws, REGEN_API_WRITE="0", REGEN_DATABASE_URL="", REGEN_DB_HOST="")
    sys.path.insert(0, ROOT)
    profile(prof)
    jobs, proofs, resumes = workspace(ws, now)
    for f in resumes:
        lane = lane_of(f, jobs)
        open(os.path.join(ws, "out", f), "wb").write(pdf(["JANE DOE", "Example City, CA | jane@example.com | github.com/janedoe-demo",
                                                          "Synthetic resume for the public REGEN demo (fictional candidate).", "",
                                                          f"{lane.upper()} LANE"] + [f"- {FACTS[x]}" for x in LANE_FACTS[lane]]))

    from fastapi.testclient import TestClient
    from apps.api.main import app
    c = TestClient(app)
    if os.path.isdir(OUT):
        shutil.rmtree(OUT)
    os.makedirs(os.path.join(OUT, "files"))
    os.makedirs(os.path.join(OUT, "job"))
    routes = ["/api/snapshot", "/api/applications?limit=2000", "/api/human", "/api/narration?limit=200", "/api/stations?recent=12",
              "/api/graph?questions=false", "/api/control/state", "/api/control/fleet", "/api/control/bench", "/api/control/evals?n=60",
              "/api/control/reach?limit=500", "/api/control/filters", "/api/reach/desk", "/api/reach/signins", "/api/reach/kit",
              "/api/factbank", "/api/outreach", "/api/control/containers"]
    manifest = {"generated": now, "note": "Synthetic data: fictional candidate and companies. Built by scripts/proxy_dataset.py.",
                "routes": {}, "jobs": {}}
    for r in routes:
        res = c.get(r)
        if res.status_code != 200:
            raise SystemExit(f"{r}: HTTP {res.status_code} {res.text[:300]}")
        name = r.split("?")[0].removeprefix("/api/").replace("/", "_") + ".json"
        json.dump(res.json(), open(os.path.join(OUT, name), "w", encoding="utf-8"), separators=(",", ":"))
        manifest["routes"][r.split("?")[0]] = name
    for j in jobs:
        res = c.get("/api/job", params={"url": j["url"]})
        if res.status_code == 200:
            name = hashlib.sha1(j["url"].encode()).hexdigest()[:12] + ".json"
            json.dump(res.json(), open(os.path.join(OUT, "job", name), "w", encoding="utf-8"), separators=(",", ":"))
            manifest["jobs"][j["url"]] = name
    for p, j in proofs:
        open(os.path.join(OUT, "files", os.path.basename(p)[:-4] + ".svg"), "w", encoding="utf-8").write(proof_svg(j))
    for f in resumes:  # the repo never holds PDFs (privacy gate + .gitignore), so the public copy is a one-page HTML resume
        lane = lane_of(f, jobs)
        open(os.path.join(OUT, "files", f[:-4] + ".html"), "w", encoding="utf-8").write(resume_html(lane))
    json.dump(manifest, open(os.path.join(OUT, "manifest.json"), "w", encoding="utf-8"), indent=1)
    shutil.rmtree(tmp, ignore_errors=True)
    n = sum(len(fs) for _, _, fs in os.walk(OUT))
    print(f"proxy dataset: {len(manifest['routes'])} routes, {len(manifest['jobs'])} job timelines, {n} files -> {os.path.relpath(OUT, ROOT)}")


if __name__ == "__main__":
    main()
