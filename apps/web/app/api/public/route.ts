// Public mode only: the anonymized feed the engine publishes (`python -m engine site --push`), proxied so the browser
// talks to one origin. Cached for 30 s, so any number of visitors cost one fetch per 30 s.
export const revalidate = 30;

const FEED = process.env.REGEN_FEED_URL || "https://sameernagar-hub.github.io/regen-engine/replay.json";

export async function GET() {
  const r = await fetch(FEED, { next: { revalidate: 30 } });
  if (!r.ok) return Response.json({ error: `feed ${r.status}` }, { status: 502 });
  return Response.json(await r.json(), { headers: { "Cache-Control": "public, max-age=15" } });
}
