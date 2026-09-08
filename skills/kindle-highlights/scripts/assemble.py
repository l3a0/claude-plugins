#!/usr/bin/env python3
"""Assemble the recovered text of every export-blocked highlight from the sweep captures.

Run from the RUN DIRECTORY (holds aligned.json from align_extents.py and pages/ from reader_capture.js):

    python3 assemble.py            # report only: residual vs the app-DB extent per blocked highlight
    python3 assemble.py --write    # also write completions.json (input for finalize.py)

Optional run-directory files:
  overrides.json   {"<loc>": "<full recovered text>"}   hand-transcribed replacements (used verbatim)
  fixes.json       [["<regex>", "<repl>"], ...]        systematic OCR slips verified against page crops

Per highlight it joins the OCR lines of every capture that shows the token, tries the join variants the
notebook stream demands (line-end hyphen kept/dropped, display-equation bodies stripped, list markers
stripped, boxed-sidebar code dropped) and keeps the variant whose length is closest to the DB extent.
Two OCR sources compete, page-scale and the 2x band re-OCR; ties within +-2 chars go to fewer
non-dictionary words. For a TRUNCATED highlight the notebook prefix is aligned (tail-anchored, so a
garbled drop-cap opener costs nothing) and only the completion after it is emitted.
"""
import glob, itertools, json, os, re, sys, difflib
from cutter import cut, recut, PAGES

RUN_DIR = os.getcwd()
A = json.load(open(os.path.join(RUN_DIR, 'aligned.json')))
H = A['highlights']
BY_TOK = {f"{h['start']}/{h['end']}": h for h in H}
OVERRIDES = json.load(open(os.path.join(RUN_DIR, 'overrides.json'))) if os.path.exists(os.path.join(RUN_DIR, 'overrides.json')) else {}
DICT = os.environ.get('KINDLE_DICT', '/usr/share/dict/words')

def norm(s):
    return re.sub(r'\s+', ' ', s.replace('‘', "'").replace('’', "'").replace('“', '"').replace('”', '"').replace('–', '-').replace('—', '-').replace('−', '-')).strip()

def typography(s):
    """Match the notebook's conventions: straight apostrophes, curly double quotes."""
    s = s.replace('‘', "'").replace('’', "'")
    # straight double quotes -> curly by position (opening after start/space/([ ; closing otherwise)
    out = []
    for i, ch in enumerate(s):
        if ch == '"':
            prev = s[i - 1] if i > 0 else ' '
            out.append('“' if prev in ' ([{—-/' else '”')
        else:
            out.append(ch)
    return ''.join(out)

EQ_LABEL = re.compile(r'^\((\d+\.\d+)\)\s+(.+)$')

def strip_equation_bodies(lines):
    """Display equations are not part of the notebook text stream, but their '(N.N)' labels are.
    Replace a line '(N.N) <body>' by '(N.N)' when the body looks like math. Returns (new_lines, n_stripped)."""
    out, n = [], 0
    prev_eq = False
    for l in lines:
        m = EQ_LABEL.match(l.strip())
        if m and (('=' in m.group(2)) or re.search(r'[Σ∑√∫≈≠±×·]|\b(log|exp|sqrt)\s*\(', m.group(2))):
            out.append(f'({m.group(1)})'); n += 1; prev_eq = True
        elif re.fullmatch(r'\((["“][^"”]*["”])\)', l.strip()):
            n += 1  # an equation's parenthesized annotation line (e.g. ("State transition")), not notebook text; OCR may order it before its label
        else:
            out.append(l); prev_eq = False
    return out, n

def join_variants(lines):
    """All ways to join lines at line-end hyphens (keep or drop), with and without equation bodies; yields (text, n_dropped)."""
    lines = [l.strip() for l in lines if l.strip()]
    variants = [lines]
    stripped, n_eq = strip_equation_bodies(lines)
    if n_eq:
        variants.insert(0, stripped)
    NUM = re.compile(r'^\d{1,2}\.\s+(?=[A-Z])')
    for v in list(variants):
        if any(NUM.match(l) for l in v):
            variants.append([NUM.sub('', l) for l in v])  # numbered list markers: not notebook text either
    for v in list(variants):
        if any(is_code_line(l) for l in v):
            variants.append([l for l in v if not is_code_line(l)])  # code inside boxed sidebars is a separate flow: not in the notebook stream
    for v in variants:
        yield from _join_variants(v)

CODE_HINT = re.compile(r"=@\(|\);\s*$|;\s*$|^function\b|^\w+\s*=\s*\w+\(|\.\*|\bend\s*$|^%")

