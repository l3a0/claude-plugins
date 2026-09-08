#!/usr/bin/env python3
"""Calibrate the cutter on ground truth before trusting any blocked cut.

Run from the RUN DIRECTORY:   python3 validate.py s000 s001 ...

For every highlight token on the given captures it prints the length residual against the app-DB extent and, where
the notebook exported the text in full, the similarity to that text with the exact differences; for truncated
highlights it compares the known notebook prefix with the start of the OCR text. Byte-exact rates on the fully
exported highlights tell you the true error classes (column ordering, dropped lines, Greek letters) before any hidden
highlight is cut.
"""
import difflib, json, os, re, sys
from cutter import cut

RUN_DIR = os.getcwd()
A = json.load(open(os.path.join(RUN_DIR, 'aligned.json')))
BY_TOK = {f"{h['start']}/{h['end']}": h for h in A['highlights']}


def norm(s):
    return re.sub(r'\s+', ' ', s.replace('‘', "'").replace('’', "'").replace('“', '"').replace('”', '"').replace('–', '-').replace('—', '-')).strip()


def join_lines(lines):
    out = ''
    for l in lines:
        l = l.strip()
        if not l:
            continue
        out = l if not out else (out + l if out.endswith('-') else out + ' ' + l)
    return out


def main(names):
    agg = {}
    for n in names:
        for tok, v in cut(n).items():
            if v['lines']:
                agg.setdefault(tok, []).append(v['lines'])
    exact = total = 0
    for tok, parts in sorted(agg.items(), key=lambda kv: int(kv[0].split('/')[0])):
        h = BY_TOK.get(tok)
        text = join_lines([l for p in parts for l in p])
        if not h:
            print(f"{tok:15s} unknown token (not in aligned.json)")
            continue
        extent = h['end'] - h['start'] + 1
        status = 'hidden' if h['hidden'] else ('truncated' if h['truncated'] else 'full')
        line = f"{tok:15s} loc={h['loc']!s:5s} {status:9s} extent={extent:5d} len={len(text):5d} resid={extent - len(text):+d} caps={len(parts)}"
        if status == 'full':
            total += 1
            a, b = norm(h['text']), norm(text)
            sim = difflib.SequenceMatcher(None, a, b).ratio()
            exact += a == b
            print(line + f" sim={sim:.4f}")
            if sim < 0.999:
                for op in difflib.SequenceMatcher(None, a, b).get_opcodes():
                    if op[0] != 'equal':
                        print(f"      {op[0]:7s} truth={a[op[1]:op[2]]!r} ocr={b[op[3]:op[4]]!r}")
        elif status == 'truncated':
            pre = norm(h['text'][:-1] if h['text'].endswith('…') else h['text'])
            got = norm(text)[:len(pre)]
            sim = difflib.SequenceMatcher(None, pre, got).ratio()
            print(line + f" prefix-sim={sim:.4f}")
        else:
            print(line)
    if total:
        print(f"full highlights: {exact}/{total} byte-exact after normalization")


if __name__ == '__main__':
    main(sys.argv[1:])
