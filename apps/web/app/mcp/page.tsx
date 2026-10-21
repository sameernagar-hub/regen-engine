"use client";
// The cord (v1.1): the engine has no model and no API key of its own. Your AI client (Claude, Cursor, ChatGPT...)
// plugs into it over MCP and operates it at zero cost. Two sockets: regen-engine (stdio, started by your client on
// this machine) and regen-bank (HTTP, the bank's `mcp` container on 127.0.0.1:8790). Each tool lands on the part of
// the engine it drives; writes need REGEN_MCP_WRITE=1 on the server (the kill switch always works).
import { useEffect, useMemo, useState } from "react";
import { Nav } from "../nav";
import { get, poll } from "@/lib/types";

type Tool = { name: string; about: string; group: string; writes: boolean };
type Server = { name: string; transport: string; url?: string; up: boolean | null; ms?: number; error?: string };
type Data = { servers: Server[]; write_enabled: boolean; tools: Tool[]; groups: Record<string, number> };

const PARTS: Record<string, { label: string; tone: string; about: string }> = {
  discovery: { label: "Discovery", tone: "#6fb7ff", about: "new boards, job-list feeds, company probes, leads -> the discover stage" },
  fitgate: { label: "Fit gate", tone: "#ff7eb6", about: "blockers on a JD, title filters, trust gate, learned phrases" },
  memory: { label: "Memory + Fact Bank", tone: "#5ee6b5", about: "applications with proof, outcomes, knowledge graph, facts, trust gate" },
  pipeline: { label: "Pipeline", tone: "#9ad1ff", about: "select, build, apply; runs and email codes" },
  answers: { label: "Needs you", tone: "#ff9f43", about: "blocking questions, answers, inbox replies" },
  gearbox: { label: "Gearbox", tone: "#f2c14e", about: "gear, clutch, rejection feedback" },
  fleet: { label: "Fleet", tone: "#b18cff", about: "containers, scaling, kill switch, audit" },
  ledger: { label: "Ledger", tone: "#ff7eb6", about: "the Postgres copy of every event" },
  repo: { label: "Repo", tone: "#7d8796", about: "repo sync: feed and pull requests" },
};
const CONFIG = `{
  "mcpServers": {
    "regen-engine": { "command": "python", "args": ["-m", "engine", "mcp"] },
    "regen-bank":   { "type": "http", "url": "http://127.0.0.1:8790/mcp" }
  }
}`;

export default function Mcp() {
  const [d, setD] = useState<Data | null>(null);
  const [err, setErr] = useState("");
  const [open, setOpen] = useState<string | null>(null);
  useEffect(() => {
    const pull = () => get<Data>("/api/control/mcp").then(setD).catch((e) => setErr(e.message));
    pull();
    return poll(pull, 20000);
  }, []);
  const byGroup = useMemo(() => {
    const m: Record<string, Tool[]> = {};
    for (const t of d?.tools || []) (m[t.group] ||= []).push(t);
    return m;
  }, [d]);
  const bank = d?.servers.find((s) => s.name === "regen-bank");
  const groups = Object.keys(PARTS).filter((g) => byGroup[g]?.length || d?.groups[g]);
  const live = bank?.up;

  return (
    <main className={`page mcp${live ? " live" : ""}`}>
      <Nav />
      <header className="hero">
        <h1>MCP: the cord</h1>
        <p>The engine has no model and no API key. Your own AI client plugs into it over MCP and operates it: reads its
          memory, starts runs, shifts gears, answers what only you can. Zero model spend, everything on this machine.
          {d && <> {d.tools.length} tools; writes are <b>{d.write_enabled ? "on" : "off"}</b> on this server
          (<code>REGEN_MCP_WRITE=1</code>), the kill switch always works.</>}</p>
      </header>
      {err && <p className="note" role="status">MCP status unreachable: {err}</p>}

      <svg className="cord" viewBox="0 0 1000 220" role="img" aria-label={`AI client connected to the engine over MCP: bank server ${live ? "up" : "down"}`}>
        <defs><filter id="cglow" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="4" result="b" /><feMerge><feMergeNode in="b" /><feMergeNode in="SourceGraphic" /></feMerge></filter></defs>
        <g transform="translate(90 110)">
          <rect className="client" x={-70} y={-46} width={140} height={92} rx={14} />
          <text className="cl-label" y={-6}>your AI client</text>
          <text className="cl-sub" y={16}>Claude · Cursor · any MCP</text>
        </g>
        <path id="cordpath" className="wire" d="M 160 110 C 300 30, 420 190, 560 110" />
        <g transform="translate(580 110)">
          <rect className="plug" x={-20} y={-26} width={40} height={52} rx={8} />
          <rect className="pin" x={-14} y={-34} width={6} height={10} rx={2} /><rect className="pin" x={8} y={-34} width={6} height={10} rx={2} />
        </g>
        {live && [0, 1, 2].map((k) => (
          <circle key={k} className="spark" r={5}><animateMotion dur="2.4s" begin={`${k * 0.8}s`} repeatCount="indefinite" path="M 160 110 C 300 30, 420 190, 560 110" /></circle>))}
        <path className="bus" d="M 600 110 H 660" />
        {groups.map((g, i) => {
          const y = 22 + i * (176 / Math.max(1, groups.length - 1));
          return (
            <g key={g} className={`dest${open === g ? " on" : ""}`} style={{ ["--tone" as any]: PARTS[g].tone }}>
              <path className="branch" d={`M 660 110 C 700 110, 700 ${y}, 740 ${y}`} />
              <circle cx={740} cy={y} r={5} />
              <text x={752} y={y + 4}>{PARTS[g].label} · {byGroup[g]?.length ?? d?.groups[g] ?? 0}</text>
            </g>
          );
        })}
      </svg>

      <section className="sockets">
        {(d?.servers || []).map((s) => (
          <div key={s.name} className={`socket ${s.up === true ? "up" : s.up === false ? "down" : "client"}`}>
            <b>{s.name}</b><span>{s.transport}</span>
            <small>{s.up === true ? `up · ${s.ms} ms · ${s.url}` : s.up === false ? `down (${s.error || "no answer"})` : "starts when your AI client connects"}</small>
          </div>))}
        <details className="socket cfg"><summary>Plug it in (.mcp.json)</summary><pre>{CONFIG}</pre></details>
      </section>

      <section className="tools">
        {groups.map((g) => (
          <article key={g} className="tool-group" style={{ ["--tone" as any]: PARTS[g].tone }}
                   onMouseEnter={() => setOpen(g)} onMouseLeave={() => setOpen(null)} onFocus={() => setOpen(g)}>
            <h2>{PARTS[g].label}</h2>
            <p className="dim small">{PARTS[g].about}</p>
            <ul>
              {(byGroup[g] || []).map((t) => (
                <li key={t.name} title={t.about}>
                  <code>{t.name}</code>{t.writes && <span className="w">write</span>}
                  <span className="about">{t.about}</span>
                </li>))}
            </ul>
          </article>))}
      </section>
    </main>
  );
}
