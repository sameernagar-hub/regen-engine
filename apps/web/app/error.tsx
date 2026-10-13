"use client";
// Any page that throws while rendering lands here instead of Next's blank "This page couldn't load": the nav stays,
// the error is named, and one click retries the page (10-12: one malformed Fact Bank source blanked /facts).
import { useEffect } from "react";
import { Nav } from "./nav";

export default function PageError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => { console.error(error); }, [error]);
  return (
    <main className="page">
      <Nav />
      <section className="card" role="alert">
        <h2 className="sub">This view hit an error</h2>
        <p className="small dim">{error.message || "Unknown error"}{error.digest ? ` (${error.digest})` : ""}</p>
        <p><button onClick={reset}>Try again</button></p>
      </section>
    </main>
  );
}
