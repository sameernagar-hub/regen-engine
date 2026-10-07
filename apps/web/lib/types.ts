// Types come from the API's OpenAPI schema (npm run gen:api), so the page and the API can't drift apart.
import type { components } from "./api";

export type Snapshot = components["schemas"]["Snapshot"];
export type Application = components["schemas"]["Application"];
export type Narration = components["schemas"]["Narration"];
export type HumanItem = components["schemas"]["HumanItem"];

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
