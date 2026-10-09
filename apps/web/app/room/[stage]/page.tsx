"use client";
// One room, up close: everything this station has logged (live), with doors to the rooms it feeds and comes from.
import Link from "next/link";
import { use } from "react";
import { Nav } from "../../nav";
import { TONE, jobHref, useStations, when } from "@/lib/room";

export default function StationRoom({ params }: { params: Promise<{ stage: string }> }) {
  const { stage } = use(params);
  const { stations, beat, error } = useStations(50);
  const i = stations?.findIndex((s) => s.key === stage) ?? -1;
  const s = stations && i >= 0 ? stations[i] : null;
  const from = stations?.filter((x) => x.feeds.includes(stage)) || [];
  const to = stations?.filter((x) => s?.feeds.includes(x.key)) || [];
  return (
    <main className="page">
      <Nav />
      <p className="crumbs"><Link href="/room">Engine room</Link> / {s?.name || stage}</p>
      {error && <p className="err" role="status">API unreachable ({error}).</p>}
      {stations && !s && <p>No station called “{stage}”. <Link href="/room">Back to the room</Link></p>}
      {s && (
        <>
          <header className={`hero station${beat?.stage === stage ? " hot" : ""}`}>
            <span className="room-no">0{i + 1}</span>
            <h1>{s.name}</h1>
            <p>{s.about}</p>
            <dl className="stats">
              <div><dt>today</dt><dd>{s.today}</dd></div>
              <div><dt>all time</dt><dd>{s.total}</dd></div>
              {Object.entries(s.tones).map(([t, v]) => <div key={t}><dt style={{ color: TONE[t] }}>{t}</dt><dd>{v}</dd></div>)}
            </dl>
          </header>
          <nav className="doors" aria-label="Connected rooms">
            {from.map((x) => <Link key={x.key} href={`/room/${x.key}`}>← from {x.name}</Link>)}
            {to.map((x) => <Link key={x.key} href={`/room/${x.key}`}>to {x.name} →</Link>)}
          </nav>
          <section aria-live="polite" aria-label={`Latest at ${s.name}`}>
            <h2 className="sub">Live log</h2>
            <ul className="log">
              {s.recent.map((l) => (
                <li key={l.id} style={{ borderColor: TONE[l.tone] }}>
                  <time>{when(l.ts)}</time>
                  <Link href={jobHref(l.url)}>{l.text}</Link>
                </li>
              ))}
              {!s.recent.length && <li className="dim">Nothing yet.</li>}
            </ul>
          </section>
        </>
      )}
    </main>
  );
}
