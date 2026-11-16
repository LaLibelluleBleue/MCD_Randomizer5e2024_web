#!/usr/bin/env python3
"""Randomizer5e2024 build script.

Reads the CSV tables in the data/ folder, fills them into template.html and
writes index.html (the file you upload to GitHub and share with players).

Usage:  python build.py        (Python 3, standard library only, no pip needed)

Edit the CSVs in Excel or any text editor. Weights are RELATIVE: they do not
have to add up to 100, the app scales them to a d100. Extra columns are allowed
and ignored. Save CSVs as "CSV UTF-8" so accents survive.
"""
import csv, json, pathlib, sys

APP = "Randomizer5e2024"
VERSION = "1.1"

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

payload = {"app": APP, "version": VERSION, "sources": sources, "species": species, "lin": lin,
           "cls": cls, "bg": bg, "sex": sex, "names": names}
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
for label, t in (("species", species), ("origins", bg), ("sex", sex)):
    print("  %s weights total %s" % (label, sum(e[1] for e in t)))
