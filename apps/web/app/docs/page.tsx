"use client";
// /docs (ALIVE Phase 5 part 2, docs/ALIVE_PLAN.md §5): "Use REGEN" for someone starting a run, and "Build on REGEN"
// for someone extending it. Content is copied from the wiki (Running, Gearbox, Shadow, FAQ, MCP-Tools) and from the
// plan's §3 container map and §4 event contract: no new facts. Also rendered as Garage > Docs inside the drawer.
import { useState } from "react";
import { Nav } from "../nav";

const START = `cd regen-engine
REGEN_MCP_WRITE=1 REGEN_DAYS=30 REGEN_MAX_PER_DAY=150 REGEN_TABS=4 \\
REGEN_ASHBY_PER_PASS=1 REGEN_LOOP_MIN=3 REGEN_SOURCES_EVERY=3 REGEN_MAX=150 \\
docker compose -f deploy/bank.compose.yml up -d --scale applier=1`;
const ENGINE = "docker exec -u 10001 deploy-pipeline-1 python -m engine";
const MCP = `{
  "mcpServers": {
    "regen-engine": { "command": "python", "args": ["-m", "engine", "mcp"] },
    "regen-bank":   { "type": "http", "url": "http://127.0.0.1:8790/mcp" }
  }
}`;

const GEARS: [string, string, string, string][] = [
  ["N", "0-0", "no new passes", "idle without a kill; in-flight forms finish"],
  ["1 crawl", "1-1", "10 min", "watching a new ATS or a rule change closely"],
  ["2 cruise", "1-3", "5 min", "the everyday choice on a laptop"],
  ["3 drive", "1-7", "3 min", "a big fresh supply; the governor still holds the fleet to what the machine carries"],
  ["4 overdrive", "2-9", "2 min", "a bigger machine than a 7.6 GB laptop VM"],
];
const SHADOW: [string, string][] = [
  ["Off", "parked questions ring for you; Shadow never picks up"],
  ["Calls (default)", "two calls 5 minutes apart, then Shadow answers as you and the job is retried"],
  ["Autopilot", "no calls: Shadow answers on the form itself and picks up parked jobs at once, abstaining when unsure"],
];
const FAQ: [string, string][] = [
  ["Does it use an LLM to write answers?", "No. Resumes and drafted answers are assembled from the Fact Bank. That is what makes \"nothing invented\" checkable."],
  ["Will it lie on a form to get through?", "No. Legal answers come only from the presets, anything unknown goes to you, and an airbag stops a submission whose legal answers drift from the presets."],
  ["Does it solve CAPTCHAs?", "No, and neither does Shadow. The form is filled up to the check and waits for you on the Desk."],
  ["Where is my data?", "On your machine, in the bank's Docker volumes (profile and workspace). CI blocks commits that would leak personal data."],
  ["Can I see what it sent?", "Yes: every receipt on the trail opens its proof (the confirmation text), the questions and answers, and the resume it used."],
  ["Does it run on its own?", "No. You start it and you stop it; nothing is scheduled."],
];
const PARTS: [string, string, string][] = [
  ["Source cells", "pipeline scan + scout", "discovered pulses; charge = postings heard in the last hour"],
  ["Judge (inverter)", "pipeline fit gate", "gate.skip pulses fall to ground with the reason"],
  ["Write coil", "pipeline compose", "resume pulses; postings ride the coil as beads"],
  ["Apply coil + rotor", "applier-N (heartbeats)", "apply.start; the rotor spins at gear speed while warm"],
  ["Sent flywheel", "ledger (postgres + ledger)", "submitted pulses, flywheel kick, receipt trail"],
  ["Hear (return line)", "feedback + supervisor IMAP", "outcome pulses flow back to the cells"],
  ["Shadow motor + clutch", "answers (Shadow tick)", "shadow.* pulses; the clutch engages on autopilot"],
  ["Your turn capacitor", "/api/human + desk", "parked pulses charge it; human.check"],
  ["Warning lights", "supervisor problems", "/control/fleet problems"],
];
const ROUTES: [string, string][] = [
  ["GET /api/stream", "server-sent events: narration (pipeline) and signal (controls)"],
  ["GET /api/narration, /api/signals", "the recent events, folded the same way as live ones"],
  ["GET /api/applications, /api/proof/{name}", "the ledger's applications and their proof"],
  ["GET /api/human, POST /api/answers", "what waits on you, and answering it"],
  ["GET|POST /api/control/gearbox", "gear (and the governor snapshot)"],
  ["GET|POST /api/control/cap, /keywords, /targeting", "daily cap level, Role Keywords, targeting"],
  ["GET /api/control/fleet", "every container's heartbeat and the problems list"],
  ["GET|POST /api/shadow, /api/shadow/brain", "Shadow's mode and what it has learned"],
  ["GET /api/report/rate, /funnel, /ab", "interviews per 100, the funnel, the Role Keywords A/B"],
  ["GET /api/outreach, POST /api/outreach/sent", "drafted notes and marking one you sent"],
];

function Code({ children }: { children: string }) {
  return <pre className="dc-code"><code>{children}</code></pre>;
}

