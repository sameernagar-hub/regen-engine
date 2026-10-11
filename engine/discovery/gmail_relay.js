// Hands-free codes: open https://mail.google.com/mail/u/0/feed/atom/ (a tiny XML page: the full Gmail UI freezes
// background tabs) and paste this once (browser tool or DevTools) while
// `python -m engine relay` runs. Every 20 s it reads Gmail's Atom feed (unread inbox, one fetch, no UI) and POSTs
// [{company, code, iso}] to the loopback relay, which writes the code only for a job that is waiting on it.
// text/plain keeps it a "simple" request (no CORS preflight). Stop: clearInterval(window.regenTimer).
window.regenPush = async () => {
  const x = await (await fetch("/mail/u/0/feed/atom/")).text(); // regex, not DOMParser: Gmail enforces TrustedHTML
  const out = [];
  for (const m of x.matchAll(/<entry>([\s\S]*?)<\/entry>/g)) {
    const e = m[1];
    const title = (e.match(/<title>([\s\S]*?)<\/title>/) || [])[1] || "";
    const summary = (e.match(/<summary>([\s\S]*?)<\/summary>/) || [])[1] || "";
    const iso = (e.match(/<issued>([^<]*)/) || [])[1] || "";
    const co = title.match(/application to (.+?)(?: - |$)/i);
    const code = summary.match(/application:?\s*([A-Za-z0-9]{8})\b/i);
    if (co && code) out.push({ company: co[1].trim(), code: code[1], iso });
  }
  const r = await fetch("http://127.0.0.1:8799/codes", { method: "POST", headers: { "Content-Type": "text/plain" }, body: JSON.stringify(out) });
  return (window.regenLast = await r.text());
};
clearInterval(window.regenTimer);
window.regenTimer = setInterval(() => window.regenPush().catch((e) => (window.regenLast = String(e))), 20000);
