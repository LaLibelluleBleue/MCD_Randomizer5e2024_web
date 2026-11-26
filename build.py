#!/usr/bin/env python3
"""Randomizer5e2024 build script.

Reads the CSV tables in the data/ folder, fills them into template.html and
writes index.html (the file you upload to GitHub and share with players).

Usage:  python build.py        (Python 3, standard library only, no pip needed)

Edit the CSVs in Excel or any text editor. Weights are RELATIVE: they do not
have to add up to 100, the app scales them to a d100. Extra columns are allowed
and ignored. Save CSVs as "CSV UTF-8" so accents survive.
"""
import atexit, csv, datetime, io, json, math, pathlib, re, sys, traceback

_HERE = pathlib.Path(__file__).resolve().parent   # captured now: __file__ is not available later, when the exit handlers run


class _Tee:
    def __init__(self, stream, buf):
        self.stream, self.buf = stream, buf

    def write(self, x):
        self.buf.append(x)
        try:
            self.stream.write(x)
        except Exception:
            self.stream.write(x.encode("ascii", "replace").decode("ascii"))

    def flush(self):
        self.stream.flush()


_LOG = []
sys.stdout, sys.stderr = _Tee(sys.stdout, _LOG), _Tee(sys.stderr, _LOG)


def _writelog():
    try:
        (_HERE / "build_log.txt").write_text("".join(_LOG), encoding="utf-8")
    except Exception as e:
        sys.__stderr__.write("Could not save build_log.txt: %r\n" % (e,))


def _hook(t, v, tb):
    # Show errors (a double-clicked window would otherwise close before you can read them) and save them to build_error.txt
    msg = "".join(traceback.format_exception(t, v, tb))
    print("\nERROR while building:\n" + msg)
    try:
        (_HERE / "build_error.txt").write_text(msg, encoding="utf-8")
    except Exception:
        pass


def _pause():
    try:
        if sys.stdin and sys.stdin.isatty():
            input("\nPress Enter to close this window...")
    except Exception:
        pass


sys.excepthook = _hook
atexit.register(_pause)
atexit.register(_writelog)   # runs first: the log is saved before the "Press Enter" prompt

APP = "Randomizer5e2024"
VERSION = "1.3.3"
IMMORTAL_SCALE = 1000   # years used to scale ages of species whose lifespan is "immortal" (display only; they never die of old age)

here = pathlib.Path(__file__).resolve().parent
data = here / "data"

# Data files that older folders may lack: they are created with default values the first time you build.
DEFAULT_FILES = {
    "odds.csv": (["key", "same_species_pct", "note"], [["Friend", 60, "chance (in %) that this kind of person is the same species as the character; otherwise a different species is drawn from the species table"], ["Enemy", 50, ""], ["Important contact", 40, ""], ["Mentor", 50, ""]]),
    "parentage.csv": (["species", "parent_a", "parent_b", "weight", "note"], [["Aasimar", "Aasimar", "Aasimar", 50, "weights are relative"], ["Aasimar", "Aasimar", "Human", 48, ""], ["Aasimar", "Human", "Human", 2, ""], ["Tiefling", "Tiefling", "Tiefling", 50, ""], ["Tiefling", "Tiefling", "Human", 48, ""], ["Tiefling", "Human", "Human", 2, ""], ["Khoravar", "Human", "Elf", 40, ""], ["Khoravar", "Khoravar", "Human", 30, ""], ["Khoravar", "Khoravar", "Elf", 30, ""], ["Kalashtar", "Kalashtar", "Kalashtar", 60, ""], ["Kalashtar", "Kalashtar", "Human", 40, ""]]),
    "offspring.csv": (["parent_a", "parent_b", "child", "weight", "note"], [["Human", "Elf", "Khoravar", 100, "a couple with no row has a child of their own species (same species) or none (different species)"], ["Khoravar", "Human", "Khoravar", 50, ""], ["Khoravar", "Human", "Human", 50, ""], ["Khoravar", "Elf", "Khoravar", 50, ""], ["Khoravar", "Elf", "Elf", 50, ""], ["Aasimar", "Human", "Aasimar", 50, ""], ["Aasimar", "Human", "Human", 50, ""], ["Tiefling", "Human", "Tiefling", 50, ""], ["Tiefling", "Human", "Human", 50, ""], ["Kalashtar", "Human", "Kalashtar", 50, ""], ["Kalashtar", "Human", "Human", 50, ""]]),
}
for _fn, (_head, _body) in DEFAULT_FILES.items():
    if not (data / _fn).exists():
        with open(data / _fn, "w", encoding="utf-8-sig", newline="") as _f:
            _w = csv.writer(_f)
            _w.writerow(_head)
            _w.writerows(_body)
        print("Note: data/%s was missing, so it was created with default values" % _fn)


_NOTED = set()