export default function Docs() {
  const [part, setPart] = useState<"use" | "build">("use");
  return (
    <main className="page dc">
      <Nav />
      <header className="dc-head">
        <h1>Docs</h1>
        <div role="tablist" aria-label="Docs sections" className="dc-tabs">
          <button type="button" role="tab" aria-selected={part === "use"} onClick={() => setPart("use")}>Use REGEN</button>
          <button type="button" role="tab" aria-selected={part === "build"} onClick={() => setPart("build")}>Build on REGEN</button>
        </div>
      </header>

      {part === "use" ? (
        <article className="dc-body" role="tabpanel" aria-label="Use REGEN">
          <section>
            <h2>Try it first</h2>
            <p>No Docker, no database, nothing applied: read a resume, scan sample boards, print the 10 best-fitting fresh roles and why each passed.</p>
            <Code>{"python -m engine try resume.txt"}</Code>
          </section>
          <section>
            <h2>Start a run</h2>
            <ol>
              <li>Start the stack (Docker Desktop running):<Code>{START}</Code></li>
              <li>Shift into gear: the gear lever on Drive, or <code>{ENGINE} gear 2</code>. Nothing applies in N.</li>
              <li>Pick the daily cap (15 / 25 / 50 / 100 / 150 a day; every start begins at the lowest level): the cap dial, or <code>{ENGINE} cap 4</code>.</li>
              <li>Choose Role Keywords on or off for this run (off by default): the switch, or <code>{ENGINE} keywords on</code>.</li>
              <li>Pick Shadow's mode (below). Then watch: current flows on a wire only while its container is warm.</li>
            </ol>
          </section>
          <section>
            <h2>Gears</h2>
            <p>The gear is the range of appliers you allow. How many run is the smallest of that range, the queue and the governor, which re-judges memory, CPU, page timeouts and the daily cap every pass.</p>
            <table><thead><tr><th>Gear</th><th>Appliers</th><th>Scan every</th><th>Use it when</th></tr></thead>
              <tbody>{GEARS.map((g) => <tr key={g[0]}>{g.map((c, i) => <td key={i}>{c}</td>)}</tr>)}</tbody></table>
          </section>
          <section>
            <h2>Shadow, your delegate</h2>
            <p>When a form stops on a question, Shadow can answer as you from your presets and Fact Bank. It never invents experience, never touches a CAPTCHA, and declines every EEO question.</p>
            <table><tbody>{SHADOW.map(([m, d]) => <tr key={m}><th>{m}</th><td>{d}</td></tr>)}</tbody></table>
          </section>
          <section>
            <h2>What "Your turn" means</h2>
            <p>A job waits on you when its form asked something nothing on file can answer truthfully, or when the site wants a human check (a CAPTCHA, an Ashby click). Answer it under Your turn &gt; Needs you and the job is retried; human checks are filled up to the check on the Desk, where you tick the box and press Submit.</p>
          </section>
          <section>
            <h2>Stop cleanly</h2>
            <ol>
              <li>Shift to N; wait until no batch is waiting or claimed (in-flight forms finish).</li>
              <li>Put the cap back to level 0 and Role Keywords off.</li>
              <li><code>docker compose -f deploy/bank.compose.yml stop</code> (volumes are kept).</li>
            </ol>
          </section>
          <section>
            <h2>FAQ</h2>
            <dl>{FAQ.map(([q, a]) => <div key={q}><dt>{q}</dt><dd>{a}</dd></div>)}</dl>
          </section>
        </article>
      ) : (
        <article className="dc-body" role="tabpanel" aria-label="Build on REGEN">
          <section>
            <h2>One entity: every part is a container</h2>
            <table><thead><tr><th>Part on screen</th><th>Container / source</th><th>What it shows</th></tr></thead>
              <tbody>{PARTS.map((p) => <tr key={p[0]}>{p.map((c, i) => <td key={i}>{c}</td>)}</tr>)}</tbody></table>
          </section>
          <section>
            <h2>Event contract</h2>
            <p>Pipeline events travel as <code>narration</code>, controls as <code>signal</code>, both on <code>/api/stream</code>. Nothing on screen moves without one.</p>
            <Code>{`narration kinds: discovered | gate.skip | resume | apply.start | submitted | parked |
                 shadow.answer | shadow.abstain | outcome | apply.fail
signal kinds:    gear | keywords | cap | targeting | shadow.mode | human.check |
                 problem | problem.clear | outreach.sent
fields:          job, company (null on the public site), by (engine|shadow|desk|you), detail`}</Code>
          </section>
          <section>
            <h2>API routes</h2>
            <table><tbody>{ROUTES.map(([r, d]) => <tr key={r}><th><code>{r}</code></th><td>{d}</td></tr>)}</tbody></table>
            <p>Writes need <code>REGEN_API_WRITE=1</code> on the API; a control changes on screen only when its signal comes back.</p>
          </section>
          <section>
            <h2>MCP: the engine has no model of its own</h2>
            <p>Your AI client plugs in over MCP and operates it at zero cost. Writes need <code>REGEN_MCP_WRITE=1</code>; the kill switch always works.</p>
            <Code>{MCP}</Code>
          </section>
          <section>
            <h2>Contributing</h2>
            <ul>
              <li><code>python -m pytest -q</code>, <code>npm run typecheck</code> and <code>python scripts/privacy_scan.py</code> clean before every change.</li>
              <li>Commit locally; the <code>reposync</code> container runs tests and the privacy scan, then opens the pull request.</li>
              <li>Coding rules: <code>docs/CODING_STANDARDS.md</code>. The revamp's build checklist: <code>docs/ALIVE_PLAN.md</code>.</li>
            </ul>
          </section>
        </article>
      )}
    </main>
  );
}
