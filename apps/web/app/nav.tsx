"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Live" },
  { href: "/control", label: "Control" },
  { href: "/applications", label: "Applications" },
  { href: "/room", label: "Engine room" },
  { href: "/facts", label: "Fact Bank" },
  { href: "/graph", label: "Memory graph" },
];

export function Nav() {
  const path = usePathname() || "/";
  return (
    <nav className="topnav" aria-label="Engine views">
      <Link href="/" className="brand">REGEN</Link>
      <ul>
        {LINKS.map((l) => {
          const on = l.href === "/" ? path === "/" : path.startsWith(l.href);
          return <li key={l.href}><Link href={l.href} aria-current={on ? "page" : undefined}>{l.label}</Link></li>;
        })}
      </ul>
    </nav>
  );
}
