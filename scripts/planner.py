"""HQ planner: turns the site's live gaps into a ranked backlog for the office agents.

HQ still never predicts or grades. It reads footyalmanac's published records,
measures where quotes and results disagree, and writes docs/data/backlog.json.
footyalmanac's agents/pick_task.py reads that file (over GitHub Pages) and
works the top tasks each morning.

The live record is used only to *locate* a gap. Every brief tells the agent to
test any fix on history (footyalmanac CLAUDE.md, Rule 1) under the usual gates.

A gap is ranked by its z-score: (won - expected) / sqrt(sum p(1-p)). Raw hit
rates are not compared, because a 70% band and a 90% band should land
differently and small samples swing. Shortfalls and overshoots are both bugs
(the site's objective 3), but a List shortfall is worth most.
"""
import json, math, os, urllib.request
from datetime import date, datetime, timedelta, timezone

REPO = "douglasbakeronline/footyalmanac"
RAW = f"https://raw.githubusercontent.com/{REPO}/main/"
WINDOW_DAYS = 28
MAX_TASKS = 12
OWNERS = {"chief", "scout", "quality", "source", "ratings", "experiment", "sports", "auditor",
          "calib", "curator", "engineer", "champ", "odds", "accas"}
SPORT_NAMES = {"nfl": "NFL", "mlb": "baseball (MLB)", "nba": "NBA", "rugby": "rugby union", "nhl": "NHL",
               "cfb": "college football", "ncaab": "college basketball", "wnba": "WNBA", "nrl": "rugby league (NRL)"}
GROUPS_RULE_FROM = "2026-10-19"   # honest leg chances (footyalmanac #47); earlier groups used the old rule

RULES = ("Use the live record only to locate the gap: never fit on record.json (Rule 1). Test any fix on history, "
         "paired and bootstrapped, fitted on the last completed season and confirmed on the current one (Rule 3 "
         "gates: 250+ check games, p(worse) at most 0.30, gain at least 0.0005 log loss). If it passes, ship the "
         "code change with its evidence. If it does not, ship a dated claude/ note with the numbers so nobody "
         "repeats it. Check claude/ and RELEASES.md first: if this exact idea was already rejected, test a "
         "different one.")


# ---------- stats ----------

def gap(rows):
    """rows: iterable of (quoted chance, landed bool). Returns n, won, expected, z."""
    n = won = 0; exp = var = 0.0
    for p, ok in rows:
        if p is None or ok is None: continue
        n += 1; won += 1 if ok else 0; exp += p; var += p * (1 - p)
    z = (won - exp) / math.sqrt(var) if var > 0 else 0.0
    return {"n": n, "won": won, "expected": round(exp, 1), "z": round(z, 2),
            "quoted": round(exp / n, 4) if n else None, "landed": round(won / n, 4) if n else None}


def pct(x): return f"{x * 100:.0f}%" if x is not None else "n/a"


def says(g): return f"{g['won']} of {g['n']} landed ({pct(g['landed'])}) against {g['expected']:.1f} expected ({pct(g['quoted'])} quoted), z {g['z']:+.1f}"


def since(rows, start, key="date"):
    return [r for r in rows if (r.get(key) or "")[:10] >= start]


# ---------- rows from each record ----------

def fq(r):
    """A football row's quote. score.py counts a drawn game as correct when the predicted scoreline was a draw
    (Douglas, 6 Oct 2026), and quotes those rows at pick-or-draw ('expected'), so landed and quoted match."""
    return r.get("expected") if r.get("expected") is not None else r["confidence"]


def football_rows(graded):
    return [r for r in graded if r.get("ok") is not None and r.get("verified") not in ("late", "timing-unverifiable")]


def tennis_rows(trec):
    return [r for r in (trec.get("graded") or []) if not r.get("void") and r.get("ok") is not None]


