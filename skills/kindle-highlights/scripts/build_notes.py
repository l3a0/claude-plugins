#!/usr/bin/env python3
"""Build one combined, location-cited Markdown file from a Kindle notebook scrape.

Usage:
    python3 build_notes.py <highlights.json> <out.md> [completions.json]

- <highlights.json> is produced by extract_highlights.js (has .book and .highlights).
- <completions.json> (optional) maps "<loc>" -> recovered text. For a TRUNCATED
  highlight the value is the text AFTER the "…" (the full text is reconstructed as
  exact-prefix(minus "…") + joiner + completion, so the scraped prefix stays
  byte-exact). For a HIDDEN highlight (export limit withheld all text; scraped
  row has text=null, hidden=true) the value is the FULL text.

Fill EDITION / PUBLISHER / YEAR below for a complete citation (not on the notebook page).
Re-run any time; it's deterministic.
"""
import json
import os
import sys

EDITION = ""    # e.g. "2nd ed."
PUBLISHER = ""  # e.g. "McGraw-Hill"
YEAR = ""       # e.g. "2007"
RECOVERED_TAG = True  # set False to make recovered entries look identical to the rest


def reconstruct(text, completion):
    base = text[:-1].rstrip() if text.endswith("…") else text.rstrip()
    joiner = "" if completion[:1] in ".,;:!?)»”’-" else " "
    return base + joiner + completion


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    src, out = sys.argv[1], sys.argv[2]
    comp_path = sys.argv[3] if len(sys.argv) > 3 else None

    payload = json.load(open(src))
    book = payload.get("book", {})
    data = list(payload["highlights"])
    completions = {}
    if comp_path and os.path.exists(comp_path):
        completions = {int(k): v for k, v in json.load(open(comp_path)).items()}

    data.sort(key=lambda x: (x["loc"] is None, x["loc"]))
    n = len(data)
    n_hidden = sum(1 for x in data if x.get("hidden"))
    n_trunc = sum(1 for x in data if x["truncated"] and not x.get("hidden"))
    n_rec = sum(1 for x in data if (x["truncated"] or x.get("hidden")) and x["loc"] in completions)
    n_pending = (n_trunc + n_hidden) - n_rec

    colors = sorted({x["color"] for x in data if x["color"]})
    n_notes = sum(1 for x in data if x.get("note"))

    title = book.get("title") or "UNKNOWN TITLE"
    author = book.get("author") or "UNKNOWN AUTHOR"
    asin = book.get("asin") or ""
    cite_bits = ", ".join(b for b in [EDITION, PUBLISHER, YEAR] if b)
    cite = f"{author}, *{title}*" + (f", {cite_bits}" if cite_bits else "") + ", Kindle."

    color_note = ("all highlights " + colors[0]) if len(colors) == 1 else f"colors: {', '.join(colors)}"
    pend_note = f" ({n_pending} still pending, flagged ⚠ truncated)" if n_pending else ""
    hid_bit = f" and {n_hidden} hidden entirely" if n_hidden else ""
    trunc_note = (
        f" {n_trunc} of these were cut off by Amazon's export limit on the notebook page{hid_bit}; "
        f"their full text was recovered from the Kindle Cloud Reader"
        + (" and is marked with a `↻` tag" if RECOVERED_TAG else "")
        + f"{pend_note}."
    ) if n_trunc else ""

    L = [f"# {title} — Kindle Highlights", ""]
    L.append(f"**{author}**" + (f" · {cite_bits}" if cite_bits else "") + (f" · Kindle (ASIN {asin})" if asin else " · Kindle"))
    L.append("")
    L.append(f"{n} highlights · {n_notes} notes · {color_note}. Quoted verbatim and located by Kindle location number.{trunc_note}")
    L.append("")
    L.append(f"> **Full citation:** {cite} Each highlight below is cited by its Kindle location.")
    L.append("")
    L.append("---")
    L.append("")

    for x in data:
        loc, color = x["loc"], x["color"]
        hidden = bool(x.get("hidden"))
        is_rec = (x["truncated"] or hidden) and loc in completions
        still_trunc = x["truncated"] and not hidden and loc not in completions
        still_hidden = hidden and loc not in completions
        head = f"### Location {loc} · {color}"
        if is_rec and RECOVERED_TAG:
            head += " · ↻ recovered"
        elif still_trunc:
            head += " · ⚠ truncated"
        elif still_hidden:
            head += " · ⚠ hidden"
        L.append(head)
        L.append("")
        if is_rec:
            L.append("<!-- full text recovered from the Kindle Cloud Reader (export-limited on notebook page) -->")
            text = completions[loc] if hidden else reconstruct(x["text"], completions[loc])
        elif still_trunc:
            L.append(f"<!-- TRUNCATED loc={loc} full_text_pending -->")
            text = x["text"]
        elif still_hidden:
            L.append(f"<!-- HIDDEN loc={loc} full_text_pending -->")
            text = None
        else:
            text = x["text"]
        if text is None:
            quote = "> `[hidden by Amazon export limit — only the location number was exported; full text pending]`"
        else:
            quote = "> " + text
            if x.get("note"):
                quote += f"\n>\n> **Note:** {x['note']}"
            if still_trunc:
                quote += " `[truncated by Amazon export limit — full text pending]`"
        L.append(quote)
        L.append("")

    content = "\n".join(L).rstrip() + "\n"
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    open(out, "w").write(content)
    print(f"wrote {out}")
    print(f"total={n} truncated={n_trunc} hidden={n_hidden} recovered={n_rec} pending={n_pending}")


if __name__ == "__main__":
    main()
