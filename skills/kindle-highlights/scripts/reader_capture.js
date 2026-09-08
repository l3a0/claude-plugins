/* Cloud Reader capture helper — install ONCE per page load via Control_Chrome.execute_javascript on the
 * read.amazon.com/?asin=<ASIN> tab (the whole file is one IIFE; it returns 'installed'). A reload wipes it:
 * re-run this file after every location.reload().
 *
 * Then drive it with small follow-up calls (each is one execute_javascript):
 *   __kh.snapshot                               // the display settings recorded at install — restore from this at the end
 *   __kh.applySettings(4, 2)                    // font index 4 + two columns via localStorage, then reload (re-install after)
 *   __kh.jump(299484)                           // annotations panel: open → click #notebook-grouped-item-<pos> → close
 *   __kh.capture('s000').then(r => __kh.last = r)   // capture the current screen; poll __kh.last
 *   __kh.sweep(1, 25, 's')                      // 25 × (next page → wait for the new render → capture 's001'..'s025')
 *   JSON.stringify(__kh.sweepLog.slice(-5))     // poll progress: [i, changed, label, tokens] per screen
 *
 * Each capture POSTs two files to the localhost receiver (scripts/receiver.py):
 *   pages/<name>.png   the page render(s) drawn into a canvas with a 64 px white border (Vision clips glyphs at the
 *                      image edge without it), at the render's native resolution (≤ 2048 px wide),
 *   pages/<name>.json  every .kg-client-highlight WORD rect, normalized to that PNG: {tok: "<start>/<end>", x, y, w, h,
 *                      hcss}, plus the footer label, settings and viewport. cutter.py matches OCR words to these rects.
 *
 * Requirements that bit in practice: the tab must stay document.visibilityState === 'visible' (renders freeze when
 * hidden — a macOS full-screen Chrome window goes hidden the moment the user switches Space); the annotations panel
 * must be CLOSED before flipping (jump() closes it); two-column mode (applySettings(_, 2)) keeps lines short enough
 * that Vision does not drop the last character of every line.
 */
