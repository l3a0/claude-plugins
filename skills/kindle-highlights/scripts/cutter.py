#!/usr/bin/env python3
"""Word-rect cutter: assign OCR words (with boxes) to the reader's word-level highlight overlay rects, per screen.

Run from the RUN DIRECTORY (the folder holding pages/ with the reader_capture.js captures:
<name>.png + <name>.json per screen, where <name> is a series letter + 3 digits, e.g. s000).

    python3 cutter.py s000 s001 ...      # prints per-token lines; caches OCR in pages/<name>.ocr.jsonl

Each capture's OCR runs once (ocr_words.swift, per-word boxes). cut() returns, per highlight token
"<start>/<end>", the OCR lines whose words fall inside that token's rects, ordered left column first,
then top to bottom. recut() re-OCRs one token's own band at 2x magnification (crop.swift) -- Vision
drops whole body-text lines at page scale and reads shaded Example boxes badly; the magnified band
recovers both. Both binaries are compiled on first use from the .swift sources next to this file.
"""
import json, os, subprocess, sys

SCRIPTS = os.path.dirname(os.path.abspath(__file__))
RUN_DIR = os.getcwd()
PAGES = os.path.join(RUN_DIR, 'pages')
MAX_RECT_H_CSS = 45  # figure-wrapping rects are much taller than a word box


def ensure_bin(name):
    """Compile <name>.swift (next to this script) into bin/<name> once; return the binary path."""
    bin_dir = os.path.join(SCRIPTS, 'bin')
    os.makedirs(bin_dir, exist_ok=True)
    out = os.path.join(bin_dir, name)
    src = os.path.join(SCRIPTS, name + '.swift')
    if not os.path.exists(out) or os.path.getmtime(out) < os.path.getmtime(src):
        subprocess.run(['swiftc', '-O', src, '-o', out], check=True)
    return out


OCR = ensure_bin('ocr_words')
CROP = ensure_bin('crop')

def ocr(name):
    out = os.path.join(PAGES, name + '.ocr.jsonl')
    if not os.path.exists(out):
        tmp = out + '.tmp'
        with open(tmp, 'w') as f:
            subprocess.run([OCR, os.path.join(PAGES, name + '.png')], stdout=f, check=True)
        os.replace(tmp, out)
    return [json.loads(l) for l in open(out) if l.strip()]

