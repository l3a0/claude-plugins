#!/usr/bin/env python3
"""Finalize the export: completions.json -> per-location fixes -> build_notes.py -> approximate tags -> QA checks.

Run from the RUN DIRECTORY:

    python3 finalize.py <out.md> [--highlights pages/<asin>_highlights.json] [--edition "2nd ed."] [--publisher Wiley] [--year 2013] [--strict]

Optional run-directory files:
  loc_fixes.json   {"<loc>": [["<regex>", "<repl>"], ...]}   corrections for ONE highlight, verified against its crop
  approx.json      [<loc>, ...]                               spans crossing a table, figure or display equation: tagged "≈ approximate"

A WARN line means a loc_fixes.json pattern no longer matches the assembler's current output. Treat it as a stop:
re-key the pattern or drop it. --strict turns those warnings into a non-zero exit.
"""
import argparse, json, os, re, subprocess, sys
SCRIPTS = os.path.dirname(os.path.abspath(__file__))
RUN_DIR = os.getcwd()
ap = argparse.ArgumentParser()
ap.add_argument('out')
ap.add_argument('--highlights', default=None, help='scrape JSON from extract_highlights.js (default pages/<asin>_highlights.json)')
ap.add_argument('--edition', default=''); ap.add_argument('--publisher', default=''); ap.add_argument('--year', default='')
ap.add_argument('--strict', action='store_true', help='exit non-zero when a loc_fixes.json pattern matched nothing')
opts = ap.parse_args()
C = json.load(open(os.path.join(RUN_DIR, 'completions.json')))
LOCFIX = json.load(open(os.path.join(RUN_DIR, 'loc_fixes.json'))) if os.path.exists(os.path.join(RUN_DIR, 'loc_fixes.json')) else {}
APPROX = json.load(open(os.path.join(RUN_DIR, 'approx.json'))) if os.path.exists(os.path.join(RUN_DIR, 'approx.json')) else []
A = json.load(open(os.path.join(RUN_DIR, 'aligned.json')))
H = {str(h['loc']): h for h in A['highlights']}
HL_JSON = opts.highlights or os.path.join(RUN_DIR, 'pages', f"{A['book']['asin']}_highlights.json")

final = {}
MISSED = 0
for loc, t in C.items():
    for pat, rep in LOCFIX.get(loc, []):
        t2 = re.sub(pat, rep, t)
        if t2 == t:
            MISSED += 1
            print(f"WARN loc {loc}: fix {pat!r} matched nothing")
        t = t2
    final[loc] = t
json.dump(final, open(os.path.join(RUN_DIR, 'completions_final.json'), 'w'), indent=1, ensure_ascii=False)

out = opts.out
cmd = [sys.executable, os.path.join(SCRIPTS, 'build_notes.py'), HL_JSON, out, os.path.join(RUN_DIR, 'completions_final.json')]
for k in ('edition', 'publisher', 'year'):
    if getattr(opts, k):
        cmd += [f'--{k}', getattr(opts, k)]
r = subprocess.run(cmd, capture_output=True, text=True)
print(r.stdout.strip()); print(r.stderr.strip())

md = open(out).read()
for loc in APPROX:
    m = re.search(rf"^### Location {loc} · \w+ · ↻ recovered$", md, re.M)  # the colour is whatever build_notes wrote
    if not m:
        sys.exit(f"approx.json lists loc {loc}, which is not a recovered section in {out}")
    md = md.replace(m.group(0), m.group(0) + " · ≈ approximate")
if APPROX:
    md = md.replace("and is marked with a `↻` tag.", "and is marked with a `↻` tag. A few spans that cross a table, a figure or a display equation are tagged `≈`. Their text is faithful. The exact boundaries are best-effort.")
md = md.rstrip('\n') + '\n'
open(out, 'w').write(md)

# ---- QA ----
print('--- QA')
if MISSED:
    print(f'loc fixes that matched nothing: {MISSED} (stale patterns — re-key them against the current assemble output, or drop the ones the recut path made redundant)')
    if opts.strict:
        sys.exit('stale loc_fixes.json: re-key the patterns, or drop --strict to accept')
secs = re.findall(r'^### Location (\d+)', md, re.M)
print('sections', len(secs), 'unique', len(set(secs)))
print('pending markers', md.count('full_text_pending'), '| stray «', md.count('«'), '| ellipsis in body', sum(1 for l in md.splitlines() if l.startswith('> ') and '…' in l))
bad = []
for loc, t in final.items():
    h = H[loc]
    full = t if h['hidden'] else ((h['text'][:-1].rstrip() if h['text'].endswith('…') else h['text'].rstrip()) + ('' if t[:1] in '.,;:!?)»”’-' else ' ') + t)
    if '  ' in full: bad.append((loc, 'double space'))
    m = re.search(r'\b(\w+) \1\b', full)
    if m and m.group(1).lower() not in ('that', 'had', 'is'): bad.append((loc, 'doubled word ' + m.group(0)))
    if re.search(r'\w-\s', full) and not re.search(r'\w- ', h['text'] or ''): pass
    if re.search(r'[a-z]-[A-Z]', full): bad.append((loc, 'hyphen-case seam'))
    if full.endswith(('-', '(', ',')): bad.append((loc, 'odd ending ' + full[-12:]))
    ex = h['end'] - h['start'] + 1
    if abs(ex - len(full)) > 3: bad.append((loc, f'residual {ex - len(full)}'))
for b in bad: print('  QA', b)
print('trailing newline ok', md.endswith('\n') and not md.endswith('\n\n'))