(() => {
  const K = window.__kh = {};
  K.RX = 'http://127.0.0.1:8931';
  K.PAD = 64;
  K.snapshot = localStorage.getItem('KWR_Display_Settings');
  K.pageImgs = () => [...document.querySelectorAll('img')].filter(i => i.src.startsWith('blob:') && i.complete && i.naturalWidth > 200 && i.getBoundingClientRect().width > 100);
  K.label = () => (document.querySelector('.footer-label.position')?.innerText || '').trim();
  K.imgSrc = () => K.pageImgs().map(i => i.src).join(',');
  K.sleep = ms => new Promise(r => setTimeout(r, ms));
  K.rects = () => {
    const out = [];
    for (const d of document.querySelectorAll('.kg-client-highlight')) {
      const tok = [...d.classList].find(c => /^\d+\/\d+$/.test(c));
      if (!tok) continue;
      const r = d.getBoundingClientRect();
      if (r.width <= 0 || r.height <= 0) continue;
      out.push({ tok, x: r.left, y: r.top, w: r.width, h: r.height });
    }
    return out;
  };
  K.capture = async (name) => {
    const imgs = K.pageImgs();
    if (!imgs.length) return { err: 'no page img' };
    const rs = imgs.map(i => i.getBoundingClientRect());
    const ux = Math.min(...rs.map(r => r.left)), uy = Math.min(...rs.map(r => r.top));
    const ux2 = Math.max(...rs.map(r => r.right)), uy2 = Math.max(...rs.map(r => r.bottom));
    const scale = imgs[0].naturalWidth / rs[0].width, P = K.PAD;
    const W = Math.round((ux2 - ux) * scale), H = Math.round((uy2 - uy) * scale);
    const c = document.createElement('canvas');
    c.width = W + 2 * P; c.height = H + 2 * P;
    const g = c.getContext('2d');
    g.fillStyle = '#fff'; g.fillRect(0, 0, c.width, c.height);
    imgs.forEach((im, i) => { const r = rs[i]; g.drawImage(im, P + Math.round((r.left - ux) * scale), P + Math.round((r.top - uy) * scale), Math.round(r.width * scale), Math.round(r.height * scale)); });
    // rects normalized to the PADDED canvas, so OCR coordinates (normalized to the PNG) line up directly
    const rects = K.rects().map(r => ({ tok: r.tok, x: (P + (r.x - ux) * scale) / c.width, y: (P + (r.y - uy) * scale) / c.height, w: r.w * scale / c.width, h: r.h * scale / c.height, hcss: r.h }));
    const meta = { name, label: K.label(), union: { x: ux, y: uy, w: ux2 - ux, h: uy2 - uy }, pad: P, scale, nImgs: imgs.length, natural: imgs.map(i => [i.naturalWidth, i.naturalHeight]), canvas: [c.width, c.height], dpr: devicePixelRatio, inner: [innerWidth, innerHeight], rects, vis: document.visibilityState, settings: localStorage.getItem('KWR_Display_Settings') };
    const blob = await new Promise(res => c.toBlob(res, 'image/png'));
    const r1 = await fetch(K.RX + '/page?name=' + name + '.png', { method: 'POST', body: blob }).then(r => r.text());
    const r2 = await fetch(K.RX + '/json?name=' + name + '.json', { method: 'POST', body: JSON.stringify(meta) }).then(r => r.text());
    return { r1, r2, nRects: rects.length, toks: [...new Set(rects.map(r => r.tok))], label: meta.label };
  };
  // Page flip: mousedown + mouseup at the centre of the chevron — exactly one viewport per pair. (.click() is inert,
  // synthetic ArrowRight dies after any Aa-panel interaction, and the full 5-event pointer sequence double-fires.)
  K.press = (sel) => {
    const b = document.querySelector(sel);
    if (!b) return false;
    const r = b.getBoundingClientRect();
    const o = { bubbles: true, cancelable: true, clientX: r.left + r.width / 2, clientY: r.top + r.height / 2, button: 0 };
    b.dispatchEvent(new MouseEvent('mousedown', o)); b.dispatchEvent(new MouseEvent('mouseup', o));
    return true;
  };
  K.next = () => K.press('[aria-label="Next page"]');
  K.prev = () => K.press('[aria-label="Previous page"]');
  // Jump to a highlight by its DB start position via the annotations panel (items exist only after the panel opens;
  // the OPEN panel swallows page flips, so close it before sweeping).
  K.jump = async (pos) => {
    const open = [...document.querySelectorAll('[aria-label]')].find(e => e.getAttribute('aria-label') === 'Annotations');
    if (open) open.click();
    let it = null;
    for (let i = 0; i < 40 && !(it = document.querySelector('#notebook-grouped-item-' + pos)); i++) await K.sleep(250);
    if (!it) return { err: 'no panel item for ' + pos + ' (panel lists at most ~500 highlights)' };
    (it.querySelector('[data-testid=notebook-item-label]') || it).click();
    await K.sleep(900);
    const close = document.querySelector('[aria-label="Close Annotations"]');
    if (close) close.click();
    await K.sleep(1500);
    return { jumped: pos, label: K.label() };
  };
  // Flip → wait until the page <img> blob URL changes (new render) → settle → capture. Stops if the tab goes hidden.
  K.sweep = async (from, n, prefix) => {
    K.sweeping = true; K.sweepLog = K.sweepLog || [];
    for (let i = from; i < from + n; i++) {
      const before = K.imgSrc(), lb = K.label();
      K.next();
      const t0 = Date.now();
      while (K.imgSrc() === before && Date.now() - t0 < 6000) await K.sleep(150);
      await K.sleep(1300);
      const name = (prefix || 's') + String(i).padStart(3, '0');
      let r; try { r = await K.capture(name); } catch (e) { r = { err: String(e) }; }
      K.sweepLog.push({ i, name, changed: K.imgSrc() !== before, waited: Date.now() - t0, fromLabel: lb, label: r.label, toks: r.toks, nRects: r.nRects, err: r.err, vis: document.visibilityState });
      if (document.visibilityState !== 'visible') break;
    }
    K.sweeping = false;
  };
  // Display settings: write localStorage and reload (the transient Aa panel did not persist slider changes on one run).
  // fontSizeIndex 4 (17.6 px) + two columns is the verified OCR-friendly layout; restore from K.snapshot afterwards.
  K.applySettings = (fontIdx, cols) => {
    const s = JSON.parse(localStorage.getItem('KWR_Display_Settings') || '{}');
    if (fontIdx !== undefined) { s.fontSizeIndex = fontIdx; s.fontSize = { 0: 11, 2: 13.9, 4: 17.6, 6: 21 }[fontIdx] || s.fontSize; }
    if (cols !== undefined) s.maxNumberColumns = cols;
    localStorage.setItem('KWR_Display_Settings', JSON.stringify(s));
    setTimeout(() => location.reload(), 300);
    return JSON.stringify({ applied: s.fontSizeIndex, cols: s.maxNumberColumns, reloading: true });
  };
  K.restoreSettings = (snapshot) => {
    const snap = snapshot || K.snapshot;
    if (!snap) return 'no snapshot recorded — pass the string you saved from __kh.snapshot';
    localStorage.setItem('KWR_Display_Settings', snap);
    setTimeout(() => location.reload(), 300);
    return 'restored ' + snap.slice(0, 60) + '…';
  };
  K.last = null; K.sweepLog = [];
  return 'installed';
})()