def assign(lines, rects):
    """Assign OCR words (page-normalized boxes) to overlay rects by center containment; return {tok: {lines, nwords, line_idx, nrects}}."""
    by_tok = {}
    for r in rects:
        by_tok.setdefault(r['tok'], []).append(r)
    result = {}
    for li, L in enumerate(lines):
        for wi, w in enumerate(L['words']):
            if w['x0'] < 0:
                continue
            cx, cy = (w['x0'] + w['x1']) / 2, (w['y0'] + w['y1']) / 2
            best = None
            for r in rects:
                sx, sy = r['w'] * 0.05, r['h'] * 0.25
                if r['x'] - sx <= cx <= r['x'] + r['w'] + sx and r['y'] - sy <= cy <= r['y'] + r['h'] + sy:
                    ov = min(w['x1'], r['x'] + r['w']) - max(w['x0'], r['x'])
                    if best is None or ov > best[0]:
                        best = (ov, r['tok'])
            if best:
                result.setdefault(best[1], []).append((li, wi, w['t'], w['x0'], w['x1'], w['y0']))
    col_of = lambda li: 0 if (lines[li]['x0'] + lines[li]['x1']) / 2 < 0.5 else 1  # two-column page: left column first
    # gap-fill (conservative, returned as a separate variant): a highlight is contiguous, so when two consecutive
    # assigned lines of one token (same column) are separated by a gap of k>=1 whole body-text lines, and exactly k
    # OCR lines assigned to NO token sit in that gap with body-text height and the column's left edge, they are lines
    # whose overlay rects the reader failed to paint. Code boxes / figures fail the height + left-edge test.
    assigned_lines = {li for ws in result.values() for (li, *_rest) in ws}
    heights = sorted(L['y1'] - L['y0'] for L in lines if L['words'])
    body_h = heights[len(heights) // 2] if heights else 0.02
    gf = {tok: list(ws) for tok, ws in result.items()}
    for tok, ws in gf.items():
        tl = sorted({li for (li, *_rest) in ws}, key=lambda li: (col_of(li), lines[li]['y0']))
        for a, b in zip(tl, tl[1:]):
            if col_of(a) != col_of(b):
                continue
            gap = lines[b]['y0'] - lines[a]['y0']
            pitch = None
            # estimate the line pitch from the token's own consecutive lines when possible, else 1.35 * body height
            pitch = body_h * 1.35
            k = round(gap / pitch) - 1
            if k < 1 or k > 3:
                continue
            between = [li for li, L in enumerate(lines) if li not in assigned_lines and col_of(li) == col_of(a)
                       and lines[a]['y0'] < L['y0'] < lines[b]['y0'] and L['words']
                       and abs((L['y1'] - L['y0']) - body_h) < 0.25 * body_h and abs(L['x0'] - lines[a]['x0']) < 0.02]
            if len(between) != k:
                continue
            for li in between:
                for wi, w in enumerate(lines[li]['words']):
                    if w['x0'] >= 0:
                        ws.append((li, wi, w['t'], w['x0'], w['x1'], w['y0']))
                assigned_lines.add(li)
    def to_lines(ws):
        ws = sorted(ws, key=lambda t: (col_of(t[0]), lines[t[0]]['y0'], t[3]))
        by_line = {}
        for (li, wi, t, x0, x1, y0) in ws:
            by_line.setdefault(li, []).append(t)
        lidx = sorted(by_line, key=lambda li: (col_of(li), lines[li]['y0']))
        return [' '.join(by_line[li]) for li in lidx], lidx
    out = {}
    for tok, ws in result.items():
        ls, lidx = to_lines(ws)
        ls_gf, _ = to_lines(gf[tok])
        out[tok] = {'lines': ls, 'lines_gf': ls_gf if ls_gf != ls else None, 'nwords': len(ws), 'line_idx': lidx, 'nrects': len(by_tok.get(tok, []))}
    for tok in by_tok:
        if tok not in out:
            out[tok] = {'lines': [], 'lines_gf': None, 'nwords': 0, 'line_idx': [], 'nrects': len(by_tok[tok])}
    return out

def cut(name, verbose=False):
    meta = json.load(open(os.path.join(PAGES, name + '.json')))
    lines = ocr(name)
    rects = [r for r in meta['rects'] if r['hcss'] <= MAX_RECT_H_CSS]
    out = assign(lines, rects)
    json.dump(out, open(os.path.join(PAGES, name + '.cut.json'), 'w'), indent=1, ensure_ascii=False)
    if verbose:
        for tok, v in sorted(out.items(), key=lambda kv: int(kv[0].split('/')[0])):
            print(tok, 'rects', v['nrects'], 'words', v['nwords'], 'lines', len(v['lines']))
            for l in v['lines']:
                print('   ', l[:110])
    return out

def recut(name, tok, scale=2.0):
    """Re-OCR just this token's band(s) at `scale`x magnification (per column) and re-assign.
    Returns the same shape as cut()[tok]. Cached in pages/recut_<name>_<tok>.json."""
    cache = os.path.join(PAGES, f'recut_{name}_{tok.replace("/", "-")}.json')
    if os.path.exists(cache):
        return json.load(open(cache))
    r = _recut(name, tok, scale)
    json.dump(r, open(cache, 'w'), ensure_ascii=False)
    return r

def _recut(name, tok, scale=2.0):
    meta = json.load(open(os.path.join(PAGES, name + '.json')))
    rects = [r for r in meta['rects'] if r['tok'] == tok and r['hcss'] <= MAX_RECT_H_CSS]
    if not rects:
        return None
    lines = []
    for col in (0, 1):
        rs = [r for r in rects if (r['x'] < 0.5) == (col == 0)]
        if not rs:
            continue
        bx = (min(r['x'] for r in rs), min(r['y'] for r in rs), max(r['x'] + r['w'] for r in rs), max(r['y'] + r['h'] for r in rs))
        out_png = os.path.join(PAGES, f'recut_{name}_{tok.replace("/", "-")}_c{col}.png')
        g = json.loads(subprocess.run([CROP, os.path.join(PAGES, name + '.png'), *[str(v) for v in bx], out_png, str(scale), '40'], capture_output=True, text=True, check=True).stdout)  # 40 px pad: less clips the first glyph of each line
        res = subprocess.run([OCR, out_png], capture_output=True, text=True, check=True).stdout
        W, Hh = g['W'], g['H']
        for l in res.splitlines():
            if not l.strip():
                continue
            L = json.loads(l)
            # map crop-normalized -> page-normalized (crop covers pixels [x0, x0+w] x [y0, y0+h] of the page)
            mx = lambda v: (g['x0'] + v * g['w']) / W
            my = lambda v: (g['y0'] + v * g['h']) / Hh
            L['x0'], L['x1'], L['y0'], L['y1'] = mx(L['x0']), mx(L['x1']), my(L['y0']), my(L['y1'])
            for w in L['words']:
                if w['x0'] >= 0:
                    w['x0'], w['x1'], w['y0'], w['y1'] = mx(w['x0']), mx(w['x1']), my(w['y0']), my(w['y1'])
            lines.append(L)
    lines.sort(key=lambda L: (L['y0'], L['x0']))
    return assign(lines, rects).get(tok)

if __name__ == '__main__':
    for n in sys.argv[1:]:
        cut(n, verbose=True)
