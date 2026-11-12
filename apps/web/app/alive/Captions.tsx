// Shadow's captions (ALIVE Phase 2): one line per thing Shadow did or declined, newest first, each from a real
// shadow.answer / shadow.abstain narration (same job, same by, same outcome as the ledger row), plus the standing
// line saying who has the wheel, from the last shadow.mode signal. Nothing here is composed without an event.
import type { Narration } from "@/lib/spine";
import { hasWheel } from "./Seat";

export type Caption = { id: string; ts: string | null; text: string; tone: "answer" | "abstain" };

/** A caption for a Shadow narration, or null for any other kind. */
export function caption(n: Narration): Caption | null {
  const co = n.company || "a posting";
  const id = `${n.id ?? ""}:${n.job ?? ""}:${n.kind}`;
  if (n.kind === "shadow.answer") {
    const conf = typeof n.conf === "number" ? ` · ${Math.round(n.conf * 100)}% sure` : "";
    return { id, ts: n.ts ?? null, tone: "answer", text: `Shadow answered for ${co}${conf}` };
  }
  if (n.kind === "shadow.abstain") {
    return { id, ts: n.ts ?? null, tone: "abstain", text: `Left this for you at ${co}: ${n.detail || "not sure enough"}` };
  }
  return null;
}

const WHEEL: Record<string, string> = {
  autopilot: "Shadow has the wheel", always: "Shadow has the wheel",
  calls: "You have the wheel · Shadow rings you first", off: "You have the wheel",
};

export function Captions({ mode, items }: { mode: string | null; items: Caption[] }) {
  const hhmm = (ts: string | null) => (ts && ts.length >= 16 ? ts.slice(11, 16) : "");
  return (
    <div className={`al-captions${hasWheel(mode) ? " al-lit" : ""}`}>
      <p className="al-wheel" role="status">{mode ? WHEEL[mode] ?? `Shadow: ${mode}` : "Shadow's mode not reported yet"}</p>
      {items.length > 0 && (
        <ol aria-live="polite" aria-label="What Shadow did">
          {items.map((c) => (
            <li key={c.id} className={`al-cap-${c.tone}`}><time>{hhmm(c.ts)}</time> {c.text}</li>
          ))}
        </ol>
      )}
    </div>
  );
}
