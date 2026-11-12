"use client";
// The four rooms (ALIVE Phase 5, docs/ALIVE_PLAN.md §5): the 15 page pills become Drive · Your turn · Results ·
// Garage. Drive is the engine itself (it closes any drawer); the other three open a drawer over the engine, which keeps
// running behind it. Each drawer shows the existing pages as tabs, rendered as they are (loaded only when picked), and
// every page keeps its own route. Esc closes; focus stays in the drawer while it is open and returns to the room button.
import dynamic from "next/dynamic";
import { useEffect, useRef, useState, type ComponentType } from "react";

const load = (f: () => Promise<{ default: ComponentType }>) =>
  dynamic(f, { ssr: false, loading: () => <p className="al-room-loading">Loading…</p> });

type Tab = { key: string; label: string; href: string; Page: ComponentType };
const ROOMS: { key: string; label: string; about: string; tabs: Tab[] }[] = [
  { key: "turn", label: "Your turn", about: "What waits on you: parked questions and the desk's human checks.", tabs: [
    { key: "needs", label: "Needs you", href: "/needs", Page: load(() => import("../needs/page")) },
    { key: "desk", label: "Desk", href: "/desk", Page: load(() => import("../desk/page")) },
  ] },
  { key: "results", label: "Results", about: "What was sent, the account portals you finish, and notes to people.", tabs: [
    { key: "applications", label: "Applications", href: "/applications", Page: load(() => import("../applications/page")) },
    { key: "reach", label: "Reach", href: "/reach", Page: load(() => import("../reach/page")) },
    { key: "outreach", label: "Outreach", href: "/outreach", Page: load(() => import("../outreach/page")) },
  ] },
  { key: "garage", label: "Garage", about: "How the engine is set up, measured and maintained.", tabs: [
    { key: "gearbox", label: "Gearbox", href: "/gearbox", Page: load(() => import("../gearbox/page")) },
    { key: "facts", label: "Fact Bank", href: "/facts", Page: load(() => import("../facts/page")) },
    { key: "graph", label: "Memory graph", href: "/graph", Page: load(() => import("../graph/page")) },
    { key: "shadow", label: "Shadow brain", href: "/shadow", Page: load(() => import("../shadow/page")) },
    { key: "evals", label: "Evals", href: "/evals", Page: load(() => import("../evals/page")) },
    { key: "oilchange", label: "Maintenance", href: "/oilchange", Page: load(() => import("../oilchange/page")) },
    { key: "mcp", label: "MCP cord", href: "/mcp", Page: load(() => import("../mcp/page")) },
  ] },
];

export function Rooms() {
  const [room, setRoom] = useState<string | null>(null);
  const [tab, setTab] = useState<Record<string, string>>({});
  const opener = useRef<HTMLButtonElement | null>(null);
  const box = useRef<HTMLDivElement>(null);
  const r = ROOMS.find((x) => x.key === room) ?? null;
  const t = r ? r.tabs.find((x) => x.key === tab[r.key]) ?? r.tabs[0] : null;

  const close = () => { setRoom(null); opener.current?.focus(); };
  useEffect(() => {
    if (!room) return;
    box.current?.querySelector<HTMLElement>("[role=tab][aria-selected=true]")?.focus();
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.preventDefault(); close(); return; }
      if (e.key !== "Tab" || !box.current) return;
      const f = [...box.current.querySelectorAll<HTMLElement>("a[href], button:not([disabled]), input, select, textarea, iframe, [tabindex]:not([tabindex='-1'])")]
        .filter((el) => el.offsetParent !== null);
      if (!f.length) return;
      const first = f[0], last = f[f.length - 1];
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
    };
    document.addEventListener("keydown", key);
    document.body.style.overflow = "hidden";
    return () => { document.removeEventListener("keydown", key); document.body.style.overflow = ""; };
  }, [room]);  // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <>
      <nav className="al-rooms" aria-label="Rooms">
        <button type="button" aria-pressed={!room} onClick={() => { setRoom(null); document.querySelector(".alive")?.scrollIntoView({ behavior: "smooth" }); }}>Drive</button>
        {ROOMS.map((x) => (
          <button key={x.key} type="button" aria-pressed={room === x.key} aria-haspopup="dialog"
                  onClick={(e) => { opener.current = e.currentTarget; setRoom(x.key); }}>{x.label}</button>
        ))}
      </nav>
      {r && t && (
        <div className="al-room-back" onClick={close}>
          <div ref={box} className="al-room" role="dialog" aria-modal="true" aria-label={r.label} onClick={(e) => e.stopPropagation()}>
            <header>
              <div><h2>{r.label}</h2><p>{r.about}</p></div>
              <button type="button" className="al-drawer-x" onClick={close} aria-label={`Close ${r.label}`}>×</button>
            </header>
            <div className="al-room-tabs" role="tablist" aria-label={`${r.label} pages`}>
              {r.tabs.map((x) => (
                <button key={x.key} type="button" role="tab" aria-selected={x.key === t.key} tabIndex={x.key === t.key ? 0 : -1}
                        onClick={() => setTab((s) => ({ ...s, [r.key]: x.key }))}>{x.label}</button>
              ))}
              <a className="al-room-own" href={t.href}>Open {t.label} on its own page ↗</a>
            </div>
            <div className="al-room-page" role="tabpanel" aria-label={t.label}>
              <t.Page />
            </div>
          </div>
        </div>
      )}
    </>
  );
}
