#!/usr/bin/env python3
"""
Build dark_mode.svg and light_mode.svg from ascii.txt + config.py + stats.json.

    python3 generate.py                     # build both SVGs
    python3 generate.py --list-vars         # print every available $placeholder
    python3 generate.py --invert FILE       # flip art's density ramp, to stdout

If stats.json is missing, placeholder values are used so the card still builds
(handy for tweaking layout without burning API calls).
"""

import html
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from string import Template

import config

HERE = Path(__file__).parent
STATS_FILE = HERE / "stats.json"

FALLBACK = {
    "login": config.GITHUB_USER, "name": config.GITHUB_USER,
    "repos": 0, "contributed": 0, "stars": 0, "followers": 0, "following": 0,
    "commits": 0, "commits_this_year": 0, "contributions_total": 0,
    "loc_added": 0, "loc_deleted": 0, "loc_net": 0,
    "top_repo": "—", "top_repo_stars": 0,
    "languages": [], "updated": "never",
}


# ──────────────────────────────────────────────────────────────────
#  helpers
# ──────────────────────────────────────────────────────────────────

def uptime(birth: date) -> str:
    today = date.today()
    y, m, d = today.year - birth.year, today.month - birth.month, today.day - birth.day
    if d < 0:
        m -= 1
        d += (today.replace(day=1) - timedelta(days=1)).day
    if m < 0:
        m += 12
        y -= 1

    def p(n, w):
        return f"{n} {w}" + ("" if n == 1 else "s")

    return f"{p(y, 'year')}, {p(m, 'month')}, {p(d, 'day')}"


def esc(s: str) -> str:
    return html.escape(str(s), quote=False)


def load_stats() -> dict:
    if STATS_FILE.exists():
        try:
            return {**FALLBACK, **json.loads(STATS_FILE.read_text())}
        except json.JSONDecodeError:
            print("stats.json is not valid JSON — using placeholders", file=sys.stderr)
    else:
        print("stats.json not found — using placeholders", file=sys.stderr)
    return dict(FALLBACK)


def build_subs(stats: dict) -> dict:
    """Every $placeholder available inside config.INFO."""
    subs = {k: v for k, v in stats.items() if not isinstance(v, (list, dict))}
    for key in ("repos", "stars", "followers", "following", "commits",
                "commits_this_year", "contributions_total",
                "loc_added", "loc_deleted", "loc_net"):
        subs[key] = f"{stats.get(key, 0):,}"
    subs["uptime"] = uptime(config.BIRTH_DATE)
    subs["today"] = date.today().isoformat()
    return subs


def sub(text: str, subs: dict) -> str:
    """$placeholder substitution that leaves unknown names alone."""
    return Template(text).safe_substitute(subs)


# ──────────────────────────────────────────────────────────────────
#  line building
# ──────────────────────────────────────────────────────────────────

def span(text, colour, bold=False):
    b = ' font-weight="bold"' if bold else ""
    return f'<tspan fill="{colour}"{b}>{esc(text)}</tspan>'


def entry_width(entry, subs, stats) -> int:
    """Minimum visible columns an entry needs."""
    kind = entry[0]
    if kind == "gap":
        return 0
    if kind == "sec":
        return len(f" - {entry[1]} ") + 8
    if kind == "kv":
        return len(f" . {entry[1]}:") + len(sub(entry[2], subs)) + 5
    if kind == "loc":
        tail = f" {stats['loc_net']:,} ( {stats['loc_added']:,}++, {stats['loc_deleted']:,}-- )"
        return len(" . Lines of Code:") + len(tail) + 4
    if kind == "langs":
        return 3 + config.LANG_NAME_W + 1 + config.BAR_COLS + 8
    return 0


