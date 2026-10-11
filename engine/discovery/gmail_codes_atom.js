// Greenhouse security codes from Gmail's Atom feed (run in any signed-in mail.google.com tab with the browser tool).
// One fetch, no UI: the search-results UI freezes background tabs after long scripts; the feed answers in ~200 ms.
// The feed lists unread inbox mail only, which is exactly where a fresh code lands. Nothing is opened or changed.
// Output: [{company, code, iso}] -> convert iso to local "HH:MM" as `when`, then  python -m engine codes '<json>'
(async () => {
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
  return JSON.stringify(out);
})();
