// Greenhouse security codes from a signed-in Gmail tab (run with the browser tool, `await` the result).
// Reads only the search-result rows ("Security code for your application to <Company> - ... : <CODE>"),
// returns [{company, code, when}] as JSON. Nothing leaves the page; no message is opened, marked or changed.
// Feed the output to:  python -m engine codes '<json>'   (writes workspace/codes/<board>_<id>.txt for waiting jobs)
(async () => {
  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  location.hash = "#inbox"; // force Gmail to re-run the search even if this tab already shows it
  await sleep(1200);
  location.hash = "#search/" + encodeURIComponent("subject:(security code) newer_than:1h");
  let rows = [];
  for (let i = 0; i < 40; i++) {
    await sleep(300);
    rows = [...document.querySelectorAll("div[role=main] tr.zA")]; // no offsetParent check: the tab may be hidden
    if (rows.length) break;
  }
  const out = [];
  for (const r of rows.slice(0, 20)) {
    const t = (r.textContent || "").replace(/\s+/g, " "); // innerText is empty while the tab is in the background
    const m = t.match(/application to ([^,]+?)(?: - |, ).*?application:?\s*([A-Za-z0-9]{8})\b/i);
    // the row's time ("22:17" today, "Oct 6" earlier): engine codes rejects codes sent before the job started waiting
    const when = (r.querySelector(".xW span[title], .xW span") || {}).textContent || "";
    if (m) out.push({ company: m[1].trim(), code: m[2], when: when.trim() });
  }
  return JSON.stringify(out);
})();
