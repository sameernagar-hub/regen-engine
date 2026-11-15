"use client";
// Test drive: the whole engine at a glance, with your resume behind the wheel. The hero is the engine on a dyno: the
// radial engine turns a belt that carries postings through Discover, the fit gate and the ranker; most drop at the
// gate, the few that fit reach "your 10". It idles until you run, then revs. The six stations below are the engine's
// real architecture in run order; a drive runs the first four on live public boards (POST /api/public/try, the same
// rules as `python -m engine try`) and shows what the last two do in a full run, without sending anything.
// Nothing is stored. Reduced motion: every animation stops, the numbers still land.
import { useEffect, useRef, useState } from "react";
import { Nav } from "../nav";
import { useTestDrive, type TryOut } from "../try-box";

const SAMPLE = `Jane Doe, Software Engineer (sample resume)
4+ years building backend and full-stack products.
Skills: Python, FastAPI, PostgreSQL, SQL, React, TypeScript, Next.js, Docker, Kubernetes, AWS, Kafka, Redis, CI/CD
Software Engineer II | Example Co | 2022 - Present
- Built REST APIs and microservices in Python serving 2M requests a day; cut p95 latency 40% with Redis caching
- Shipped a full-stack Next.js dashboard with React and TypeScript; end-to-end tests with Playwright in GitHub Actions
Software Engineer | Sample Labs | 2021 - 2022
- Ran event pipelines on Kafka and PostgreSQL; deployed on AWS with Docker and Kubernetes`;

const DISCLAIMER = "For illustration only. Matches come from automated keyword scoring and can be wrong or out of date; check every posting yourself before you apply. REGEN is not responsible for decisions made from these results.";

type Station = { key: string; name: string; href: string; tone: string; does: string; drive: (o: TryOut | null) => string; dry?: boolean };
const filtered = (o: TryOut) => Object.values(o.blocked).reduce((a, b) => a + b, 0);
const STATIONS: Station[] = [
  { key: "facts", name: "Fact Bank", href: "/facts", tone: "#f2c14e",
    does: "Everything a resume is allowed to say about you, each item backed by proof. The engine never writes anything that isn't in here.",
    drive: (o) => o ? `reads as ${o.profile.lanes[0]}, ${o.profile.years} yrs, ${o.profile.keywords.length} keywords` : "reads your resume the way a recruiter would" },
  { key: "discover", name: "Discover", href: "/room/listen", tone: "#6fb7ff",
    does: "Checks thousands of company job boards and six big-tech career sites on a schedule, so new roles are seen within hours of posting.",
    drive: (o) => o ? `${o.boards} boards, ${o.postings.toLocaleString()} open postings` : "pulls every open posting from 40 boards" },
  { key: "gate", name: "Fit gate", href: "/room", tone: "#ff9f43",
    does: "Throws out roles that don't fit the resume: a different kind of role, the wrong level, outside the US, or older than a month.",
    drive: (o) => o ? `${o.passing} fit you · ${filtered(o).toLocaleString()} filtered` : "keeps only roles your resume fits" },
  { key: "compose", name: "Compose", href: "/applications", tone: "#5ee6b5",
    does: "Builds a resume for each posting from the Fact Bank, leading with what that job asks for. Here it scores your match instead.",
    drive: (o) => o ? `read ${o.checked} job descriptions, scored ATS match` : "reads each job description like an ATS" },
  { key: "apply", name: "Apply", href: "/control", tone: "#ff7eb6", dry: true,
    does: "Fills in each application in a real browser and saves a receipt. Questions it can't answer from your facts wait for you; so do CAPTCHAs.",
    drive: (o) => o ? "not run: the test drive never submits" : "not run on a test drive" },
  { key: "inbox", name: "Inbox", href: "/gearbox", tone: "#a78bfa", dry: true,
    does: "Reads the replies, sorts interviews from rejections, and uses each rejection to tighten the filter.",
    drive: (o) => o ? "not run: nothing was sent" : "not run on a test drive" },
];
const PARTS: [string, string, string, string][] = [
  ["Engine room", "/room", "Every job end to end through the stations.", "#6fb7ff"],
  ["Gearbox", "/gearbox", "Speed in gears; the governor scales the appliers from memory, CPU and timeouts.", "#5ee6b5"],
  ["Shadow", "/shadow", "Your AI delegate: answers forms as you, and holds back when it isn't sure.", "#a78bfa"],
  ["Fact Bank", "/facts", "Every claim a resume may make, and which resumes used it.", "#f2c14e"],
  ["Needs you", "/needs", "Questions only you can answer, grouped so one answer clears many jobs.", "#ff9f43"],
  ["MCP cord", "/mcp", "Plug your AI client in and operate the engine at zero model cost.", "#ff7eb6"],
];
const f = (n: number) => Math.round(n * 100) / 100;  // same digits on the server and in the browser (hydration)
const LANE_TONE: Record<string, string> = { software: "#6fb7ff", "ai / ml": "#a78bfa", data: "#5ee6b5", "devops / sre": "#ff9f43", security: "#ff5a5f",
  product: "#f2c14e", design: "#ff7eb6", program: "#f0b64c", solutions: "#7dd3fc" };

