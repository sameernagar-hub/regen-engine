"use client";
// The Claude cord + ignition (11-24): the line between the engine's agents and the operator's Claude session.
//   ignition = engine/ignite.py: one key turn sets gear (max 3), Role Keywords, the daily cap level and Shadow's mode,
//              and resumes every orchestrator agent. The page only drops a request; the supervisor's next tick
//              (<= 15 s) runs it as the engine user, so the API never writes engine state itself.
//   cord     = engine/cord.py: asks the agents sent (Shadow's abstained questions, fleet problems, dead letters) and
//              Claude's replies. Read-only here: Claude answers over MCP (cord_reply), the same truth policy as
//              answer_save, so a reply can never bypass the Fact Bank from a browser.
import { useEffect, useState } from "react";
import { Nav } from "../nav";
import { get, post, poll } from "@/lib/types";

type Ask = { id: string; t: number; ts?: string; from: string; kind: string; text: string; context?: { job?: string; question?: string } };
type Reply = { id: string; answer: string; by?: string; t: number; saved?: unknown };
type Ignition = { gear: string | null; gear_label?: string | null; keywords: boolean | null; cap_level: number | null; cap: number | null;
  cap_levels?: number[]; shadow: string | null; agents: Record<string, boolean>; last?: { t: number; by?: string; result?: any } | null;
  pending?: boolean };
type Cord = { ts: number; open: Ask[]; replies: Reply[]; ignition: Ignition };

const ago = (t?: number | null) => {
  if (!t) return "never";
  const s = Math.max(0, Date.now() / 1000 - t);
  return s < 90 ? `${Math.round(s)} s ago` : s < 5400 ? `${Math.round(s / 60)} min ago` : s < 172800 ? `${Math.round(s / 3600)} h ago` : `${Math.round(s / 86400)} d ago`;
};
const KIND: Record<string, string> = { question: "question", problem: "fleet problem", dead_letter: "dead letter", note: "note" };