def build_lines(width, colours, subs, stats):
    """
    Returns (lines, bars) where lines is a list of tspan-body strings and bars
    is a list of (row_index, pct, colour) for language bars drawn as rects.
    """
    lines, bars = [], []

    def dotted(left, value_spans, plain_len):
        ndots = max(width - len(left) - plain_len - 2, 1)
        return (span(left, colours["key"])
                + span(" " + "." * ndots, colours["dots"])
                + "".join(value_spans))

    for entry in config.INFO:
        kind = entry[0]

        if kind == "gap":
            lines.append("")

        elif kind == "sec":
            left = f" - {entry[1]} "
            lines.append(span(left, colours["sec"])
                         + span("-" * max(width - len(left), 0), colours["rule"]))

        elif kind == "kv":
            value = sub(entry[2], subs)
            lines.append(dotted(f" . {entry[1]}:",
                                [span(" " + value, colours["value"])],
                                len(value)))

        elif kind == "loc":
            net = f"{stats['loc_net']:,}"
            added = f"{stats['loc_added']:,}++"
            removed = f"{stats['loc_deleted']:,}--"
            plain = len(f" {net} ( {added}, {removed} )")
            lines.append(dotted(
                " . Lines of Code:",
                [span(f" {net} ( ", colours["value"]),
                 span(added, colours["add"]),
                 span(", ", colours["value"]),
                 span(removed, colours["del"]),
                 span(" )", colours["value"])],
                plain,
            ))

        elif kind == "langs":
            limit = entry[1] if len(entry) > 1 else 5
            langs = stats.get("languages", [])[:limit]
            if not langs:
                lines.append(span(" . (no language data yet)", colours["dots"]))
                continue
            for lang in langs:
                name = lang["name"][:config.LANG_NAME_W]
                pct = f"{lang['pct']:.1f}%"
                # name column, then blank space where the bar rect is drawn,
                # then the percentage.
                left = f" . {name:<{config.LANG_NAME_W}} "
                gap = " " * config.BAR_COLS
                tail_pad = max(width - len(left) - config.BAR_COLS - len(pct) - 1, 1)
                lines.append(
                    span(left, colours["value"])
                    + f'<tspan>{gap}</tspan>'
                    + span(" " * tail_pad + pct, colours["value"])
                )
                bars.append((len(lines) - 1, lang["pct"], lang["color"]))

    return lines, bars


# ──────────────────────────────────────────────────────────────────
#  rendering
# ──────────────────────────────────────────────────────────────────

def render(theme, art_lines, art_cols, art_rows, info_cols, subs, stats):
    c = config.THEMES[theme]
    cw, lh, pad = config.CHAR_W, config.LINE_HEIGHT, config.PAD
    stacked = getattr(config, "LAYOUT", "side") == "stacked"

    lines, bars = build_lines(info_cols, c, subs, stats)
    info_rows = len(lines) + 1                    # +1 for the prompt line

    y0 = pad + config.FONT_SIZE
    art_x = pad

    if stacked:
        # Art above, info below. Width is max() rather than sum(), which is
        # what actually makes the text render larger on GitHub.
        info_x = pad
        art_y = y0
        info_y = y0 + (art_rows + 1) * lh if art_lines else y0
        total_cols = max(art_cols, info_cols)
        total_rows = (art_rows + 1 if art_lines else 0) + info_rows
    else:
        info_x = pad + (art_cols + config.GAP_COLS) * cw
        art_y = info_y = y0
        total_cols = art_cols + config.GAP_COLS + info_cols
        total_rows = max(art_rows, info_rows)

    width = round(pad * 2 + total_cols * cw)
    height = round(pad * 2 + total_rows * lh)

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family=\'{config.FONT_STACK}\' '
        f'font-size="{config.FONT_SIZE}">',
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="10" '
        f'fill="{c["bg"]}" stroke="{c["border"]}"/>',
    ]

    # ASCII art
    if art_lines:
        out.append(f'<text x="{art_x}" y="{art_y}" fill="{c["ascii"]}" xml:space="preserve">')
        for i, line in enumerate(art_lines):
            out.append(f'<tspan x="{art_x}" dy="{0 if i == 0 else lh}">{esc(line) or " "}</tspan>')
        out.append("</text>")

    # language bars (drawn under the text so the percentage stays crisp)
    bar_x = info_x + (3 + config.LANG_NAME_W + 1) * cw
    bar_w = config.BAR_COLS * cw
    bar_h = 9
    for row, pct, colour in bars:
        # row 0 of `lines` is the line after the prompt line
        cy = info_y + (row + 1) * lh
        by = cy - config.FONT_SIZE * 0.72
        out.append(f'<rect x="{bar_x:.1f}" y="{by:.1f}" width="{bar_w:.1f}" '
                   f'height="{bar_h}" rx="{bar_h/2}" fill="{c["bartrack"]}"/>')
        fill_w = max(bar_w * pct / 100, 2)
        out.append(f'<rect x="{bar_x:.1f}" y="{by:.1f}" width="{fill_w:.1f}" '
                   f'height="{bar_h}" rx="{bar_h/2}" fill="{colour}"/>')

    # info column
    out.append(f'<text x="{info_x}" y="{info_y}" xml:space="preserve">')
    rule = "-" * max(info_cols - len(config.PROMPT) - 1, 0)
    out.append(
        f'<tspan x="{info_x}" dy="0">'
        + span(config.PROMPT, c["prompt"], bold=True)
        + span(" " + rule, c["rule"])
        + "</tspan>"
    )
    for line in lines:
        out.append(f'<tspan x="{info_x}" dy="{lh}">{line or " "}</tspan>')
    out.append("</text>")

    out.append("</svg>")
    return "\n".join(out)


