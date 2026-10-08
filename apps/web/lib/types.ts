// Types come from the API's OpenAPI schema (npm run gen:api), so the page and the API can't drift apart.
import type { components } from "./api";

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

export async function get<T>(path: string): Promise<T> {
  const r = await fetch(path, { cache: "no-store" });
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json() as Promise<T>;
}

// The one write (v0.8): answer a waiting question. The API refuses it unless REGEN_API_WRITE=1 on your machine.
export async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).detail || `${path}: ${r.status}`);
  return r.json() as Promise<T>;
}