def is_code_line(l):
    l = l.strip()
    words = [w.lower() for w in re.findall(r'[A-Za-z]{3,}', l)]
    dict_words = sum(1 for w in words if w in WORDS)
    if CODE_HINT.search(l):
        return dict_words <= max(2, len(words) // 3)
    # identifier-heavy continuation line: e.g. 'parseEarningsCalendarFromEarningsDotCom(prevDate,' / 'todaydate,allsyms)'
    idents = re.findall(r'[A-Za-z_][A-Za-z0-9_]*', l)
    return bool(idents) and dict_words == 0 and bool(re.search(r'[(),_]', l)) and ' ' not in l.replace(', ', ',')

BULLET = re.compile(r'^[•■▪◦●]\s*')

def _join_variants(lines):
    lines = [BULLET.sub('', l) for l in lines]  # list markers are neither in the notebook text nor on the position ruler
    hy = [i for i in range(len(lines) - 1) if lines[i].endswith('-')]
    if len(hy) > 8:  # too many to enumerate; keep hyphens
        hy = []
    for drop in itertools.product([False, True], repeat=len(hy)):
        dmap = dict(zip(hy, drop))
        out = ''
        for i, l in enumerate(lines):
            if not out:
                out = l
            elif out.endswith('-') and (i - 1) in dmap:
                out = (out[:-1] if dmap[i - 1] else out) + l
            else:
                out = out + ' ' + l
        yield out, sum(drop)

def collect():
    names = sorted(os.path.basename(p)[:-5] for p in glob.glob(os.path.join(PAGES, '*.json'))
                   if re.fullmatch(r'[a-z]\d{3}', os.path.basename(p)[:-5]) and os.path.exists(p[:-5] + '.png'))
    agg = {}
    for n in names:
        c = cut(n)
        for tok, v in c.items():
            if v['lines']:
                agg.setdefault(tok, []).append({'cap': n, 'lines': v['lines'], 'lines_gf': v.get('lines_gf')})
    # A resumed sweep (next series letter, e.g. s -> t) re-captures the tail of the last screen of the
    # previous series, and a different window layout OCRs it slightly differently. Where a token has parts
    # in two consecutive series, drop the earlier part's tail that the later part re-captures (fuzzy).
    for tok, parts in agg.items():
        series = sorted({p['cap'][0] for p in parts})
        for s1, s2 in zip(series, series[1:]):
            sp = [p for p in parts if p['cap'][0] == s1]; tp = [p for p in parts if p['cap'][0] == s2]
            s_text = ' '.join(l for p in sp for l in p['lines']); t_text = ' '.join(l for p in tp for l in p['lines'])
            k = _overlap(s_text, t_text)
            if k >= len(s_text) - 5:
                parts = [p for p in parts if p['cap'][0] != s1]
            elif k >= 20:
                keep = s_text[:len(s_text) - k].rstrip()
                parts = [{'cap': sp[0]['cap'], 'lines': [keep], 'lines_gf': None}] + [p for p in parts if p['cap'][0] != s1]
        agg[tok] = parts
    return names, agg

def _overlap(a, b):
    """How many trailing chars of a are re-captured at the start of b (fuzzy, tolerates OCR slips between two renders).
    Anchors the last 60 chars of a inside the head of b; returns the covered length of a, or 0 if a's tail is not in b."""
    an, bn = norm(a), norm(b)
    if not an or not bn:
        return 0
    tail = an[-60:]
    head = bn[:len(an) + 200]
    sm = difflib.SequenceMatcher(None, tail, head, autojunk=False)
    m = sm.find_longest_match(0, len(tail), 0, len(head))
    if m.size < 25:
        return 0
    end_in_b = m.b + m.size + (len(tail) - (m.a + m.size))  # where a's tail ends inside b
    return min(len(an), end_in_b)

def best_text(tok, parts, h):
    extent = h['end'] - h['start'] + 1
    lines = [l for p in parts for l in p['lines']]
    cands = list(join_variants(lines))
    if any(p.get('lines_gf') for p in parts):
        lines_gf = [l for p in parts for l in (p.get('lines_gf') or p['lines'])]
        cands += list(join_variants(lines_gf))
    if h['truncated'] and not h['hidden']:
        pre = h['text'][:-1] if h['text'].endswith('…') else h['text']
        need = extent - len(pre)
        best = None
        for text, nd in cands:
            comp = completion_after_prefix(pre, text)
            if comp is None:
                continue
            r = need - len(comp)
            if best is None or abs(r) < abs(best[0]):
                best = (r, comp, text, nd)
        if best is None:
            return None, None, 'prefix-not-found'
        return best[1], best[0], 'ok'
    else:
        best = min(cands, key=lambda c: abs(extent - len(c[0])))
        return best[0], extent - len(best[0]), 'ok'

def completion_after_prefix(pre, text):
    """Align the TAIL of the (normalized) prefix against the OCR text and return the text after the prefix end.
    Tail-anchoring tolerates heavy OCR garble earlier in the prefix (drop-cap chapter openers)."""
    a = norm(pre)
    b = re.sub(r'\s+', ' ', text).strip(); bn = norm(b)
    assert len(bn) == len(b)
    tail = a[-min(len(a), 220):]
    sm = difflib.SequenceMatcher(None, tail, bn, autojunk=False)
    blocks = [bl for bl in sm.get_matching_blocks() if bl.size > 0]
    if not blocks:
        return None
    matched = sum(bl.size for bl in blocks)
    if matched < 0.6 * len(tail):
        return None
    last = blocks[-1]
    end_b = last.b + last.size + (len(tail) - (last.a + last.size))  # extend by any unmatched tail remainder
    end_b = max(0, min(len(b), end_b))
    # snap to a word edge only when the alignment landed mid-word (letter|letter); never past an opening bracket or space
    while 0 < end_b < len(b) and b[end_b - 1].isalnum() and b[end_b].isalnum():
        end_b += 1
    return b[end_b:].strip()

WORDS = set(w.strip().lower() for w in open(DICT)) if os.path.exists(DICT) else set()

def nonword_count(text):
    n = 0
    for w in re.findall(r"[A-Za-z']+", text):
        a = w.lower().strip("'")
        if len(a) > 2 and a not in WORDS and a.rstrip('s') not in WORDS:
            n += 1
    return n

def assemble_one(h, parts):
    """Best recovered text for one blocked highlight. Two OCR sources compete: the plain page OCR and a 2x band re-OCR of the
    highlight's own rects (which recovers lines Vision drops at page scale and reads the shaded Example boxes better).
    Pick by |extent residual| first, then by fewer non-dictionary words. Returns (text, resid, status)."""
    tok = f"{h['start']}/{h['end']}"
    cands = []
    text, resid, st = best_text(tok, parts, h)
    if text is not None:
        cands.append((abs(resid), nonword_count(text), text, resid, st))
    rparts = []
    for p in parts:
        rc = recut(p['cap'], tok)
        rparts.append({'cap': p['cap'], 'lines': rc['lines'] if rc and rc['lines'] else p['lines'], 'lines_gf': (rc or {}).get('lines_gf')})
    t2, r2, s2 = best_text(tok, rparts, h)
    if t2 is not None:
        cands.append((abs(r2), nonword_count(t2), t2, r2, s2 + '+recut'))
    if not cands:
        return None, None, st
    # tolerance: residuals within ±2 are equivalent; then prefer fewer non-words
    cands.sort(key=lambda c: (min(c[0], 2), c[1], c[0]))
    _, _, text, resid, st = cands[0]
    text = apply_fixes(typography(text))
    return text, resid, st

FIXES = [(re.compile(p), r) for p, r in json.load(open(os.path.join(RUN_DIR, 'fixes.json')))] if os.path.exists(os.path.join(RUN_DIR, 'fixes.json')) else []

def apply_fixes(text):
    """Systematic OCR slips verified against the page images (fixes.json: [regex, replacement])."""
    for p, r in FIXES:
        text = p.sub(r, text)
    return text

def main(write=False):
    names, agg = collect()
    completions = {}
    report = []
    for h in H:
        if not (h['truncated'] or h['hidden']):
            continue
        tok = f"{h['start']}/{h['end']}"
        if str(h['loc']) in OVERRIDES:
            completions[str(h['loc'])] = OVERRIDES[str(h['loc'])]
            report.append((h['loc'], tok, 'override', 0, 0, ''))
            continue
        parts = agg.get(tok)
        if not parts:
            report.append((h['loc'], tok, 'MISSING', None, 0, ''))
            continue
        text, resid, st = assemble_one(h, parts)
        if text is None:
            report.append((h['loc'], tok, st, None, len(parts), ''))
            continue
        completions[str(h['loc'])] = text
        report.append((h['loc'], tok, 'hidden' if h['hidden'] else 'trunc', resid, len(parts), text[:60]))
    if write:
        json.dump(completions, open(os.path.join(RUN_DIR, 'completions.json'), 'w'), indent=1, ensure_ascii=False)
    n_ok = sum(1 for r in report if r[3] is not None and abs(r[3]) <= 2)
    n_bad = [r for r in report if r[3] is None or abs(r[3]) > 2]
    print(f"captures={len(names)} blocked={len(report)} within±2={n_ok} needs-attention={len(n_bad)}")
    for r in n_bad:
        print('  ', r[:5])
    return report

if __name__ == '__main__':
    main('--write' in sys.argv)