export default function CordPage() {
  const [c, setC] = useState<Cord | null>(null);
  const [msg, setMsg] = useState("");
  const [busy, setBusy] = useState(false);
  const [gear, setGear] = useState("3");
  const [kw, setKw] = useState("on");
  const [cap, setCap] = useState(4);
  const [shadow, setShadow] = useState("autopilot");

  useEffect(() => {
    const pull = () => get<Cord>("/api/control/cord").then(setC).catch((e) => setMsg(`cord unreachable: ${e.message}`));
    pull();
    return poll(pull, 5000);
  }, []);

  const turn = async () => {
    if (busy) return;
    setBusy(true);
    setMsg("");
    try {
      await post("/api/control/ignite", { gear, keywords: kw, cap, shadow });
      setMsg(`Key turned: gear ${gear}, keywords ${kw}, cap level ${cap}, Shadow ${shadow}. The supervisor runs it on its next tick (≤ 15 s).`);
      setC(await get<Cord>("/api/control/cord"));
    } catch (e: any) {
      setMsg(`ignition: ${e.message}`);
    } finally {
      setBusy(false);
    }
  };

  const ig = c?.ignition;
  const names = Object.keys(ig?.agents || {});
  const resumed = names.filter((n) => !ig!.agents[n]).length;
  const asks = c?.open || [];
  return (
    <main className="page cd">
      <Nav />
      <header className="hero">
        <h1>Claude cord</h1>
        <p>The engine's agents can ask your Claude chat for help, and Claude answers back. When Shadow won't guess at a
          form question, when the supervisor sees a new fleet problem, or when a background task lands in the dead
          letter, an ask goes down this cord. Claude picks it up over MCP, answers from your Fact Bank, and the job
          retries. No API keys, no spend.</p>
        <p>Ignition is the key: one turn puts the engine in gear, sets Role Keywords, the daily cap and Shadow's mode,
          and wakes every background agent. It never goes above gear 3.</p>
      </header>
      {msg && <p className="note" role="status">{msg}</p>}

      <section className="cd-ign" aria-label="Ignition">
        <div className={`cd-key${ig?.pending ? " turning" : ig?.last ? " on" : ""}`} aria-hidden>
          <svg viewBox="0 0 120 120"><circle className="cd-bezel" cx="60" cy="60" r="52" /><circle className="cd-barrel" cx="60" cy="60" r="34" />
            <g className="cd-blade"><rect x="54" y="22" width="12" height="76" rx="4" /><circle cx="60" cy="60" r="9" /></g>
            <text x="60" y="16">ACC</text><text x="104" y="64">ON</text><text x="60" y="114">START</text></svg>
        </div>
        <dl className="cd-gauges">
          <div><dt>gear</dt><dd>{ig?.gear ?? "·"}</dd></div>
          <div><dt>Role Keywords</dt><dd>{ig?.keywords == null ? "·" : ig.keywords ? "on" : "off"}</dd></div>
          <div><dt>daily cap</dt><dd>{ig?.cap ?? "·"}<small>{ig?.cap_level != null ? ` level ${ig.cap_level}` : ""}</small></dd></div>
          <div><dt>Shadow</dt><dd>{ig?.shadow ?? "·"}</dd></div>
          <div><dt>agents resumed</dt><dd>{ig ? `${resumed}/${names.length}` : "·"}</dd></div>
          <div><dt>last ignition</dt><dd className="cd-sm">{ig?.pending ? "turning…" : ago(ig?.last?.t)}</dd></div>
        </dl>
        <form className="cd-form" onSubmit={(e) => { e.preventDefault(); turn(); }}>
          <label>gear<select value={gear} onChange={(e) => setGear(e.target.value)}>{["N", "1", "2", "3"].map((g) => <option key={g}>{g}</option>)}</select></label>
          <label>keywords<select value={kw} onChange={(e) => setKw(e.target.value)}><option>on</option><option>off</option></select></label>
          <label>cap<select value={cap} onChange={(e) => setCap(+e.target.value)}>
            {(ig?.cap_levels || [15, 25, 50, 100, 150]).map((n, i) => <option key={i} value={i}>{i} · {n}/day</option>)}</select></label>
          <label>Shadow<select value={shadow} onChange={(e) => setShadow(e.target.value)}>{["autopilot", "calls", "off"].map((m) => <option key={m}>{m}</option>)}</select></label>
          <button className="cd-btn" disabled={busy || !!ig?.pending}>Turn the key</button>
        </form>
        {names.length > 0 && <ul className="cd-agents">{names.map((n) => <li key={n} className={ig!.agents[n] ? "paused" : "on"}>{n.replace(/_/g, " ")}</li>)}</ul>}
      </section>

      <section className="cd-line">
        <h2>Open asks <span className="cd-count">{asks.length}</span></h2>
        {asks.length === 0 && <p className="dim small">{c ? "Nothing on the line. The agents are handling it." : "Listening…"}</p>}
        <ul className="cd-asks">
          {asks.map((a) => (
            <li key={a.id} className={`cd-ask ${a.kind}`}>
              <div className="cd-head"><span className={`cd-tag ${a.kind}`}>{KIND[a.kind] || a.kind}</span>
                <span className="cd-from">from {a.from}</span><span className="dim">{ago(a.t)}</span></div>
              {a.context?.job && <p className="cd-job">{a.context.job}</p>}
              <p className="cd-text">{a.text}</p>
              <code className="cd-id">{a.id}</code>
            </li>))}
        </ul>
        <p className="dim small">Claude answers with the MCP tool <code>cord_reply</code>; this page only shows the line.</p>
      </section>

      <section className="cd-line">
        <h2>Recent replies</h2>
        {(c?.replies || []).length === 0 && <p className="dim small">No replies yet.</p>}
        <ul className="cd-replies">
          {[...(c?.replies || [])].reverse().map((r) => (
            <li key={r.id + r.t}><div className="cd-head"><span className="cd-from">{r.by || "claude"}</span><span className="dim">{ago(r.t)}</span>
              {r.saved ? <span className="cd-tag saved">saved as Shadow</span> : null}</div>
              <p className="cd-text">{r.answer}</p><code className="cd-id">{r.id}</code></li>))}
        </ul>
      </section>
    </main>
  );
}
