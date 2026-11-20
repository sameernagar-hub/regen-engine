// Input screen for every box that takes resume text (Test drive, /pipeline, /docs, POST /api/public/try). Runs in the
// browser before anything is read, and again on the server so the API can't be called around it. Three refusals:
//   abuse      profanity, slurs or threats, including masked spellings (f*ck, sh!t, a$$hole)
//   sensitive  data that must never be pasted into a website: SSNs, card numbers, passwords, API keys, bank numbers
//   not-resume too little text, or text with no sign of a job history (no titles, roles, dates or sections)
// Nothing is logged: the reason names the kind of problem, never the matched text.
import { analyze } from "./resume-nlp";

export type Screen = { ok: true } | { ok: false; kind: "abuse" | "sensitive" | "not-resume"; reason: string };

// masked letters people use to dodge filters
const LEET: Record<string, string> = { a: "a@4*", e: "e3*", i: "i1!|*", o: "o0*", u: "uv*", s: "s$5*", t: "t7+", c: "c(k*", k: "k", g: "g9", l: "l1|" };
const SEP = "[^a-z0-9]{0,2}";  // f.u.c.k, f-u-c-k, f**k
const word = (w: string) => w.split("").map((ch) => `[${(LEET[ch] ?? ch).replace(/[\]\\^-]/g, "\\$&")}]`).join(SEP);
// whole words only, so "Scunthorpe", "class", "assess", "cocktail", "Dickens" and "retardant" pass
const ABUSE = ["fuck", "fucking", "fucker", "motherfucker", "fck", "fuk", "shit", "shitty", "bullshit", "bitch", "cunt", "asshole", "bastard",
  "dickhead", "slut", "whore", "wanker", "twat", "nigger", "nigga", "faggot", "fag", "retard", "retarded", "kike", "spic", "chink"];
const ABUSE_RE = new RegExp(`(?<![a-z])(?:${ABUSE.map(word).join("|")})(?![a-z])`, "i");
const THREAT_RE = /\b(?:i(?:'ll| will| am going to| wanna| want to)\s+(?:kill|shoot|stab|hurt|bomb)|kill\s+(?:you|them|everyone|all of you)|bomb\s+(?:threat|the)|shoot\s+up)\b/i;

const SSN_RE = /\b(?!000|666|9\d\d)\d{3}-(?!00)\d{2}-(?!0000)\d{4}\b|\b(?:ssn|social security(?: number| no\.?)?)\s*[:#]?\s*\d{3}[- ]?\d{2}[- ]?\d{4}\b/i;
const SECRET_RE = /\b(?:password|passwd|pwd|passcode)\s*[:=]\s*\S{4,}|\b(?:sk|pk|rk)[-_](?:live|test|proj|ant)?[-_]?[a-z0-9]{16,}|\bAKIA[0-9A-Z]{16}\b|\bgh[pousr]_[A-Za-z0-9]{30,}|-----BEGIN [A-Z ]*PRIVATE KEY-----/i;
const BANK_RE = /\b(?:routing|account|acct|bank)\s*(?:number|no\.?|#)\s*[:#]?\s*\d[\d -]{6,}|\biban\s*[:#]?\s*[A-Z]{2}\d{2}/i;

function luhn(d: string) {
  let sum = 0;
  for (let i = 0; i < d.length; i++) { let n = +d[d.length - 1 - i]; if (i % 2) { n *= 2; if (n > 9) n -= 9; } sum += n; }
  return sum % 10 === 0;
}
// card layouts only (4-4-4-4, Amex 4-6-5, or one unbroken run), so a phone number next to a year is not a card
const hasCard = (t: string) => (t.match(/\b\d{4}([ -]?)\d{4}\1\d{4}\1\d{1,7}\b|\b\d{4}[ -]?\d{6}[ -]?\d{5}\b/g) || []).some((m) => { const d = m.replace(/\D/g, ""); return d.length >= 13 && d.length <= 19 && !/^(\d)\1+$/.test(d) && luhn(d); });

export function screenResume(text: string): Screen {
  const t = (text || "").normalize("NFKC");
  if (ABUSE_RE.test(t) || THREAT_RE.test(t))
    return { ok: false, kind: "abuse", reason: "This text contains offensive or threatening language, so it was not accepted. Paste a resume: your job titles, where you worked and what you did." };
  if (SSN_RE.test(t)) return { ok: false, kind: "sensitive", reason: "This looks like it contains a Social Security number. Remove it and try again: a resume never needs one, and you should never paste one into a website." };
  if (hasCard(t)) return { ok: false, kind: "sensitive", reason: "This looks like it contains a payment card number. Remove it and try again: never paste card numbers into a website." };
  if (SECRET_RE.test(t)) return { ok: false, kind: "sensitive", reason: "This looks like it contains a password, API key or private key. Remove it (and change it, if it was real) before you try again." };
  if (BANK_RE.test(t)) return { ok: false, kind: "sensitive", reason: "This looks like it contains a bank account or routing number. Remove it and try again." };
  const words = t.match(/[A-Za-z][A-Za-z'+#.-]*/g) || [];
  if (words.length < 12) return { ok: false, kind: "not-resume", reason: "That's too short to be a resume. Paste the whole thing: job titles, employers, dates and what you did." };
  const letters = (t.match(/[A-Za-z]/g) || []).length;
  if (letters / Math.max(1, t.replace(/\s/g, "").length) < 0.5 || /(.)\1{9,}/.test(t) || new Set(words.map((w) => w.toLowerCase())).size < words.length * 0.2)
    return { ok: false, kind: "not-resume", reason: "This doesn't read like a resume (mostly symbols, numbers or repeated text). Paste your actual resume text." };
  const a = analyze(t, false, false);
  const dated = /\b(?:19[6-9]\d|20[0-4]\d)\b|\bpresent\b|\bcurrent\b/i.test(t);
  if (a.evidence_total === 0 && !dated)
    return { ok: false, kind: "not-resume", reason: "This doesn't look like a resume: no job titles, roles, skills or dates were found. Paste your resume text and run it again." };
  return { ok: true };
}