def rows(name):
    with open(data / name, encoding="utf-8-sig", newline="") as f:
        text = f.read()
    first = text.split("\n", 1)[0]
    delim = ";" if first.count(";") > first.count(",") else ("\t" if first.count("\t") > first.count(",") else ",")
    if delim != "," and name not in _NOTED:
        _NOTED.add(name)
        print("Note: %s is separated by '%s' (read correctly). 'CSV UTF-8 (comma delimited)' is the safest format." % (name, "TAB" if delim == "\t" else delim))
    return [r for r in csv.DictReader(io.StringIO(text), delimiter=delim) if any((v or "").strip() for v in r.values())]


def num(x):
    v = float(str(x).strip().replace(",", "."))
    return int(v) if v == int(v) else v


_all_species = rows("species.csv")
npc_only = set()
for r in _all_species:
    _nm = r["species"].strip()
    _pl = (r.get("Playable") or r.get("playable") or "").strip().lower()
    _np = (r.get("NPC") or r.get("npc") or r.get("NPC only") or "").strip().lower()
    if _pl in ("no", "n", "0", "false") or _np in ("yes", "y", "1", "true") or num(r["weight"]) == 0:
        npc_only.add(_nm)
_refs = set()
for _fn, _cols in (("parentage.csv", ("species", "parent_a", "parent_b")), ("offspring.csv", ("parent_a", "parent_b", "child"))):
    if (data / _fn).exists():
        for r in rows(_fn):
            for _c in _cols:
                _refs.add((r.get(_c) or "").strip())
_refs.discard("")
for _x in sorted(_refs - {r["species"].strip() for r in _all_species}):
    npc_only.add(_x)
    print("Note: '%s' appears in parentage/offspring but not in species.csv, so it is an NPC-only species (never playable, no occupation, cannot die of old age; its names go in names_npc.csv)" % _x)
species = [[r["species"].strip(), num(r["weight"]), r["source"].strip()] for r in _all_species if r["species"].strip() not in npc_only]
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

names = {s: {"F": [], "M": [], "S": []} for s in sp_names + sorted(npc_only)}
for r in sum((rows(p.name) for p in sorted(data.glob("names*.csv"))), []):   # every names*.csv in data/
    sp, lst = r["species"].strip(), r["list"].strip().upper()
    if sp not in names or lst not in ("F", "M", "S"):
        sys.exit("names.csv: bad species or list on row: %s" % dict(r))
    names[sp][lst].append(r["name"].strip())

for _s in sp_names + sorted(npc_only):
    if not names[_s]["F"] and not names[_s]["M"]:
        print("WARNING: no names for %s %s in any names*.csv (NPC-only species belong in names_npc.csv); Human names will be used for it" % ("NPC-only species" if _s in npc_only else "species", _s))

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


for _s in sp_names:
    if not any(c["w"].get(_s) for c in cls):
        print("Warning: no class odds for species %s in classes.csv; every class will be equally likely for it" % _s)
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
ages, turn = {}, {}
for r in rows("species.csv"):
    sp_ = r["species"].strip()
    life = (r.get("lifespan") or "80").strip()
    immortal = life.lower() == "immortal"
    ages[sp_] = [num(r.get("adult_age") or 18), IMMORTAL_SCALE if immortal else num(life), 1 if immortal else 0]
    tv = (r.get("Transformed") or r.get("transformed") or "0").strip()
    turn[sp_] = num(tv) if tv else 0
for _x in npc_only:
    if _x not in ages:
        ages[_x] = [18, IMMORTAL_SCALE, 1]
    ages[_x][1], ages[_x][2], turn[_x] = IMMORTAL_SCALE, 1, 0

# ---- Backstory tables (backstory.csv): real dice and roll ranges, like the book ----
bt, bd = {}, {}
for r in rows("backstory.csv") + rows("events.csv"):
    tb, ex = r["table"].strip(), r["dice"].strip()
    m = re.match(r"^(-?\d+)\s*(?:[-\u2013]|to)\s*(-?\d+)$", r["roll"].strip())
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
    dmin, dmax = n_ + b_, n_ * s_ + b_
    for a_, c_ in zip(rws, rws[1:]):
        if c_["lo"] != a_["hi"] + 1:
            print("Warning: table %s (%s): rolls %s and %s are not consecutive" % (tb, bd[tb], a_["r"], c_["r"]))
    if rws[0]["lo"] > dmin:
        print("Warning: table %s (%s): rolls start at %s but the dice can roll %s" % (tb, bd[tb], rws[0]["lo"], dmin))
    if rws[-1]["hi"] < dmax:
        print("Warning: table %s (%s): rolls end at %s but the dice can roll %s" % (tb, bd[tb], rws[-1]["hi"], dmax))

hyb = []
if (data / "hybrids.csv").exists():
    hyb = [[r["species_a"].strip(), r["species_b"].strip(), r["child_species"].strip()] for r in rows("hybrids.csv")]

