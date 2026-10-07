// REGEN: job-alert emails -> leads (run inside a signed-in Gmail tab, e.g. via the Claude in Chrome javascript tool;
// prefix the expression with `await` so the tool waits for it, and pass the day window in the last line).
// Reads LinkedIn / Indeed / Glassdoor / ZipRecruiter / Handshake alert emails from the last DAYS days through
// Gmail's own print view (same origin, no API keys, nothing leaves the browser) and writes one row per listing
// into an <article id="regen-alerts"> on the page:  source ¦ title ¦ company ¦ location ¦ email date, rows split by §
// (visible separators, because page-text readers collapse tabs and newlines).
// The operator copies that text to workspace/alerts/<date>.txt and runs `python -m engine alerts <file>`,
// which filters, resolves each company to its own ATS board and queues the matches (engine/discovery/alerts.py).
// Only titles, companies and locations are extracted: no links, tracking ids or message bodies.
(async (DAYS = 2) => {
  // Gmail matches these fragments against the sender address: LinkedIn job alerts + "jobs similar to",
  // Indeed job matches, ZipRecruiter, Glassdoor and Handshake (non-listing emails just parse to nothing)
  const SENDERS = ['jobalerts-noreply', 'jobs-noreply', 'match.indeed.com', 'ziprecruiter.com', 'glassdoor.com',
    'joinhandshake.com'];
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const pol = window._regenPol || (window._regenPol = trustedTypes.createPolicy('regen' + Date.now(), { createHTML: s => s }));
  const ik = window.GLOBALS && GLOBALS[9];
  const lines = async id => {
    const html = await (await fetch(`/mail/u/0/?ik=${ik}&view=pt&search=all&th=${id}`)).text();
    const d = new DOMParser().parseFromString(pol.createHTML(html), 'text/html');
    d.querySelectorAll('style,script,head').forEach(e => e.remove());
    const w = d.createTreeWalker(d.body, NodeFilter.SHOW_TEXT), out = [];
    for (let n; (n = w.nextNode());) {
      const s = n.nodeValue.replace(/[͏​-‏  ­\s]+/g, ' ').trim();
      if (s && out[out.length - 1] !== s) out.push(s);
    }
    return out;
  };
  // badges that sit between a title and its company line ("New Grad ..." is a title, so badges match whole lines)
  const JUNK = /^((Actively recruiting|Easy Apply|Apply now|Message|New|Recently posted|1-Click Apply|View Details)$|\$|\d+ (school alum|connection)|•)/i;
  const back = (L, i) => { let j = i - 1; while (j > 0 && JUNK.test(L[j])) j--; return j; };
  const LOC = /(, [A-Z]{2}( \d{5})?$|^Remote$|United States|Bay Area|\(Remote\)|\(Hybrid\)|\(On-?site\)|, England)/;
  const parse = {
    linkedin(L) {
      const r = [];
      for (let i = 1; i < L.length; i++) {
        if (/This email was intended|^See all/.test(L[i])) break;
        const m = L[i].match(/^(.+?) · (.+)$/);
        if (!m) continue;
        const j = back(L, i);
        if (!L[j].includes(' · ') && L[j] !== 'Manage alerts') r.push([L[j].replace(/^#/, ''), m[1], m[2]]);
      }
      return r;
    },
    handshake(L) {
      const r = [];
      for (let i = 2; i < L.length; i++)
        if (L[i].includes(' • ') && /Full-Time|Part-Time|Internship|Contract/.test(L[i]))
          r.push([L[i - 1], L[i - 2], L[i].split(' • ').pop()]);
      return r;
    },
    glassdoor(L) {
      const r = [];
      for (let i = 2; i < L.length; i++) {
        if (/This message was sent/.test(L[i])) break;
        if (!/, [A-Z]{2}$|^Remote$/.test(L[i]) || /\$/.test(L[i - 1])) continue;
        const rated = /^\d\.\d ★$/.test(L[i - 2]);
        const co = rated ? L[i - 3] : L[i - 2];
        if (!/^(Your job listings|You can edit|To help refine)/.test(co)) r.push([L[i - 1], co, L[i]]);
      }
      return r;
    },
    ziprecruiter(L) {
      const r = [];
      for (let i = 1; i < L.length; i++) {
        if (/^View More Jobs/.test(L[i])) break;
        const p = L[i].split(' • ');
        if (p.length >= 2 && LOC.test(p[1])) r.push([L[back(L, i)], p[0], p[1]]);
      }
      return r;
    },
    indeed(L, subject) {
      const m = subject.match(/^(.+) @ (.+)$/);
      if (!m) return [];
      const k = L.indexOf(m[2], L.indexOf('This is a bad match'));
      return [[m[1], m[2], k > 0 && LOC.test(L[k + 1]) ? L[k + 1] : '']];
    },
  };
  const src = e => /linkedin/.test(e) ? 'linkedin' : /handshake/.test(e) ? 'handshake' : /glassdoor/.test(e) ? 'glassdoor'
    : /ziprecruiter/.test(e) ? 'ziprecruiter' : /indeed/.test(e) ? 'indeed' : null;

  location.hash = '#search/' + encodeURIComponent(`newer_than:${DAYS}d from:(${SENDERS.join(' OR ')})`);
  await sleep(5000);
  const rows = [...document.querySelectorAll('tr.zA')].filter(r => r.offsetParent);
  const seen = new Set(), tsv = [];
  let msgs = 0;
  for (const row of rows) {
    const from = row.querySelector('[email]')?.getAttribute('email') || '';
    const id = row.querySelector('[data-legacy-thread-id]')?.getAttribute('data-legacy-thread-id');
    if (!id || !src(from)) continue;
    const L = await lines(id), s = src(from);
    const subject = row.querySelector('.bog')?.innerText || L.find(x => / @ /.test(x)) || '';
    const date = row.querySelector('.xW span')?.title || '';
    msgs++;
    for (const [title, company, loc] of parse[s](L, subject)) {
      const key = (company + '|' + title).toLowerCase();
      if (!title || !company || seen.has(key) || /[¦§]/.test(title + company + loc)) continue;
      seen.add(key);
      tsv.push([s, title, company.replace(/ (New|\+1)$/, ''), loc, date].join(' ¦ '));
    }
  }
  let a = document.getElementById('regen-alerts');
  if (!a) { a = document.createElement('article'); a.id = 'regen-alerts'; document.body.prepend(a); }
  a.textContent = 'REGEN-ALERTS § ' + tsv.join(' § ') + ' § END-ALERTS';
  return `${msgs} alert emails, ${tsv.length} listings`;
})();
