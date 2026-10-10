// Shown on the public site (NEXT_PUBLIC_REGEN_MODE=public) for pages that read private data: the control room,
// applications, needs-you and the Fact Bank only ever run against the API on the user's own machine.
import Link from "next/link";
import { Nav } from "./nav";

export function LocalOnly({ title, what }: { title: string; what: string }) {
  return (
    <main className="page">
      <Nav />
      <header className="hero">
        <h1>{title}</h1>
        <p>{what}</p>
      </header>
      <section className="card">
        <h2 className="sub">Runs on your machine</h2>
        <p>This page reads private data (resumes, answers, your Fact Bank), so it only works against the REGEN API on your own
          computer. The public site shows the anonymized live feed instead.</p>
        <pre className="logbox">{`git clone https://github.com/sameernagar-hub/regen-engine && cd regen-engine
REGEN_API_WRITE=1 python -m uvicorn apps.api.main:app --port 8787
npm --prefix apps/web run dev    # then open http://127.0.0.1:3000`}</pre>
        <p className="row small"><Link href="/">Watch the live feed →</Link><Link href="/room">Engine room →</Link><Link href="/graph">Memory graph →</Link></p>
      </section>
    </main>
  );
}
