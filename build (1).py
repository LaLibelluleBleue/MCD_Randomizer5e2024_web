#!/usr/bin/env python3
"""Randomizer5e2024 build script.

Reads the CSV tables in the data/ folder, fills them into template.html and
writes index.html (the file you upload to GitHub and share with players).

Usage:  python build.py        (Python 3, standard library only, no pip needed)

Edit the CSVs in Excel or any text editor. Weights are RELATIVE: they do not
have to add up to 100, the app scales them to a d100. Extra columns are allowed
and ignored. Save CSVs as "CSV UTF-8" so accents survive.
"""
import csv, json, math, pathlib, re, sys

APP = "Randomizer5e2024"
VERSION = "1.2.11"

here = pathlib.Path(__file__).resolve().parent
data = here / "data"


def rows(name):
    with open(data / name, encoding="utf-8-sig", newline="") as f:
        return [r for r in csv.DictReader(f) if any((v or "").strip() for v in r.values())]


def num(x):
    v = float(x)
    return int(v) if v == int(v) else v


species = [[r["species"].strip(), num(r["weight"]), r["source"].strip()] for r in rows("species.csv")]
sp_names = [s[0] for s in species]

lin = {}
for r in rows("lineages.csv"):
    if r["species"].strip() not in sp_names:
        sys.exit("lineages.csv: unknown species " + r["species"])
    lin.setdefault(r["species"].strip(), []).append([r["lineage"].strip(), num(r["weight"]), r["source"].strip()])

cls = []
for r in rows("classes.csv"):
    cls.append({"n": r["class"].strip(), "s": r["source"].strip(),
                "w": {k: num(r[k]) for k in sp_names if (r.get(k) or "").strip() != ""}})

bg = [[r["origin"].strip(), num(r["weight"]), r["source"].strip()] for r in rows("origins.csv")]
sex = [[r["sex"].strip(), num(r["weight"])] for r in rows("sex.csv")]

names = {s: {"F": [], "M": [], "S": []} for s in sp_names}
for r in rows("names.csv"):
    sp, lst = r["species"].strip(), r["list"].strip().upper()
    if sp not in names or lst not in ("F", "M", "S"):
        sys.exit("names.csv: bad species or list on row: %s" % dict(r))
    names[sp][lst].append(r["name"].strip())

sources = {r["code"].strip(): r["title"].strip() for r in rows("sources.csv")}
for table in (species, bg):
    for e in table:
        if e[2] not in sources:
            print("Warning: source code '%s' is not listed in sources.csv" % e[2])


# ---- Starved-entry check: every non-zero weight must keep at least one d100 face ----
def faces(ws):
    s = sum(ws)
    f = [0] * len(ws)
    for r in range(1, 101):
        x = math.ceil(r * s / 100)
        c = 0
        for i, w in enumerate(ws):
            c += w
            if x <= c:
                f[i] += 1
                break
        else:
            f[-1] += 1
    return f


def fix(label, table, wi):
    for _ in range(10):
        ws = [e[wi] for e in table]
        f, s = faces(ws), sum(ws)
        bad = [i for i, e in enumerate(table) if e[wi] > 0 and f[i] == 0]
        if not bad:
            return
        for i in bad:
            old = table[i][wi]
            table[i][wi] = math.ceil(s / 100)
            print("Bumped %s / %s: weight %s -> %s (it had no d100 face)" % (label, table[i][0], old, table[i][wi]))


fix("species", species, 1)
for _s, _l in lin.items():
    fix("lineage " + _s, _l, 1)
for _s in sp_names:
    _t = [[c["n"], c["w"].get(_s, 0)] for c in cls]
    fix("class (" + _s + ")", _t, 1)
    for c, e in zip(cls, _t):
        if _s in c["w"] or e[1]:
            c["w"][_s] = e[1]
fix("origins", bg, 1)
fix("sex", sex, 1)

# ---- Species ages (extra columns in species.csv) ----
ages = {r["species"].strip(): [num(r.get("adult_age") or 18), num(r.get("lifespan") or 80)] for r in rows("species.csv")}

# ---- Backstory tables (backstory.csv): real dice and roll ranges, like the book ----
bt, bd = {}, {}
for r in rows("backstory.csv") + rows("events.csv"):
    tb, ex = r["table"].strip(), r["dice"].strip()
    m = re.match(r"^(\d+)\s*[-\u2013]\s*(\d+)$", r["roll"].strip())
    lo, hi = (int(m.group(1)), int(m.group(2))) if m else (int(r["roll"]), int(r["roll"]))
    if bd.setdefault(tb, ex) != ex:
        sys.exit("backstory.csv: table %s uses two different dice" % tb)
    bt.setdefault(tb, []).append({"r": r["roll"].strip(), "lo": lo, "hi": hi, "txt": r["result"].strip(),
                                  "val": (r.get("value") or "").strip(), "tag": (r.get("tag") or "").strip(),
                                  "note": (r.get("note") or "").strip(), "src": (r.get("source") or "").strip()})
for tb, rws in bt.items():
    rws.sort(key=lambda r: r["lo"])
    m = re.match(r"^(\d*)d(\d+)([+-]\d+)?$", bd[tb])
    n_, s_, b_ = int(m.group(1) or 1), int(m.group(2)), int(m.group(3) or 0)
    nxt = n_ + b_
    for r in rws:
        if r["lo"] != nxt:
            print("Warning: backstory table %s (%s): roll %s does not follow on from %s" % (tb, bd[tb], r["lo"], nxt - 1))
        nxt = r["hi"] + 1
    if nxt != n_ * s_ + b_ + 1:
        print("Warning: backstory table %s (%s): rolls end at %s, dice go up to %s" % (tb, bd[tb], nxt - 1, n_ * s_ + b_))

hyb = []
if (data / "hybrids.csv").exists():
    hyb = [[r["species_a"].strip(), r["species_b"].strip(), r["child_species"].strip()] for r in rows("hybrids.csv")]

odds = {}
if (data / "odds.csv").exists():
    odds = {r["key"].strip(): num(r["same_species_pct"]) for r in rows("odds.csv")}

payload = {"app": APP, "version": VERSION, "sources": sources, "species": species, "lin": lin,
           "cls": cls, "bg": bg, "sex": sex, "names": names, "bt": bt, "bd": bd, "age": ages, "hyb": hyb, "odds": odds}
blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

template = (here / "template.html").read_text(encoding="utf-8")
marker = "const DATA=/*DATA*/null;"
if marker not in template:
    sys.exit("template.html is missing the DATA marker")
(here / "index.html").write_text(template.replace(marker, "const DATA=" + blob + ";"), encoding="utf-8")

print("Built index.html (%s v%s)" % (APP, VERSION))
for s in sp_names:
    n = names[s]
    print("  %-11s names F/M/S: %d/%d/%d" % (s, len(n["F"]), len(n["M"]), len(n["S"])))
print("  backstory tables: %d (%d rows)" % (len(bt), sum(len(v) for v in bt.values())))
for label, t in (("species", species), ("origins", bg), ("sex", sex)):
    print("  %s weights total %s" % (label, sum(e[1] for e in t)))
