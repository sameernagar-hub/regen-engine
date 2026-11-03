"use client";
// Desk (11-02): every job waiting on a human check, next to the desk browser itself. The desk's VNC password is new on
// every start (workspace/.desk_pass); the API puts it into the noVNC link (/api/reach/desk -> open), so the embedded
// desk connects on its own and you never type it. The password stays: without it any web page could drive the desk
// browser over ws://127.0.0.1:6080. Two kinds of rows: forms already filled in the desk (tick hCaptcha + Submit there)
// and CAPTCHA / human-click pages on the employer's site (open, finish, come back). The desk never sees your Submit,
// so "Mark submitted" records it (POST /api/human/mark) and the job leaves the list.
import { useEffect, useMemo, useState } from "react";
import { Nav } from "../nav";
import { get, post, poll, type HumanItem } from "@/lib/types";

type Desk = { desk: { up: boolean; state: string; queued: number; last: string } | null; open: string };

const IN_DESK = /filled in the desk|in the desk \(/i;
const HUMAN = /captcha|human click|human check|no confirmation seen/i;

export default function DeskPage() {
  return <DeskView />;
}

function DeskView() {
  const [items, setItems] = useState<HumanItem[] | null>(null);
  const [desk, setDesk] = useState<Desk | null>(null);
  const [gone, setGone] = useState<Record<string, string>>({});
  const [msg, setMsg] = useState("");

  const pull = () => get<HumanItem[]>("/api/human").then(setItems).catch((e) => setMsg(e.message));
  const pullDesk = () => get<Desk>("/api/reach/desk").then(setDesk).catch(() => setDesk(null));
  useEffect(() => { pull(); pullDesk(); const a = poll(pull, 20000), b = poll(pullDesk, 15000); return () => { a(); b(); }; }, []);

  const [inDesk, onSite] = useMemo(() => {
    const live = (items || []).filter((i) => i.url && !gone[i.url]);
    return [live.filter((i) => IN_DESK.test(i.text + " " + (i.missing || []).join(" "))),
            live.filter((i) => !IN_DESK.test(i.text + " " + (i.missing || []).join(" ")) && HUMAN.test(i.text + " " + (i.missing || []).join(" ")))];
  }, [items, gone]);

  const mark = async (it: HumanItem, m: "submitted" | "skipped") => {
    try {
      await post("/api/human/mark", { url: it.url, mark: m });
      setGone((g) => ({ ...g, [it.url as string]: m }));
      setMsg(`${it.job}: marked ${m}.`);
    } catch (e: any) { setMsg(e.message); }
  };

  const row = (it: HumanItem, where: "desk" | "site") => (
    <li key={it.url} className="card need">
      <div className="need-head"><b>{it.job}</b></div>
      <p className="dim small">{where === "desk" ? "Filled in the desk: tick the hCaptcha box, press Submit." : it.text}</p>
      <p className="row small">
        {where === "site" && <a className="btn" href={it.url as string} target="_blank" rel="noreferrer noopener">Open posting ↗</a>}
        <button className="btn gold" onClick={() => mark(it, "submitted")}>Mark submitted</button>
        <button className="btn" onClick={() => mark(it, "skipped")}>Skip</button>
      </p>
    </li>
  );

  return (
    <main className="page">
      <Nav />
      <header className="hero">
        <h1>Desk</h1>
        <p>{items ? `${inDesk.length} filled in the desk, ${onSite.length} waiting on a human check on the employer's page.` : "Loading…"} The desk below connects by itself; nothing asks for a password.</p>
      </header>
      {msg && <p className="note" role="status">{msg}</p>}
      <section className="card" aria-label="Desk browser">
        <p className="dim small">Desk: {desk?.desk ? `${desk.desk.up ? desk.desk.state : "down"}${desk.desk.queued ? `, ${desk.desk.queued} queued` : ""}` : "not reachable"}
          {desk?.open && <> · <a href={desk.open} target="_blank" rel="noreferrer">Open full screen ↗</a></>}</p>
        {desk?.open ? <iframe title="Desk browser" src={desk.open} style={{ width: "100%", height: "72vh", border: 0, borderRadius: 8, background: "#000" }} />
                    : <p className="dim">The desk is not up.</p>}
      </section>
      <h2>In the desk</h2>
      <ol className="needs">{inDesk.map((it) => row(it, "desk"))}</ol>
      {items && !inDesk.length && <p className="dim">Nothing filled in the desk right now.</p>}
      <h2>On the employer's page</h2>
      <ol className="needs">{onSite.map((it) => row(it, "site"))}</ol>
      {items && !onSite.length && <p className="dim">No CAPTCHAs or human clicks waiting.</p>}
    </main>
  );
}
