/* Load every highlight row of the open book into the notebook page, then scrape with extract_highlights.js.
 *
 * Run on the read.amazon.com/notebook tab with the book selected. A large notebook renders only its first
 * page of rows, and synthetic scrolling may never load the next batch. This script fetches the pages
 * through the notebook's own pagination endpoint,
 *   GET /notebook?asin=<ASIN>&contentLimitState=<state>&token=<token>
 * appends each new row to #kp-notebook-annotations, and stops at the first page that adds no new row. A row
 * counts as new when its location plus its text has not been seen, because the token can loop and re-serve
 * rows already on the page (SKILL.md, Step 2).
 *
 * It runs async and returns 'started' at once, since an AppleScript `execute` returns only a synchronous
 * value. Poll with:   JSON.stringify(window.__pg)
 * until done is true. __pg = {done, pages, added, total, capped, err}. capped: true means the 60-page limit
 * stopped it while the token still had pages, so run it again.
 *
 * The ASIN comes from window.__khAsin when set, else from the book's /dp/ link on the page. The notebook
 * ignores ?asin= in its own URL and may show the last book viewed, so the URL is not trusted for it.
 */
window.__pg = { done: false, pages: 0, added: 0, total: 0, capped: false, err: null };
(async () => {
  try {
    if (!location.pathname.startsWith('/notebook')) throw new Error('not the notebook page: ' + location.href);
    const asin = window.__khAsin
      || ((document.querySelector('#kp-notebook-annotations-pane a[href*="/dp/"], a[href*="/dp/"]') || {}).href || '')
        .match(/\/dp\/([A-Z0-9]{10})/)?.[1];
    if (!asin) throw new Error('no ASIN found: set window.__khAsin = "<ASIN>" and run again');
    const ann = document.querySelector('#kp-notebook-annotations');
    const key = r => (r.querySelector('#kp-annotation-location') || {}).value + '|'
      + ((r.querySelector('span#highlight') || {}).textContent || '');
    const seen = new Set([...ann.querySelectorAll('.kp-notebook-row-separator')].map(key));
    let tok = (document.querySelector('.kp-notebook-annotations-next-page-start') || {}).value || '';
    let st = (document.querySelector('.kp-notebook-content-limit-state') || {}).value || '';
    let i = 0;
    for (; tok && i < 60; i++) {
      const r = await fetch(`/notebook?asin=${asin}&contentLimitState=${encodeURIComponent(st)}&token=${encodeURIComponent(tok)}`,
        { headers: { 'x-requested-with': 'XMLHttpRequest' } });
      if (!r.ok) throw new Error(`page ${i + 1}: HTTP ${r.status}`);
      const d = new DOMParser().parseFromString(await r.text(), 'text/html');
      let added = 0;
      for (const row of d.querySelectorAll('.kp-notebook-row-separator')) {
        const k = key(row);
        if (!seen.has(k)) { seen.add(k); ann.appendChild(document.importNode(row, true)); added++; }
      }
      __pg.pages++; __pg.added += added;
      if (!added) { tok = ''; break; }
      const nt = d.querySelector('.kp-notebook-annotations-next-page-start');
      const ns = d.querySelector('.kp-notebook-content-limit-state');
      tok = nt ? nt.value : '';
      if (ns && ns.value) st = ns.value;
    }
    __pg.capped = !!tok;
    __pg.total = ann.querySelectorAll('.kp-notebook-row-separator').length;
  } catch (e) { __pg.err = String(e); }
  __pg.done = true;
})();
'started'
