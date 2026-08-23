/* Cloud Reader recovery snippets — run individually via
 * Control_Chrome.execute_javascript on the read.amazon.com/?asin=<ASIN> tab.
 * Each is a self-contained IIFE you can paste as the `code` argument.
 * Pages render as images, so these only NAVIGATE/MARK — you READ the text from
 * a computer-use screenshot + zoom.
 */

// 1) Dismiss the "Most Recent Page Read" dialog (click its "No").
(() => { const b = [...document.querySelectorAll('button,a,[role=button]')].find(x => (x.innerText || '').trim() === 'No'); if (b) b.click(); return JSON.stringify({ dismissed: !!b }); })()

// 2) Open the in-reader notebook (Annotations) panel.
(() => { const el = [...document.querySelectorAll('[aria-label],[title]')].find(e => (e.getAttribute('aria-label') || e.title) === 'Annotations'); if (el) el.click(); return JSON.stringify({ opened: !!el }); })()

// 3) List the notebook items' start positions, in order (line up 1:1 with the
//    scraped highlights sorted by location). Run once to build loc -> startPos.
(() => { const items = [...document.querySelectorAll('.notebook-content ion-item.notebook-editable-item')]; return JSON.stringify({ count: items.length, positions: items.map(it => Number((it.id || '').replace('notebook-grouped-item-', ''))).filter(Number.isFinite) }); })()

// 4) Navigate to a highlight (replace POS with its startPos). Also clears any prior outline.
(() => { document.querySelectorAll('[data-hloutline]').forEach(e => { e.style.outline = ''; e.removeAttribute('data-hloutline'); }); const it = document.querySelector('#notebook-grouped-item-' + POS); if (!it) return JSON.stringify({ err: 'no item' }); (it.querySelector('[data-testid=notebook-item-label]') || it).click(); return JSON.stringify({ navigated: POS }); })()

// 5) Page forward / back (chevron .click() is a no-op; synthetic ArrowRight/Left works).
//    NOTE: one key press advances the whole viewport — a 2-page spread in two-column
//    mode, one full-width page in single-column.
(() => { ['keydown', 'keyup'].forEach(t => document.dispatchEvent(new KeyboardEvent(t, { key: 'ArrowRight', code: 'ArrowRight', keyCode: 39, which: 39, bubbles: true }))); return JSON.stringify({ adv: 1 }); })()
(() => { ['keydown', 'keyup'].forEach(t => document.dispatchEvent(new KeyboardEvent(t, { key: 'ArrowLeft', code: 'ArrowLeft', keyCode: 37, which: 37, bubbles: true }))); return JSON.stringify({ back: 1 }); })()

// 6) Outline a highlight's EXACT extent in red (replace POS). Use when two highlights
//    are adjacent with no gap, to see precisely where one ends. Returns the start/end
//    position token; end == (next highlight's start - 1) when truly adjacent.
(() => { document.querySelectorAll('[data-hloutline]').forEach(e => { e.style.outline = ''; e.removeAttribute('data-hloutline'); }); const start = POS + '/'; const divs = [...document.querySelectorAll('.kg-client-highlight')].filter(d => [...d.classList].some(c => c.startsWith(start))); divs.forEach(d => { d.style.outline = '3px solid red'; d.setAttribute('data-hloutline', '1'); }); return JSON.stringify({ matched: divs.length, token: [...new Set(divs.flatMap(d => [...d.classList].filter(c => /^\d+\/\d+$/.test(c))))] }); })()

// 7) Snapshot the reader display settings — RECORD the output; you restore from it after
//    the run. Settings persist in origin-wide localStorage (key KWR_Display_Settings:
//    fontSizeIndex 0-13 where 0 = smallest, sideMarginsSize narrow|medium|wide,
//    maxNumberColumns 1|2), shared by EVERY read.amazon.com tab.
(() => localStorage.getItem('KWR_Display_Settings'))()

// 8) Apply display settings (replace FONT_IDX, 'MARGIN_LABEL' = Narrow|Medium|Wide,
//    'COLUMNS_LABEL' = Two Columns|Single Column; leave a placeholder unreplaced to
//    skip that knob — unmatched labels are just reported in `missed`). For scan density
//    use FONT_IDX = 0, 'Narrow', and skip columns: the reader re-paginates either
//    column mode to fill the window (owner-verified), so columns change paging
//    mechanics, not density. For the restore, re-run with the values recorded by 7.
//    The Aa panel is TRANSIENT (auto-closes between calls), so this is a
//    POLL: first call opens the panel and returns {panel:'opening'}; call again to apply.
//    Verify by re-running 7 — the slider path (value + ionInput/ionChange CustomEvents)
//    is live-verified to persist; the margin/column span-click uses the same UI pattern
//    but was not live-verified, so trust the readback, not the click.
(() => { const r = document.querySelector('ion-range.font-size-slider'); if (!r) { const b = document.querySelector('[aria-label="Reader settings"]'); if (b) b.click(); return JSON.stringify({ panel: 'opening - call again' }); } r.value = FONT_IDX; ['ionInput', 'ionChange'].forEach(t => r.dispatchEvent(new CustomEvent(t, { detail: { value: FONT_IDX }, bubbles: true }))); const missed = []; ['MARGIN_LABEL', 'COLUMNS_LABEL'].forEach(lbl => { const s = [...document.querySelectorAll('span[aria-checked]')].find(x => (x.textContent || '').trim() === lbl); if (!s) { missed.push(lbl); return; } if (s.getAttribute('aria-checked') !== 'true') s.click(); }); return JSON.stringify({ applied: true, fontIdx: FONT_IDX, missed }); })()