/** A number that counts up to its value when it changes (instant with reduced motion). */
function Count({ to }: { to: number }) {
  const [v, setV] = useState(0);
  const from = useRef(0);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) { setV(to); from.current = to; return; }
    const a = from.current, t0 = performance.now(); let raf = 0;
    const step = (t: number) => { const k = Math.min(1, (t - t0) / 1100); setV(Math.round(a + (to - a) * (1 - (1 - k) ** 3))); if (k < 1) raf = requestAnimationFrame(step); else from.current = to; };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [to]);
  return <>{v.toLocaleString()}</>;
}

/** The engine on a dyno: radial engine -> belt -> postings through Discover, the gate and the ranker -> your 10. */
function Dyno({ mode }: { mode: "idle" | "rev" | "cruise" }) {
  const CX = 112, CY = 150;
  const cyl = Array.from({ length: 8 }, (_, i) => -90 + i * 45);
  const cards = Array.from({ length: 12 }, (_, i) => ({ i, pass: i % 4 === 1, tone: ["#6fb7ff", "#a78bfa", "#5ee6b5", "#ff7eb6", "#7dd3fc", "#f0b64c"][i % 6] }));
  return (
    <svg className={`td-dyno ${mode}`} viewBox="0 0 640 300" role="img"
         aria-label={mode === "rev" ? "The engine running your resume through the stations" : "The engine idling, ready for a resume"}>
      <defs>
        <radialGradient id="tdCase" cx=".45" cy=".4" r=".7"><stop offset="0" stopColor="#2b3442" /><stop offset=".7" stopColor="#141a23" /><stop offset="1" stopColor="#0b0f15" /></radialGradient>
        <linearGradient id="tdBarrel" x1="0" x2="1"><stop offset="0" stopColor="#1a212c" /><stop offset=".45" stopColor="#3a4556" /><stop offset="1" stopColor="#141a22" /></linearGradient>
        <linearGradient id="tdTrack" x1="0" x2="1"><stop offset="0" stopColor="#6fb7ff" /><stop offset=".5" stopColor="#ff9f43" /><stop offset="1" stopColor="#f2c14e" /></linearGradient>
        <filter id="tdGlow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="4" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter>
      </defs>
      {/* the radial engine */}
      <g className="td-eng">
        {cyl.map((a, i) => (
          <g key={a} transform={`rotate(${a + 90} ${CX} ${CY})`}>
            <rect className="td-barrel" x={CX - 13} y={CY - 98} width={26} height={60} rx={4} />
            {[0, 1, 2, 3].map((f) => <rect key={f} className="td-fin" x={CX - 18} y={CY - 92 + f * 13} width={36} height={4} rx={2} />)}
            <g className="td-piston" style={{ animationDelay: `calc(var(--beat) * ${-i / 8})` }}><rect x={CX - 9} y={CY - 84} width={18} height={12} rx={3} /></g>
            <circle className="td-spark" cx={CX} cy={CY - 104} r={4} style={{ animationDelay: `calc(var(--beat) * ${-i / 8})` }} />
          </g>
        ))}
        <circle className="td-case" cx={CX} cy={CY} r={40} />
        <g className="td-crank" style={{ transformOrigin: `${CX}px ${CY}px` }}>
          {Array.from({ length: 16 }, (_, t) => { const r = (t * 22.5 * Math.PI) / 180; return <line key={t} className="td-tooth" x1={f(CX + Math.cos(r) * 28)} y1={f(CY + Math.sin(r) * 28)} x2={f(CX + Math.cos(r) * 35)} y2={f(CY + Math.sin(r) * 35)} />; })}
          <circle className="td-pin" cx={CX + 14} cy={CY} r={6} />
        </g>
        <circle className="td-hub" cx={CX} cy={CY} r={18} />
        <text className="td-hubtext" x={CX} y={CY + 4}>REGEN</text>
      </g>
      {/* belt from the crank to the conveyor drum */}
      <path className="td-belt" d={`M ${CX + 20} ${CY - 18} L 214 222 M ${CX + 20} ${CY + 18} L 214 258`} />
      <circle className="td-drum" cx={222} cy={240} r={18} />
      <g className="td-drum-spokes" style={{ transformOrigin: "222px 240px" }}>{[0, 60, 120].map((r) => <line key={r} x1={222} y1={226} x2={222} y2={254} transform={`rotate(${r} 222 240)`} />)}</g>
      {/* conveyor with the stations */}
      <line className="td-track" x1={222} y1={222} x2={612} y2={222} />
      <line className="td-track-flow" x1={222} y1={222} x2={612} y2={222} />
      {[["Discover", 300, "#6fb7ff"], ["Fit gate", 420, "#ff9f43"], ["Rank", 520, "#5ee6b5"]].map(([n, x, c]) => (
        <g key={n as string} className="td-gate-arch" style={{ ["--c" as any]: c }}>
          <path d={`M ${(x as number) - 22} 224 L ${(x as number) - 22} 172 Q ${x} 156 ${(x as number) + 22} 172 L ${(x as number) + 22} 224`} />
          <circle className="td-lamp" cx={x as number} cy={166} r={4} />
          <text x={x as number} y={150}>{n}</text>
        </g>
      ))}
      <g className="td-tray"><rect x={572} y={226} width={60} height={34} rx={6} /><text x={602} y={248}>your 10</text></g>
      {cards.map((c) => (
        <rect key={c.i} className={`td-card ${c.pass ? "pass" : "drop"}`} x={230} y={206} width={22} height={14} rx={3}
              style={{ ["--tone" as any]: c.tone, animationDelay: `calc(var(--lap) * ${-c.i / 12})` }} />
      ))}
    </svg>
  );
}

