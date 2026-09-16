"""
Everything you edit by hand lives here.

Values in INFO may contain $placeholders — they get filled in from stats.json
(fetched by stats.py) plus a few computed values. Run

    python3 generate.py --list-vars

to print every placeholder that's currently available.
"""

from datetime import date

# ── who you are ────────────────────────────────────────────────────

GITHUB_USER = "Ash173"
PROMPT      = "ashwinrnair"
BIRTH_DATE  = date(2002, 3, 17)      # <-- CHANGE THIS. Drives $uptime.

# ASCII art. Give each theme its own file when you want different art for
# light and dark backgrounds (density-ramp portraits usually need inverting).
# A theme with no entry here — or whose file is missing — falls back to
# ASCII_FILE, so a single ascii.txt still works fine.
ASCII_FILE  = "ascii.txt"
ASCII_FILES = {
    "dark":  "ascii_dark.txt",
    "light": "ascii_light.txt",
}

# ── the card body ──────────────────────────────────────────────────
#
#   ("kv",  key, value)        a dotted line
#   ("sec", title)             a "- Section ----" divider
#   ("gap",)                   blank line
#   ("loc", )                  the green/red lines-of-code line (all dynamic)
#   ("langs", n)               top n languages as coloured bars (all dynamic)
#
INFO = [
    ("kv", "OS",     "Windows 11, Ubuntu"),
    ("kv", "Uptime", "$uptime"),
    ("kv", "Host",   "Indian Institute of Technology, Kanpur"),
    ("kv", "Kernel", "M.Tech, Microelectronics & VLSI"),
    #("kv", "IDE",    "VS Code, Cadence Virtuoso"),
    ("gap",),
    ("kv", "Languages.Programming", "Python, C, C++, MATLAB"),
    ("kv", "Languages.Hardware",    "Verilog HDL, Verilog-A, SPICE"),
    ("kv", "Languages.Real",        "English, Malayalam, Hindi"),
    ("gap",),
    ("kv", "Tools.Digital",  "Icarus Verilog, Yosys, Vivado"),
    ("kv", "Tools.EDA", "Cadence Virtuoso, Synopsys HSPICE, Keysight ADS"),
    ("kv", "Tools.Others",   "Spectre, IC-CAP, Sentaurus TCAD, Ansys HFSS"),
    ("gap",),
    ("sec", "Contact"),
    ("kv", "Email.Personal", "ashwinrnair2002@gmail.com"),
    ("kv", "Email.Academic", "ashwinnair25@iitk.ac.in"),
    ("kv", "LinkedIn",       "ashwinrnair17"),
    ("kv", "GitHub",         "$login"),
    ("gap",),
    ("sec", "GitHub Stats"),
    ("kv", "Repos",         "$repos {Contributed: $contributed}  |  Stars: $stars"),
    ("kv", "Followers",     "$followers  |  Following: $following"),
    ("kv", "Commits",       "$commits  |  This year: $commits_this_year"),
    ("kv", "Contributions", "$contributions_total all time"),
    ("kv", "Most Starred",  "$top_repo ($top_repo_stars)"),
    ("loc",),
    ("gap",),
    ("sec", "Top Languages"),
    ("langs", 5),
    ("gap",),
    ("kv", "Last Updated", "$updated"),
]

# ── looks ──────────────────────────────────────────────────────────

FONT_SIZE   = 16
LINE_HEIGHT = 20
CHAR_W      = FONT_SIZE * 0.6        # monospace advance width
PAD         = 24                     # padding inside the card
GAP_COLS    = 4                      # blank columns between art and info
BAR_COLS    = 22                     # width of a language bar, in characters
LANG_NAME_W = 14                     # language-name column width, in characters

FONT_STACK  = ('"Andale Mono", AndaleMono, "Cascadia Mono", '
               '"DejaVu Sans Mono", "Liberation Mono", monospace')

THEMES = {
    "dark": {
        "bg":      "#1a1b27",
        "border":  "#2b2d40",
        "ascii":   "#8b93a7",
        "prompt":  "#70a5fd",
        "rule":    "#4a5163",
        "sec":     "#e4bf7a",
        "key":     "#38bdae",
        "dots":    "#3f465a",
        "value":   "#d9dde3",
        "add":     "#3fb950",
        "del":     "#f85149",
        "bartrack": "#2b2d40",
    },
    "light": {
        "bg":      "#ffffff",
        "border":  "#d0d7de",
        "ascii":   "#57606a",
        "prompt":  "#0969da",
        "rule":    "#afb8c1",
        "sec":     "#953800",
        "key":     "#1f7a6f",
        "dots":    "#c4cbd4",
        "value":   "#24292f",
        "add":     "#1a7f37",
        "del":     "#cf222e",
        "bartrack": "#eaeef2",
    },
}