def sports_rows(srec):
    out, seen = [], set()
    for d in srec.get("days") or []:
        for g in d.get("games") or []:
            if g.get("ok") is None or g.get("id") in seen: continue
            seen.add(g.get("id")); out.append(dict(g, date=(g.get("when") or d.get("date") or "")[:10]))
    return out


# ---------- standing priorities from footyalmanac's README ----------

ROADMAP = [
    ("own-band", "curator", "Replay own-band List admission for every sport",
     "College football passed the cumulative 80% rule while its 70-80% calls landed in the low 70s, and rugby union "
     "and college basketball (70% bars) show the same shape in testing. Replay, for every sport in one run, a rule "
     "that admits a pick only if its own 5-point band landed at least the bar on held-out games. Report picks gained "
     "and lost per sport and the hit rate either way. Ship the rule where it clearly passes."),
    ("tennis-surface", "sports", "Give tennis results a surface",
     "ESPN tennis results carry no surface, so every result since June is rated as hard court; WTA live calls run "
     "below their quotes. Find a free, automatable source or a maintained tournament-to-surface map, apply it in "
     "build_tennis.py, and replay the live period on both tours. Tennis returns to the List only on that evidence."),
    ("coverage-af", "scout", "Cover Croatia, Serbia, Ukraine, Hungary, Korea or the UAE",
     "These leagues have no free source. Check API-Football's league list (af-leagues.json, the paid plan already "
     "held) for each, add the ones it carries with name-matching tests, and keep them off the List until replayed. "
     "Measure the API allowance each adds per build."),
    ("odds-keys", "odds", "Log why tennis tournaments miss an Odds API key",
     "Almaty, the European Open and the Japan Open matched no sport key on 19 Oct. Log the active key list in "
     "groupings.py --probe (the sports list costs no credits) and fix the matching so priced tennis legs reach the tab."),
]


# ---------- the tasks ----------

def task(key, owner, title, brief, g, weight, metric):
    assert owner in OWNERS, owner
    return {"key": f"hq-{key}", "owner": owner, "title": title[:80], "brief": brief + "\n\n" + RULES,
            "evidence": g, "metric": metric, "score": round(weight * abs(g["z"]), 2)}