odds = {}
if (data / "odds.csv").exists():
    odds = {r["key"].strip(): num(r["same_species_pct"]) for r in rows("odds.csv")}

# ---- Parentage (who a character's parents can be) and offspring (what species a couple's child can be) ----
par, off = {}, []
known_sp = set(sp_names) | npc_only
if (data / "parentage.csv").exists():
    for r in rows("parentage.csv"):
        names3 = [r["species"].strip(), r["parent_a"].strip(), r["parent_b"].strip()]
        for n_ in names3:
            if n_ not in known_sp:
                print("Warning: parentage.csv mentions unknown species '%s'" % n_)
        par.setdefault(names3[0], []).append([names3[1], names3[2], num(r["weight"])])
if (data / "offspring.csv").exists():
    for r in rows("offspring.csv"):
        trio = [r["parent_a"].strip(), r["parent_b"].strip(), r["child"].strip()]
        for n_ in trio:
            if n_ not in known_sp:
                print("Warning: offspring.csv mentions unknown species '%s'" % n_)
        off.append(trio + [num(r["weight"])])
for sp_, lst in par.items():
    for a_, b_, w_ in lst:
        if a_ != b_ and not any(((o[0] == a_ and o[1] == b_) or (o[0] == b_ and o[1] == a_)) and o[2] == sp_ for o in off):
            print("Warning: %s parents %s + %s: offspring.csv has no row letting that couple have a %s child" % (sp_, a_, b_, sp_))
if (data / "hybrids.csv").exists():
    print("Note: hybrids.csv is no longer used; put couples and their children in offspring.csv")

REPORT = []


def rep(line):
    REPORT.append(line)
    print(line)


rep("Data check (%s)" % datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))
rep("Data folder: %s" % data)
_expected = ["species.csv", "lineages.csv", "classes.csv", "origins.csv", "sex.csv", "sources.csv", "backstory.csv", "events.csv", "odds.csv", "parentage.csv", "offspring.csv"]
for _fn in _expected:
    rep("  %-16s %s" % (_fn, ("found, %d rows" % len(rows(_fn))) if (data / _fn).exists() else "MISSING"))
_namefiles = sorted(p.name for p in data.glob("names*.csv"))
for _fn in _namefiles:
    rep("  %-16s found, %d rows (names)" % (_fn, len(rows(_fn))))
if not any(n.lower().startswith("names_npc") for n in _namefiles) and npc_only:
    rep("  names_npc.csv    MISSING (needed for NPC-only species: %s)" % ", ".join(sorted(npc_only)))
for _p in sorted(data.glob("*.csv")):
    if _p.name not in _expected and _p not in data.glob("names*.csv"):
        rep("  NOT USED: %s (the build only reads the files listed above)" % _p.name)
rep("Playable species: %d | NPC-only species: %s" % (len(sp_names), ", ".join(sorted(npc_only)) or "none"))
_okeys = ["Friend", "Enemy", "Important contact", "Mentor"]
rep("Odds loaded from odds.csv: " + (", ".join("%s=%s%%" % (k, v) for k, v in odds.items()) or "NONE (built-in defaults will be used)"))
for _k in _okeys:
    if _k not in odds:
        rep("WARNING: odds.csv has no row named '%s' (spelling must match exactly); the built-in default will be used" % _k)
for _k in odds:
    if _k not in _okeys:
        rep("WARNING: odds.csv row '%s' is not recognized and is ignored (expected: %s)" % (_k, ", ".join(_okeys)))
rep("Backstory/event tables: %d (%d rows) | parentage species: %d | offspring rows: %d" % (len(bt), sum(len(v) for v in bt.values()), len(par), len(off)))
for _s in sp_names + sorted(npc_only):
    _n = names[_s]
    rep("  names %-12s F/M/S: %d/%d/%d" % (_s, len(_n["F"]), len(_n["M"]), len(_n["S"])))

payload = {"app": APP, "version": VERSION, "sources": sources, "species": species, "lin": lin,
           "cls": cls, "bg": bg, "sex": sex, "names": names, "bt": bt, "bd": bd, "age": ages, "hyb": hyb, "odds": odds, "turn": turn, "par": par, "off": off, "npcsp": sorted(npc_only), "report": REPORT}
blob = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")

template = (here / "template.html").read_text(encoding="utf-8")
marker = "const DATA=/*DATA*/null;"
if marker not in template:
    sys.exit("template.html is missing the DATA marker")
(here / "index.html").write_text(template.replace(marker, "const DATA=" + blob + ";"), encoding="utf-8")

print("Built index.html (%s v%s)" % (APP, VERSION))
for label, t in (("species", species), ("origins", bg), ("sex", sex)):
    print("  %s weights total %s" % (label, sum(e[1] for e in t)))
