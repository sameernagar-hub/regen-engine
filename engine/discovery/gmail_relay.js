// Hands-free codes: open https://mail.google.com/mail/u/0/feed/atom/ (a tiny XML page: the full Gmail UI freezes
// background tabs) and paste this once (browser tool or DevTools) while
// `python -m engine relay` runs. Every 20 s it reads Gmail's Atom feed (unread inbox, one fetch, no UI) and POSTs
// [{company, code, iso}] to the loopback relay, which writes the code only for a job that is waiting on it.
// Gmail threads every code email for one company: the feed entry carries the thread's newest time but an OLDER
// message's summary (10-11: the stale code bounced). So each code thread is read in print view (one small fetch) and
// every code in it is sent oldest first; the relay takes the newest one the job has not tried.
// text/plain keeps it a "simple" request (no CORS preflight). Stop: clearInterval(window.regenTimer).
window.regenPush = async () => {
  const x = await (await fetch("/mail/u/0/feed/atom/")).text(); // regex, not DOMParser: Gmail enforces TrustedHTML
  const out = [];
  for (const m of x.matchAll(/<entry>([\s\S]*?)<\/entry>/g)) {
    const e = m[1];
    const title = (e.match(/<title>([\s\S]*?)<\/title>/) || [])[1] || "";
    const iso = (e.match(/<issued>([^<]*)/) || [])[1] || "";
    const co = title.match(/application to (.+?)(?: - |$)/i);
    if (!co) continue;
    const href = ((e.match(/<link[^>]*href="([^"]+)"/) || [])[1] || "").replace(/&amp;/g, "&");
    const th = (href.match(/message_id=([0-9a-f]+)/) || [])[1];
    let codes = [];
    if (th) {
      const t = await (await fetch("/mail/u/0/?ui=2&view=pt&search=all&th=" + th)).text();
      codes = [...t.matchAll(/application:?\s*(?:<[^>]+>\s*)*([A-Za-z0-9]{8})\b/gi)].map((z) => z[1]);
    }
    if (!codes.length) codes = [((e.match(/<summary>([\s\S]*?)<\/summary>/) || [])[1] || "").match(/application:?\s*([A-Za-z0-9]{8})\b/i)?.[1]].filter(Boolean);
    for (const code of codes) out.push({ company: co[1].trim(), code, iso });
  }
  const r = await fetch("http://127.0.0.1:8799/codes", { method: "POST", headers: { "Content-Type": "text/plain" }, body: JSON.stringify(out) });
  return (window.regenLast = await r.text());
};
clearInterval(window.regenTimer);
window.regenTimer = setInterval(() => window.regenPush().catch((e) => (window.regenLast = String(e))), 20000);
