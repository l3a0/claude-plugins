#!/usr/bin/env python3
"""Inspect one blocked highlight: notebook prefix tail, the assembled text and its residual, and a crop of its
page region per capture and column (pages/crop_<loc>_<capture>_c<col>.png) to read by eye.

Run from the RUN DIRECTORY:   python3 inspect_highlight.py [-v] <loc> [<loc> ...]     (-v dumps the OCR lines too)
"""
import json, os, sys, glob, re, subprocess
from cutter import cut, PAGES, CROP
from assemble import H, BY_TOK, collect, best_text, assemble_one

def crop(png, box, out):
    r = subprocess.run([CROP, png, *[str(v) for v in box], out], capture_output=True, text=True)
    return r.stdout.strip() or r.stderr.strip()

def main(locs):
    names, agg = collect()
    for loc in locs:
        h = next(x for x in H if x['loc'] == loc)
        tok = f"{h['start']}/{h['end']}"
        extent = h['end'] - h['start'] + 1
        print('=' * 100)
        print(f"loc {loc} tok {tok} extent {extent} {'HIDDEN' if h['hidden'] else 'TRUNCATED'}")
        if h['text']:
            print('NOTEBOOK PREFIX TAIL:', '…' + h['text'][-260:])
        parts = agg.get(tok, [])
        for p in parts:
            meta = json.load(open(os.path.join(PAGES, p['cap'] + '.json')))
            rects = [r for r in meta['rects'] if r['tok'] == tok]
            small = [r for r in rects if r['hcss'] <= 45]
            big = [r for r in rects if r['hcss'] > 45]
            print(f"-- capture {p['cap']} label={meta['label']} rects={len(rects)} tall-rects={[(round(r['hcss']), round(r['w']*meta['canvas'][0])) for r in big]}")
            if VERBOSE:
                for l in p['lines']:
                    print('   |', l)
            if rects:
                x0 = min(r['x'] for r in rects); y0 = min(r['y'] for r in rects)
                x1 = max(r['x'] + r['w'] for r in rects); y1 = max(r['y'] + r['h'] for r in rects)
                # crop per column so the crop stays readable
                cols = sorted({0 if r['x'] < 0.5 else 1 for r in rects})
                for c in cols:
                    rs = [r for r in rects if (0 if r['x'] < 0.5 else 1) == c]
                    bx = (min(r['x'] for r in rs), min(r['y'] for r in rs), max(r['x'] + r['w'] for r in rs), max(r['y'] + r['h'] for r in rs))
                    out = os.path.join(PAGES, f"crop_{loc}_{p['cap']}_c{c}.png")
                    print('   crop:', crop(os.path.join(PAGES, p['cap'] + '.png'), bx, out))
        if parts:
            text, resid, st = assemble_one(h, parts)
            print(f"ASSEMBLED ({st}) resid={resid} len={len(text) if text else None}")
            print('   ', text)

VERBOSE = False
if __name__ == '__main__':
    VERBOSE = '-v' in sys.argv
    main([int(a) for a in sys.argv[1:] if a.isdigit()])
