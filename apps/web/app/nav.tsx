"use client";
// The dock (v0.16): the engine on the front page is the navigation now, so inner pages carry one way home and the
// name of the part you are in. Every page is reached from its part of the engine (app/page.tsx).
import Link from "next/link";
import { usePathname } from "next/navigation";
import { API_ORIGIN } from "../lib/types";

const HERE: [string, string][] = [
  ["/live", "Live"], ["/control", "Control"], ["/applications", "Applications"], ["/needs", "Needs you"], ["/reach", "Reach"], ["/bigtech", "Big tech"],
  ["/outreach", "Outreach"], ["/room", "Engine room"], ["/gearbox", "Gearbox"], ["/mcp", "MCP cord"], ["/job", "Job"], ["/evals", "Evals"], ["/facts", "Fact Bank"], ["/graph", "Memory graph"],
];

export function Nav() {
  const path = usePathname() || "/";
  const here = HERE.find(([h]) => path.startsWith(h))?.[1];
  return (
    <nav className="dock" aria-label="Engine">
      <Link href="/" className="home" aria-label="Back to the engine">
        <svg className="gear" viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="12" r="7" fill="none" stroke="#f2c14e" strokeWidth="2" strokeDasharray="3 2.5" />
          <circle cx="12" cy="12" r="3" fill="#f2c14e" />
        </svg>
        REGEN engine
      </Link>
      {here && <span className="here" aria-current="page">{here}</span>}
      {process.env.NEXT_PUBLIC_REGEN_MODE !== "public" && (  // the API's own page: request tracker + live ledger tables
        <a className="data" href={`${API_ORIGIN}/db`} title="Ledger database: live tables, filters, CSV/JSON download">Data ↗</a>)}
    </nav>
  );
}