function Tach({ mode }: { mode: "idle" | "rev" | "cruise" }) {
  // one centre (100, 100) for the arc, the ticks and the needle; the dial sweeps 240° (-120° to +120° from straight up)
  const C = 100, R = 80, pt = (deg: number, r: number) => [f(C + Math.sin((deg * Math.PI) / 180) * r), f(C - Math.cos((deg * Math.PI) / 180) * r)];
  const [sx, sy] = pt(-120, R), [ex, ey] = pt(120, R);
  const dial = `M ${sx} ${sy} A ${R} ${R} 0 1 1 ${ex} ${ey}`;
  const ticks = Array.from({ length: 11 }, (_, i) => -120 + i * 24);
  return (
    <svg className={`td-tach ${mode}`} viewBox="0 0 200 172" role="img" aria-label={`Tachometer: ${mode}`}>
      <defs><linearGradient id="tdRpm" x1="0" x2="1"><stop offset="0" stopColor="#3ddc84" /><stop offset=".55" stopColor="#f2c14e" /><stop offset="1" stopColor="#ff5a5f" /></linearGradient></defs>
      <path className="arc" d={dial} />
      <path className="arc-live" d={dial} pathLength={100} />
      {ticks.map((a) => { const [x1, y1] = pt(a, 60), [x2, y2] = pt(a, 68); return <line key={a} className="tick" x1={x1} y1={y1} x2={x2} y2={y2} />; })}
      <g className="needle"><line x1={C} y1={C} x2={C} y2={34} /><circle cx={C} cy={C} r="8" /></g>
      <text x={C} y="164">{mode === "rev" ? "RUNNING" : mode === "cruise" ? "DONE" : "IDLE"}</text>
    </svg>
  );
}

function Ring({ pct }: { pct: number }) {
  const tone = pct >= 70 ? "#3ddc84" : pct >= 50 ? "#f2c14e" : "#ff9f43";
  return <span className="td-ring" style={{ ["--p" as any]: pct, ["--tone" as any]: tone }} aria-label={`ATS match ${pct}%`}><b>{pct}<small>%</small></b></span>;
}