# ──────────────────────────────────────────────────────────────────
#  ASCII art loading
# ──────────────────────────────────────────────────────────────────

# Heaviest -> lightest. Space is deliberately NOT in the ramp: it's background,
# and mapping it to '@' would flood the card.
RAMP = "@%#*+=-:."


def invert_art(text: str) -> str:
    """
    Reverse the density ramp: the heaviest character becomes the lightest and
    vice versa, leaving spaces (background) and everything outside the ramp
    untouched. Turns a density portrait drawn for a dark background into one
    that reads correctly on a light background.
    """
    table = {c: RAMP[len(RAMP) - 1 - i] for i, c in enumerate(RAMP)}
    return "".join(table.get(ch, ch) for ch in text)


def load_art(theme: str):
    """Art for one theme, falling back to the shared ASCII_FILE."""
    names = []
    per_theme = getattr(config, "ASCII_FILES", {}) or {}
    if theme in per_theme:
        names.append(per_theme[theme])
    names.append(config.ASCII_FILE)

    for name in names:
        path = HERE / name
        if path.exists():
            text = path.read_text(encoding="utf-8").rstrip("\n")
            return text.split("\n"), name

    return [], None


def main():
    stats = load_stats()
    subs = build_subs(stats)

    if "--list-vars" in sys.argv:
        print("Available placeholders:\n")
        for k, v in sorted(subs.items()):
            print(f"  ${k:<22} {v}")
        print(f"\n  plus ('langs', n) for the top-n language bars "
              f"({len(stats.get('languages', []))} language(s) known)")
        return

    if "--invert" in sys.argv:
        i = sys.argv.index("--invert")
        if i + 1 >= len(sys.argv):
            sys.exit("usage: python3 generate.py --invert <file>   (prints to stdout)")
        src = Path(sys.argv[i + 1])
        if not src.exists():
            sys.exit(f"no such file: {src}")
        sys.stdout.write(invert_art(src.read_text(encoding="utf-8")))
        return

    # Load every theme's art first, so all cards can share one set of
    # dimensions — otherwise the image would resize when the viewer's
    # system theme flips.
    arts = {t: load_art(t) for t in config.THEMES}
    art_cols = max((len(l) for lines, _ in arts.values() for l in lines), default=0)

    info_cols = max(
        max(entry_width(e, subs, stats) for e in config.INFO),
        len(config.PROMPT) + 10,
    )
    art_rows = max((len(lines) for lines, _ in arts.values()), default=0)

    width = None
    for theme in config.THEMES:
        art_lines, src = arts[theme]
        svg = render(theme, art_lines, art_cols, art_rows, info_cols, subs, stats)
        (HERE / f"{theme}_mode.svg").write_text(svg, encoding="utf-8")
        print(f"wrote {theme}_mode.svg   (art: {src or 'none'})")
        width = int(re.search(r'width="(\d+)"', svg).group(1))

    layout = getattr(config, "LAYOUT", "side")
    print(f"  layout  {layout}   art {art_cols}x{art_rows} cols, info {info_cols} cols")
    print(f"  uptime  {subs['uptime']}")
    print(f"  stats   {stats['updated']}")
    report_scale(width, layout, art_cols, info_cols)


# GitHub's README content column is roughly this wide in CSS pixels. Anything
# wider gets scaled down to fit, shrinking the text with it.
README_COLUMN_PX = 830


def report_scale(width, layout, art_cols, info_cols):
    if not width:
        return
    scale = min(1.0, README_COLUMN_PX / width)
    effective = config.FONT_SIZE * scale

    print(f"\n  card is {width}px wide; GitHub's README column is ~{README_COLUMN_PX}px")
    if scale >= 0.995:
        print(f"  -> renders at full size, text reads at {config.FONT_SIZE}px. Good.")
        return

    print(f"  -> GitHub scales it to {scale * 100:.0f}%, so text reads at "
          f"~{effective:.1f}px")
    print("     Raising FONT_SIZE will NOT help — it scales down by the same "
          "factor.")
    print("     Fewer COLUMNS is the only lever:")
    if layout == "side":
        stacked_w = round(config.PAD * 2 + max(art_cols, info_cols) * config.CHAR_W)
        stacked_s = min(1.0, README_COLUMN_PX / stacked_w)
        print(f"       - LAYOUT = \"stacked\" in config.py -> {stacked_w}px "
              f"({stacked_s * 100:.0f}%, ~{config.FONT_SIZE * stacked_s:.1f}px text)")
    budget = int((README_COLUMN_PX - config.PAD * 2) / config.CHAR_W)
    print(f"       - narrower ASCII art (fits at <= {budget} cols in stacked layout)")
    print(f"       - shorten your longest INFO value (info is {info_cols} cols)")


if __name__ == "__main__":
    main()
