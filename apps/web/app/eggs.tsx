"use client";
// Easter eggs, site-wide. Nothing here runs per frame: one keydown listener, one hover timer, and effects that build
// their DOM on trigger and remove it when done. Listed in CHANGELOG [Unreleased] 2026-10-22 for maintainers only;
// the site itself never mentions them.
//   - the Konami code revs the engine: the page shakes and gold sparks fly
//   - typing "panda" (outside a text field) makes a panda peek up from the bottom edge and wave
//   - typing "hired" rains paper resumes
//   - holding the cursor on the dock's gear for 3 s overheats it (gear 2 is the house rule)
//   - the browser console greets whoever opens it
// prefers-reduced-motion: the notes still appear, the motion does not.
import { useEffect } from "react";
import "./eggs.css";

const KONAMI = ["ArrowUp", "ArrowUp", "ArrowDown", "ArrowDown", "ArrowLeft", "ArrowRight", "ArrowLeft", "ArrowRight", "b", "a"];
const WORDS: Record<string, () => void> = { panda: peek, hired: resumes };
const calm = () => !!window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

function spawn(html: string, cls: string, ms: number): HTMLElement {
  const el = document.createElement("div");
  el.className = cls;
  el.setAttribute("aria-hidden", "true");
  el.innerHTML = html;
  document.body.appendChild(el);
  setTimeout(() => el.remove(), ms);
  return el;
}

function say(text: string) {
  document.querySelector(".egg-note")?.remove();
  const el = spawn("", "egg-note", 3600);
  el.setAttribute("role", "status");
  el.removeAttribute("aria-hidden");
  el.textContent = text;
}

function rev() {
  say("Overdrive unlocked. Cosmetically: the real engine stays in cruise.");
  if (calm()) return;
  document.body.classList.remove("egg-rev");
  void document.body.offsetWidth;  // restart the animation on a second code
  document.body.classList.add("egg-rev");
  setTimeout(() => document.body.classList.remove("egg-rev"), 900);
  const sparks = Array.from({ length: 28 }, (_, i) => {
    const a = (i / 28) * Math.PI * 2 + Math.random() * 0.3, d = 140 + Math.random() * 260;
    return `<i style="--x:${(Math.cos(a) * d).toFixed(0)}px;--y:${(Math.sin(a) * d).toFixed(0)}px;--t:${(0.5 + Math.random() * 0.5).toFixed(2)}s"></i>`;
  }).join("");
  spawn(sparks, "egg-sparks", 1300);
}

function peek() {
  spawn(`<svg viewBox="0 0 120 110" width="120" height="110">
    <circle cx="26" cy="22" r="16" fill="#111"/><circle cx="94" cy="22" r="16" fill="#111"/>
    <ellipse cx="60" cy="62" rx="50" ry="46" fill="#f7f5ef"/>
    <ellipse cx="40" cy="58" rx="12" ry="16" transform="rotate(30 40 58)" fill="#111"/>
    <ellipse cx="80" cy="58" rx="12" ry="16" transform="rotate(-30 80 58)" fill="#111"/>
    <circle cx="42" cy="56" r="4.5" fill="#fff"/><circle cx="78" cy="56" r="4.5" fill="#fff"/>
    <circle cx="43" cy="57" r="2.6" fill="#120a05"/><circle cx="77" cy="57" r="2.6" fill="#120a05"/>
    <path d="M53 74Q60 70 67 74Q65 80 60 81Q55 80 53 74Z" fill="#111"/>
    <path d="M52 86Q56 90 60 86Q64 90 68 86" fill="none" stroke="#111" stroke-width="2" stroke-linecap="round"/>
    <ellipse cx="30" cy="80" rx="7" ry="4" fill="#ff8fab" opacity=".6"/><ellipse cx="90" cy="80" rx="7" ry="4" fill="#ff8fab" opacity=".6"/>
    <g class="egg-paw"><ellipse cx="104" cy="96" rx="14" ry="12" fill="#111"/></g></svg>`, "egg-peek", calm() ? 2500 : 3400);
}

function resumes() {
  say("Not yet. Keep the engine running.");
  if (calm()) return;
  const sheets = Array.from({ length: 26 }, () =>
    `<i style="left:${(Math.random() * 100).toFixed(1)}vw;--r:${(Math.random() * 720 - 360).toFixed(0)}deg;--s:${(2.2 + Math.random() * 1.6).toFixed(2)}s;--d:${(Math.random() * 0.8).toFixed(2)}s"><b></b><b></b><b></b></i>`).join("");
  spawn(sheets, "egg-paper", 4800);
}

const ART = `
   ▄▄       ▄▄
  ████▄▄▄▄▄████      REGEN engine
   ▀█▀ ▄▄▄ ▀█▀       You opened the console, so you are one of us.
   █ ▐█▌ ▐█▌ █       The engine is open source: github.com/sameernagar-hub/regen-engine
   █   ▄▀▄   █       Try the Konami code. Or type a word a panda would know.
    ▀▄▄▄▄▄▄▄▀
`;

export function Eggs() {
  useEffect(() => {
    const w = window as typeof window & { __regenHello?: boolean };
    if (!w.__regenHello) {
      w.__regenHello = true;
      console.log(`%c${ART}`, "color:#f2c14e;font-family:monospace;font-size:12px");
    }

    let keys: string[] = [], typed = "";
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement | null;
      if (t && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))) return;
      const k = e.key.length === 1 ? e.key.toLowerCase() : e.key;
      keys = [...keys, k].slice(-KONAMI.length);
      if (keys.join() === KONAMI.join()) { keys = []; rev(); return; }
      if (k.length !== 1) return;
      typed = (typed + k).slice(-12);
      for (const [word, fn] of Object.entries(WORDS)) if (typed.endsWith(word)) { typed = ""; fn(); }
    };

    // the dock gear: hover 3 s and it overheats
    let timer = 0;
    const over = (e: PointerEvent) => {
      const gear = (e.target as Element | null)?.closest?.(".dock .gear");
      if (!gear || timer) return;
      timer = window.setTimeout(() => {
        gear.classList.add("egg-hot");
        say("Easy. Gear 2 is the house rule.");
        setTimeout(() => gear.classList.remove("egg-hot"), 2600);
      }, 3000);
      gear.addEventListener("pointerleave", () => { clearTimeout(timer); timer = 0; }, { once: true });
    };

    window.addEventListener("keydown", onKey);
    document.addEventListener("pointerover", over);
    return () => { window.removeEventListener("keydown", onKey); document.removeEventListener("pointerover", over); clearTimeout(timer); };
  }, []);
  return null;
}