def plan(files, today=None, done=()):
    """files: record-graded.json, tennis-record.json, sports-record.json, groupings-record.json,
    record.json and the latest predictions list ('predictions'). done: task keys with a pull request
    merged in the last 30 days. Returns the backlog dict."""
    done = set(done)
    today = today or datetime.now(timezone.utc).date()
    start = (today - timedelta(days=WINDOW_DAYS)).isoformat()
    fb = football_rows((files.get("record-graded.json") or {}).get("graded") or [])
    tn = tennis_rows(files.get("tennis-record.json") or {})
    sp = sports_rows(files.get("sports-record.json") or {})
    fbw, tnw, spw = since(fb, start), since(tn, start), since(sp, start)
    T = []

    # 1. Daily List: quoted vs landed, by sport (objective 2)
    lists = {"football": gap((fq(r), r["ok"]) for r in fbw if r.get("list")),
             "tennis": gap((r["confidence"], r["ok"]) for r in tnw if r.get("list"))}
    for s in sorted({g.get("sport") for g in spw if g.get("list")} - {None}):
        lists[s] = gap((g["confidence"], g["ok"]) for g in spw if g.get("list") and g.get("sport") == s)
    for s, g in lists.items():
        if g["n"] >= 15 and g["z"] <= -1.0:
            name = SPORT_NAMES.get(s, s)
            T.append(task(f"list-{s}", "curator" if s == "football" else "sports",
                f"Daily List {name}: {g['won']}/{g['n']} against {g['expected']:.0f} expected",
                f"Over the last {WINDOW_DAYS} days the {name} Daily List picks: {says(g)}. The List promises at least "
                "80% and quotes that match what lands. Find where the shortfall sits (league or tournament, 5-point "
                "band, home or away pick, Celtic's Law, early season) and whether the bar or the quote is wrong. "
                "Suspects from the site README: the cumulative tested rate shown on rows (own-band rates are "
                "stricter), and tier-2 leagues at a 75% bar. If a stricter admission rule would have landed 80% on "
                "history, ship it.", g, 3.0, "list"))

    # 1b. Football List split by tier: main set v API-Football wider leagues
    for tier, test in (("main", lambda r: not str(r.get("league", "")).startswith("af.")),
                       ("wider", lambda r: str(r.get("league", "")).startswith("af."))):
        g = gap((fq(r), r["ok"]) for r in fb if r.get("list") and test(r))
        if g["n"] >= 20 and g["z"] <= -1.5:
            T.append(task(f"list-football-{tier}", "curator",
                f"Football List, {'main' if tier == 'main' else 'wider API-Football'} leagues below quote",
                f"Football Daily List picks from the {'main league set (80% bar)' if tier == 'main' else '227 wider API-Football leagues (75% bar, build.LIST_MIN_AFX)'}, "
                f"all graded to date: {says(g)}. Replay this tier's admission on history and test a higher bar or "
                "an own-band rule for it alone.", g, 2.5, "list"))

    # 2. Reserve (62% up to the bar)
    for s, rows in (("football", fbw), ("tennis", tnw), ("other sports", spw)):
        q = fq if s == "football" else (lambda r: r["confidence"])
        g = gap((q(r), r["ok"]) for r in rows if r.get("reserve"))
        if g["n"] >= 30 and g["z"] <= -1.5:
            T.append(task(f"reserve-{s.replace(' ', '-')}", "curator", f"Reserve ({s}) landing below its quotes",
                f"{s.title()} reserve picks over the last {WINDOW_DAYS} days: {says(g)}. Find which bands or "
                "competitions carry the gap and whether the reserve should exclude them.", g, 1.5, "honesty"))

    # 3. Honesty: football calibration by 5-point band, every graded call, either direction (objective 3)
    bands = []
    for lo in range(50, 100, 5):
        g = gap((fq(r), r["ok"]) for r in fb if lo / 100 <= fq(r) < (lo + 5) / 100)
        if g["n"] >= 100: bands.append((lo, g))
    if bands:
        lo, g = max(bands, key=lambda b: abs(b[1]["z"]))
        if abs(g["z"]) >= 2.0:
            word = "under" if g["z"] < 0 else "over"
            T.append(task(f"band-{lo}", "calib", f"Football {lo}-{lo + 5}% band lands {word} its quote",
                f"Every graded football call quoted (pick, or pick-or-draw where the predicted score is a draw) {lo}-{lo + 5}%: {says(g)}. A gap in either direction is a bug. "
                "Check whether the calibration curve (calibration.json, a straight line in confidence) can bend "
                "enough here, or whether one group of competitions (wider API-Football leagues, cups, Celtic's Law) "
                "drives it. calibration.json only changes through tune.py's gates (Rule 5): improve the method, "
                "never hand-edit the file.", g, 2.0, "honesty"))

    # 4. Draws: the model's own draw chance against draws that happened, on confident picks
    strong = [r for r in fb if r["confidence"] >= 0.70 and r.get("p") and len(r["p"]) == 3]
    if strong:
        g = gap((r["p"][1], r.get("actual") == "d") for r in strong)
        losses = sum(1 for r in strong if not r["ok"])
        drawn = sum(1 for r in strong if not r["ok"] and r.get("actual") == "d")
        flip = dict(g, z=-g["z"])     # more draws than priced is the shortfall
        if losses >= 15 and g["z"] >= 1.5:
            T.append(task("draws-strong", "experiment", f"Draws: {drawn} of {losses} losses at 70%+ were draws",
                f"Football calls quoted 70% or more: the model priced {g['expected']:.1f} draws and {g['won']} "
                f"happened over {g['n']} games (z {g['z']:+.1f}). {drawn} of the {losses} losses were draws. Test "
                "ONE draw-risk signal on history (predictability.py is the harness): a low expected-goals total, "
                "two defensive sides, a narrow rating gap with a big home edge. A signal that passes should "
                "demote the pick from the List, not flip it to a draw.", flip, 2.0, "list"))

    # 5. Leagues landing below their quotes (enough games to mean something)
    by_lg = {}
    for r in fb: by_lg.setdefault(r.get("league"), []).append(r)
    names = {k: v.get("name", k) for k, v in ((files.get("record.json") or {}).get("byLeague") or {}).items()}
    lg = [(k, gap((fq(r), r["ok"]) for r in rows)) for k, rows in by_lg.items() if len(rows) >= 40]
    for k, g in sorted(lg, key=lambda x: x[1]["z"])[:2]:
        if g["z"] > -2.0: break
        T.append(task(f"league-{k}", "champ" if k == "en.2" else "experiment",
            f"{names.get(k, k)} lands below its quotes",
            f"{names.get(k, k)} ({k}), every graded call: {says(g)}. Break the misses down on history (promoted "
            "sides, early season, home advantage, draws, rating source) and test ONE league-level fix.", g, 1.2, "honesty"))

    # 6. Tennis by tour
    for tour in ("ATP", "WTA"):
        g = gap((r["confidence"], r["ok"]) for r in tnw if r.get("tour") == tour)
        if g["n"] >= 40 and abs(g["z"]) >= 1.5:
            word = "below" if g["z"] < 0 else "above"
            T.append(task(f"tennis-{tour.lower()}", "sports", f"{tour} landing {word} its quotes",
                f"{tour} calls over the last {WINDOW_DAYS} days: {says(g)}. Tennis is off the Daily List until its "
                "live record holds. Known cause: ESPN results carry no surface, so everything since June is rated "
                "as hard court. Find a free, automatable surface source or test a tournament-to-surface map, then "
                "replay the live period.", g, 1.5, "honesty"))

    # 7. Other sports, each sport's full graded record
    for s, v in sorted(((files.get("sports-record.json") or {}).get("bySport") or {}).items()):
        if not v or v.get("n", 0) < 30: continue
        n, e = v["n"], v["expected"]
        g = {"n": n, "won": v["correct"], "expected": round(n * e, 1), "quoted": e, "landed": v["accuracy"],
             "z": round((v["correct"] - n * e) / math.sqrt(n * e * (1 - e)), 2)}
        if abs(g["z"]) >= 1.5:
            word = "below" if g["z"] < 0 else "above"
            nm = SPORT_NAMES.get(s, s)
            T.append(task(f"sport-{s}", "sports", f"{nm[0].upper() + nm[1:]} landing {word} its quotes",
                f"{SPORT_NAMES.get(s, s)}, every graded call: {says(g)}. Check the Elo settings for this sport "
                "(K, home advantage, season carry-over) with sports.py --tune style evidence on history. Under-quoting "
                "is a bug too: it keeps good picks off the List.", g, 1.2, "honesty"))

    # 8. Odds tab: legs under the honest-chance rule
    legs = []
    for d in (files.get("groupings-record.json") or {}).get("days") or []:
        if d.get("date", "") < GROUPS_RULE_FROM: continue
        for grp in d.get("groups") or []:
            for leg in grp.get("legs") or []:
                if leg.get("status") in ("won", "lost") and leg.get("p") is not None:
                    legs.append((d["date"], grp.get("name"), leg.get("event"), leg))
    seen, uniq = set(), []
    for dt, _, ev, leg in legs:
        if (dt, ev) in seen: continue
        seen.add((dt, ev)); uniq.append(leg)
    g = gap((l["p"], l["status"] == "won") for l in uniq)
    if g["n"] >= 30 and g["z"] <= -1.5:
        T.append(task("groups-legs", "accas", f"Odds tab legs: {g['won']}/{g['n']} against {g['expected']:.0f} expected",
            f"Distinct group legs since the honest-chance rule ({GROUPS_RULE_FROM}): {says(g)}. Each leg's chance is "
            "already the lower of the tested rate and the bookmaker's fair chance, so a shortfall here means one of "
            "those is still too high for the kind of leg the rules pick. Find which sport, price range or "
            "competition carries it. Prices never feed a model.", g, 1.5, "honesty"))

    # 9. Coverage: unrated fixtures on today's board (objective 1)
    preds = files.get("predictions") or []
    unrated = [p for p in preds if p.get("unrated")]
    if len(unrated) >= 5:
        lgs = {}
        for p in unrated: lgs[p.get("league")] = lgs.get(p.get("league"), 0) + 1
        top = ", ".join(f"{k} ({v})" for k, v in sorted(lgs.items(), key=lambda x: -x[1])[:6])
        g = {"n": len(preds), "won": len(preds) - len(unrated), "expected": float(len(preds)),
             "quoted": 1.0, "landed": round(1 - len(unrated) / len(preds), 4) if preds else None,
             "z": round(-min(6.0, len(unrated) / 10), 2)}
        T.append(task("unrated", "quality", f"{len(unrated)} unrated fixtures on today's board",
            f"{len(unrated)} of {len(preds)} football fixtures in the latest predictions are unrated. Most: {top}. "
            "Separate name mismatches (fix the matcher, add LIVE_NAMES, extend nametest.py) from competitions with "
            "no prior season (backfill or a source). Never force a doubtful match (Rule 6).", g, 1.0, "coverage"))

    # 10. The site's own priority list, worked until an agent ships it (README, "Where the biggest improvements are").
    # Each drops out for 30 days once a pull request for it has merged, so finished work is not redone.
    for key, owner, title, brief in ROADMAP:
        if f"hq-{key}" in done: continue
        T.append({"key": f"hq-{key}", "owner": owner, "title": title, "brief": brief + "\n\n" + RULES,
                  "evidence": None, "metric": "roadmap", "score": 1.0})

    T.sort(key=lambda t: -t["score"])
    worst = max(bands, key=lambda b: abs(b[1]["z"])) if bands else None
    objectives = {
        "list": {k: v for k, v in lists.items() if v["n"]},
        "listAll": gap([(fq(r), r["ok"]) for r in fbw if r.get("list")] +
                       [(r["confidence"], r["ok"]) for r in tnw if r.get("list")] +
                       [(g["confidence"], g["ok"]) for g in spw if g.get("list")]),
        "honesty": {"worstBand": dict(worst[1], band=f"{worst[0]}-{worst[0] + 5}%") if worst else None},
        "coverage": {"fixtures": len(preds), "unrated": len(unrated)},
    }
    return {"generated": datetime.now(timezone.utc).isoformat(timespec="minutes"), "window": WINDOW_DAYS,
            "since": start, "objectives": objectives, "tasks": T[:MAX_TASKS]}


# ---------- fetching ----------

def fetch(path):
    try:
        with urllib.request.urlopen(RAW + path, timeout=90) as r: return json.load(r)
    except Exception as e:
        print("planner: could not fetch", path, e, flush=True); return None


def gather(preds=None):
    files = {f: fetch(f) for f in ("record-graded.json", "record.json", "tennis-record.json",
                                    "sports-record.json", "groupings-record.json")}
    files["predictions"] = preds or []
    return files


def write(data_dir, preds=None, done=()):
    """Fetch, plan and save. Keeps yesterday's backlog if the main record could not be read."""
    files = gather(preds)
    path = os.path.join(data_dir, "backlog.json")
    if not files.get("record-graded.json"):
        print("planner: no football record, backlog left as it was", flush=True); return None
    b = plan(files, done=done)
    tmp = path + ".tmp"; json.dump(b, open(tmp, "w"), indent=1); os.replace(tmp, path)
    print(f"planner: {len(b['tasks'])} tasks", flush=True)
    return b


if __name__ == "__main__":
    here = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "data")
    b = write(here)
    for t in (b or {}).get("tasks", []): print(f"{t['score']:5.1f}  {t['owner']:10} {t['key']:28} {t['title']}")
