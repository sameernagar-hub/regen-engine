// Types come from the API's OpenAPI schema (npm run gen:api), so the page and the API can't drift apart.
import type { components } from "./api";
import { proxyFile, proxyGet, proxyPost } from "./proxy";

export type Snapshot = components["schemas"]["Snapshot"];
export type Application = components["schemas"]["Application"];
export type Narration = components["schemas"]["Narration"];
export type HumanItem = components["schemas"]["HumanItem"];
export type AnswerIn = components["schemas"]["AnswerIn"];

export const STAGES = [
  { key: "listen", verb: "listening" },
  { key: "judge", verb: "judging" },
  { key: "write", verb: "writing" },
  { key: "apply", verb: "applying" },
  { key: "hear", verb: "hearing back" },
] as const;

// The browser talks to the API container directly (no proxy hop through the web server). /api/public is the web
// app's own route (the Render site); everything else lives on the API at NEXT_PUBLIC_REGEN_API.
export const API_ORIGIN = process.env.NEXT_PUBLIC_REGEN_API || "http://127.0.0.1:8787";
// Public mode (the Render site): files and data come from the proxy dataset (lib/proxy.ts), the live feed from /api/public.
const PUBLIC_MODE = process.env.NEXT_PUBLIC_REGEN_MODE === "public";
export const api = (path: string) =>
  path.startsWith("/api/public") ? path : PUBLIC_MODE ? proxyFile(path) : API_ORIGIN + path;

export async function get<T>(path: string): Promise<T> {
  if (PUBLIC_MODE && !path.startsWith("/api/public")) return proxyGet<T>(path);
  const r = await fetch(api(path), { cache: "no-store" });
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json() as Promise<T>;
}

// The one write (v0.8): answer a waiting question. The API refuses it unless REGEN_API_WRITE=1 on your machine.
export async function post<T>(path: string, body: unknown): Promise<T> {
  if (PUBLIC_MODE) return proxyPost<T>(path, body);
  const r = await fetch(api(path), { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `${path}: ${r.status}`);
  return r.json() as Promise<T>;
}
