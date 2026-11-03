/* Load every highlight row of the open book into the notebook page, then scrape with extract_highlights.js.
 *
 * Run on the read.amazon.com/notebook tab with the book selected. A large notebook renders only its first
 * page of rows, and synthetic scrolling may never load the next batch. This script fetches the pages
 * through the notebook's own pagination endpoint,
 *   GET /notebook?asin=<ASIN>&contentLimitState=<state>&token=<token>
 * appends each new row to #kp-notebook-annotations, and stops at the first page whose rows are all repeats,
 * because the token can loop and re-serve rows already on the page (SKILL.md, Step 2). A row is a repeat
 * when its location, text, note and header match a row already seen. Rows with no text, which the export
 * limit hides, also carry their order among the text-less rows of the same location on their page, so two
 * hidden highlights that start at one location stay two rows.
 *
 * It runs async and returns 'started' at once, since an AppleScript `execute` returns only a synchronous
 * value. Poll with:   JSON.stringify(window.__pg)
 * until done is true. __pg = {done, asin, pages, added, total, header, capped, tok, st, err}.
 * - header is the "N Highlights | M Notes" text the page shows. It can undercount, so Step 4's database
 *   count is the check that no row is missing.
 * - capped: true means the 60-page limit stopped it with pages left. Run it again on the same page load and it
 *   resumes from the token it stopped at.
 * - err is set when a page fails or holds no rows at all, such as a sign-in page served with HTTP 200.
 *
 * The ASIN comes from the book's /dp/ link on the page, because the notebook ignores ?asin= in its own URL and
 * may show the last book viewed. window.__khAsin is used only when the page has no /dp/ link, and a value that
 * disagrees with the page's link stops the script.
 */
(() => {
  const prev = window.__pg;
  const pg = window.__pg = { done: false, asin: null, pages: 0, added: 0, total: 0, header: null, capped: false,
    tok: '', st: '', err: null };
  (async () => {
    try {
      if (!location.pathname.startsWith('/notebook')) throw new Error('not the notebook page: ' + location.href);
      const link = document.querySelector('#kp-notebook-annotations-pane a[href*="/dp/"]')
        || document.querySelector('a[href*="/dp/"]');
      const pageAsin = ((link || {}).href || '').match(/\/dp\/([A-Z0-9]{10})/)?.[1];
      const handAsin = window.__khAsin;
      if (handAsin && !/^[A-Z0-9]{10}$/.test(handAsin)) throw new Error('window.__khAsin is not an ASIN: ' + handAsin);
      if (handAsin && pageAsin && handAsin !== pageAsin)
        throw new Error(`window.__khAsin ${handAsin} disagrees with the page's ${pageAsin}: clear it or select that book`);
      const asin = pg.asin = pageAsin || handAsin;
      if (!asin) throw new Error('no ASIN found: set window.__khAsin = "<ASIN>" and run again');

      const ann = document.querySelector('#kp-notebook-annotations');
      const pane = document.querySelector('#kp-notebook-annotations-pane') || document.body || {};
      pg.header = ((pane.innerText || '').match(/[\d,]+\s+Highlights?\s*\|\s*[\d,]+\s+Notes?/) || [null])[0];
      const txt = (r, s) => ((r.querySelector(s) || {}).textContent || '').trim();
      const keys = rows => {
        const n = {};
        return rows.map(r => {
          const loc = (r.querySelector('#kp-annotation-location') || {}).value;
          const text = txt(r, 'span#highlight');
          const k = [loc, text, txt(r, '#note'), txt(r, '#annotationHighlightHeader')].join('|');
          if (text) return k;
          n[k] = (n[k] || 0) + 1;
          return k + '|hidden#' + n[k];
        });
      };
      const seen = new Set(keys([...ann.querySelectorAll('.kp-notebook-row-separator')]));
      const resume = prev && prev.capped && prev.asin === asin && prev.tok;
      let tok = resume ? prev.tok : (document.querySelector('.kp-notebook-annotations-next-page-start') || {}).value || '';
      let st = resume ? prev.st : (document.querySelector('.kp-notebook-content-limit-state') || {}).value || '';
      for (let i = 0; tok && i < 60; i++) {
        const r = await fetch(`/notebook?asin=${asin}&contentLimitState=${encodeURIComponent(st)}&token=${encodeURIComponent(tok)}`,
          { headers: { 'x-requested-with': 'XMLHttpRequest' } });
        if (!r.ok) throw new Error(`page ${pg.pages + 1}: HTTP ${r.status}`);
        const d = new DOMParser().parseFromString(await r.text(), 'text/html');
        const rows = [...d.querySelectorAll('.kp-notebook-row-separator')];
        if (!rows.length) throw new Error(`page ${pg.pages + 1}: no rows (signed out, or an error page?)`);
        let added = 0;
        keys(rows).forEach((k, j) => {
          if (!seen.has(k)) { seen.add(k); ann.appendChild(document.importNode(rows[j], true)); added++; }
        });
        pg.pages++; pg.added += added;
        if (!added) { tok = ''; break; }
        const nt = d.querySelector('.kp-notebook-annotations-next-page-start');
        const ns = d.querySelector('.kp-notebook-content-limit-state');
        tok = nt ? nt.value : '';
        if (ns && ns.value) st = ns.value;
      }
      pg.tok = tok; pg.st = st;
      pg.capped = !!tok;
      pg.total = ann.querySelectorAll('.kp-notebook-row-separator').length;
    } catch (e) { pg.err = String(e); }
    pg.done = true;
  })();
  return 'started';
})()