export default function TestDrive() {
  const t = useTestDrive();
  const [stage, setStage] = useState(-1);  // station being driven; 6 = drive complete
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const clear = () => { timers.current.forEach(clearTimeout); timers.current = []; };
  useEffect(() => clear, []);

  const drive = async (override?: string) => {
    clear(); setStage(0);
    timers.current.push(setTimeout(() => setStage(1), 600));
    timers.current.push(setTimeout(() => setStage(2), 4500));
    const o = await t.go(override);
    clear();
    if (!o) { setStage(-1); return; }
    [2, 3, 4, 5, 6].forEach((s, i) => timers.current.push(setTimeout(() => setStage(s), 280 * (i + 1))));
    timers.current.push(setTimeout(() => document.getElementById("td-results")?.scrollIntoView({ behavior: "smooth", block: "start" }), 280 * 6 + 200));
  };
  const sample = () => { t.setText(SAMPLE); drive(SAMPLE); };
  const mode = t.busy || (stage >= 0 && stage < 6) ? "rev" : stage === 6 ? "cruise" : "idle";
  const o = t.out;
  const blocked = o ? Object.entries(o.blocked) : [];
  const maxBlocked = Math.max(1, ...blocked.map(([, n]) => n));

  return (
    <main className={`page td td-${mode}`} id="main">
      <Nav />
      <div className="td-aurora" aria-hidden />
      <header className="td-hero">
        <div className="td-pitch">
          <p className="eyebrow"><span className="brand">Test drive</span><span className="try-live" aria-hidden />live on public boards</p>
          <h1>See which open roles the engine would pick <em>for you.</em></h1>
          <p>Paste your resume. The engine works out what kind of role you do and at what level, pulls every open
            posting from <b>40 public company boards</b>, reads the job descriptions of the ones that fit, and ranks
            them the way an applicant tracking system would: <b>keywords the job asks for that your resume has</b>.</p>
          <p>About 15 seconds. No account, nothing is applied to, and your text isn&apos;t saved.</p>
          <a className="td-start" href="#td-seat-h" onClick={(e) => { e.preventDefault(); document.getElementById("td-text")?.focus(); document.getElementById("td-seat-h")?.scrollIntoView({ behavior: "smooth", block: "start" }); }}>
            Start the test drive <span aria-hidden>↓</span></a>
        </div>
        <div className="td-rig">
          <Dyno mode={mode} />
          <div className="td-cluster" aria-label="Instrument cluster">
            <Tach mode={mode} />
            <div className="td-gauges">
              <div style={{ ["--tone" as any]: "#6fb7ff" }}><span>Postings scanned</span><b><Count to={stage >= 2 && o ? o.postings : 0} /></b></div>
              <div style={{ ["--tone" as any]: "#ff9f43" }}><span>Fit your profile</span><b><Count to={stage >= 3 && o ? o.passing : 0} /></b></div>
              <div style={{ ["--tone" as any]: "#5ee6b5" }}><span>JDs read</span><b><Count to={stage >= 4 && o ? o.checked : 0} /></b></div>
              <div style={{ ["--tone" as any]: "#f2c14e" }}><span>Best match</span><b><Count to={stage >= 6 && o?.top[0] ? o.top[0].match : 0} />%</b></div>
            </div>
          </div>
        </div>
      </header>

      <section className="td-seat" aria-labelledby="td-seat-h">
        <h2 id="td-seat-h"><span className="n" style={{ ["--tone" as any]: "#f2c14e" }}>1</span>Paste your resume</h2>
        <label htmlFor="td-text">Plain text is fine; copy it straight out of your PDF or doc. It&apos;s used for this one run and then dropped.</label>
        <textarea id="td-text" rows={7} value={t.text} onChange={(e) => t.setText(e.target.value)} maxLength={50000}
                  placeholder="Paste the text of your resume here" />
        <div className="td-actions">
          <button type="button" className="td-ignite" onClick={() => drive()} disabled={t.busy || !t.text.trim()}>
            <span className="key" aria-hidden />{t.busy ? "Running…" : "Run the test drive"}</button>
          <button type="button" className="td-sample" onClick={sample} disabled={t.busy}>Try it with a sample resume</button>
        </div>
        {t.err && <p className="alive-error" role="status">{t.err}</p>}
        <p className="td-fine">{DISCLAIMER}</p>
      </section>

      <section className="td-route" aria-labelledby="td-route-h">
        <h2 id="td-route-h"><span className="n" style={{ ["--tone" as any]: "#6fb7ff" }}>2</span>What happens, step by step</h2>
        <p className="td-sub">These are the engine&apos;s six stations, in the order every job moves through them. The test drive
          runs the first four on live data. The last two only run when you start the engine for real, so here they
          show what they would do.</p>
        <ol className="td-stations">
          {STATIONS.map((s, i) => {
            const state = stage > i || stage === 6 ? "done" : stage === i ? "on" : "";
            return (
              <li key={s.key} className={`${state}${s.dry ? " dry" : ""}`} style={{ ["--tone" as any]: s.tone, ["--i" as any]: i }}>
                <span className="td-plug" aria-hidden />
                <h3><small>{String(i + 1).padStart(2, "0")}</small> {s.name}</h3>
                <p className="does">{s.does}</p>
                <p className="now" aria-live="polite">{s.drive(stage > i || stage === 6 ? o : null)}</p>
                <a href={s.href}>Open {s.name} →</a>
              </li>
            );
          })}
        </ol>
      </section>

      {o && stage === 6 && (
        <section className="td-results" id="td-results" aria-labelledby="td-res-h">
          <h2 id="td-res-h"><span className="n" style={{ ["--tone" as any]: "#5ee6b5" }}>3</span>Your results</h2>
          <div className="td-profile">
            <div className="who">
              <span>Your resume reads as</span>
              <b>{o.profile.lanes.map((l) => <i key={l} style={{ ["--tone" as any]: LANE_TONE[l] || "#6fb7ff" }}>{l}</i>)}</b>
              <small>{o.profile.years} yrs{o.profile.senior ? " · senior" : ""}{o.profile.student ? " · student" : ""} · {o.profile.keywords.length} keywords found</small>
            </div>
            <p className="kw">{o.profile.keywords.slice(0, 28).map((k) => <span key={k} className="try-chip">{k}</span>)}
              {o.profile.keywords.length > 28 && <span className="more">+{o.profile.keywords.length - 28} more</span>}</p>
          </div>
          <div className="td-res-grid">
            <div>
              <h3>Your 10 best matches</h3>
              {o.top.length ? (
                <ol className="td-roles">{o.top.map((j, i) => (
                  <li key={j.url} style={{ ["--i" as any]: i }}>
                    <Ring pct={j.match} />
                    <div className="body">
                      <a href={j.url} target="_blank" rel="noreferrer noopener">{j.title}</a>
                      <span className="co">{j.company}{j.location ? ` · ${j.location}` : ""}</span>
                      <p className="chips">{j.matched.slice(0, 8).map((k) => <span key={k} className="ok">{k}</span>)}
                        {j.missing.slice(0, 4).map((k) => <span key={k} className="miss">{k}</span>)}</p>
                      <small>{j.reason.replace(/^ATS match \d+% \((\d+ of \d+ JD keywords)\)(: [^;]*)?(; missing [^;]*)?/, "$1")}</small>
                    </div>
                  </li>))}
                </ol>)
                : <p className="td-sub">Nothing in this sample of boards fits this resume right now. Try again later: postings change hourly.</p>}
              <p className="td-legend"><span className="ok">has it</span><span className="miss">the job asks, resume doesn&apos;t show</span></p>
            </div>
            <aside className="td-gate">
              <h3>Why the rest were filtered out</h3>
              <p className="td-sub">{filtered(o).toLocaleString()} of {o.postings.toLocaleString()} postings didn&apos;t fit. In a real run none of these get an application.</p>
              <ul>{blocked.map(([r, n], i) => (
                <li key={r} style={{ ["--i" as any]: i }}><span>{r}</span><b>{n.toLocaleString()}</b><i style={{ width: `${Math.max(2, (n / maxBlocked) * 100)}%` }} /></li>))}
              </ul>
            </aside>
          </div>
          <p className="td-fine">{DISCLAIMER}</p>
        </section>
      )}

      <section className="td-glance" aria-labelledby="td-glance-h">
        <h2 id="td-glance-h"><span className="n" style={{ ["--tone" as any]: "#a78bfa" }}>4</span>The rest of the engine</h2>
        <p className="td-sub">Each part below is its own page in this demo (the data behind them is synthetic).</p>
        <div className="td-parts">
          {PARTS.map(([name, href, about, tone], i) => <a key={href} href={href} style={{ ["--i" as any]: i, ["--tone" as any]: tone }}><b>{name}</b><span>{about}</span></a>)}
        </div>
      </section>

      <section className="td-own" aria-labelledby="td-own-h">
        <h2 id="td-own-h">Run it on your own machine</h2>
        <p>The same check runs locally with plain Python, no packages needed:</p>
        <pre className="dc-code"><code>{"git clone https://github.com/sameernagar-hub/regen-engine && cd regen-engine\npython -m engine try resume.txt     # a PDF needs: pip install pypdf"}</code></pre>
        <p>Setting up a full run (Docker, your own Fact Bank, real applications with a receipt for each) is covered in the <a href="/docs">Docs</a>.</p>
      </section>
    </main>
  );
}
