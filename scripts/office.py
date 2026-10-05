"""Footyalmanac HQ office engine. Runs in GitHub Actions on the office rhythm and writes JSON for the office page."""
import json, subprocess, threading, time, random, sys, argparse
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

REPO = "douglasbakeronline/footyalmanac"
UK = ZoneInfo("Europe/London")
import os
DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "data")
os.makedirs(DATA, exist_ok=True)
def _load(name, default):
    try: return json.load(open(os.path.join(DATA, name)))
    except Exception: return default
def _save(name, obj):
    tmp = os.path.join(DATA, name + ".tmp"); json.dump(obj, open(tmp, "w"), indent=1); os.replace(tmp, os.path.join(DATA, name))
STATE = {"standups": _load("standups.json", []), "events": _load("events.json", []), "chats": _load("chats.json", []), "reports": _load("reports.json", [])}

# UK-time rhythm. kind: "work" = background task, "standup" = full meeting
STAGE = None
RHYTHM = [
    {"t": "03:00", "kind": "work", "name": "Fixture sweep", "who": ["scout", "quality", "source"], "desc": "Gather every fixture worldwide and check names, leagues and history."},
    {"t": "03:30", "kind": "work", "name": "Predictions ranked", "who": ["ratings", "curator"], "desc": "Rate every match and rank the strongest picks."},
    {"t": "04:00", "kind": "standup", "name": "Morning stand-up", "who": "all", "desc": "All of today's work surfaced before you wake."},
    {"t": "07:45", "kind": "briefing", "name": "Douglas's daily briefing", "who": ["h2", "h3", "curator", "auditor"], "desc": "Yesterday, today's big games and why, tomorrow, and three groups of five."},
    {"t": "12:30", "kind": "refresh", "name": "Groups refresh", "who": ["h2", "h3"], "desc": "Re-price and regroup from games still to start."},
    {"t": "17:00", "kind": "refresh", "name": "Evening groups", "who": ["h2", "h3"], "desc": "Late kick-offs regrouped for the evening."},
    {"t": "13:00", "kind": "work", "name": "Midday refresh", "who": ["scout", "quality", "auditor"], "desc": "Late fixtures, team news, early results graded."},
    {"t": "13:30", "kind": "standup", "name": "Afternoon stand-up", "who": "all", "desc": "Accuracy check-in and any changes to the board."},
    {"t": "23:30", "kind": "work", "name": "Results & experiments", "who": ["auditor", "calib", "experiment"], "desc": "Grade the day and run overnight accuracy tests."},
    {"t": "18:00", "dow": 4, "kind": "saturday", "name": "Fri: Saturday picks preview", "who": ["curator", "scout", "ratings", "calib", "quality", "auditor", "chief"], "desc": "First look at Saturday's board, posted to GitHub."},
    {"t": "07:00", "dow": 5, "kind": "saturday", "name": "Sat: Saturday picks final", "who": ["curator", "scout", "ratings", "calib", "quality", "auditor", "chief"], "desc": "Final Saturday board after the morning build."},
    {"t": "07:30", "dow": 6, "kind": "saturday", "name": "Sun: Saturday picks graded", "who": ["auditor", "calib", "chief"], "desc": "How Saturday's picks did, with the misses reviewed."},
    {"t": "23:45", "kind": "report", "name": "Daily playback", "who": "all", "desc": "Business playback: KPIs vs objectives, wins, lessons and shout-outs."},
]

def gh_json(args):
    try:
        out = subprocess.run(["gh"] + args, capture_output=True, text=True, timeout=60)
        return json.loads(out.stdout) if out.stdout.strip() else None
    except Exception:
        return None

def raw(path):
    return gh_json(["api", f"repos/{REPO}/contents/{path}", "-H", "Accept: application/vnd.github.raw"])

def latest_dir_file(d):
    items = gh_json(["api", f"repos/{REPO}/contents/{d}"]) or []
    if not isinstance(items, list):
        print("listing failed", d, str(items)[:200], flush=True); items = []
    names = sorted(i["name"] for i in items if i.get("name", "").endswith(".json"))
    return (names[-1], raw(f"{d}/{names[-1]}")) if names else (None, None)

def pct(x): return f"{x*100:.0f}%" if x is not None else "n/a"

def gather():
    rec = raw("record.json") or {}
    calib = raw("calibration.json") or {}
    tune = raw("tuning-report.json") or {}
    srec = raw("sports-record.json") or {}
    trec = raw("tennis-record.json") or {}
    pname, preds = latest_dir_file("predictions")
    _, spreds = latest_dir_file("predictions-sports")
    _, tpreds = latest_dir_file("predictions-tennis")
    commits = gh_json(["api", f"repos/{REPO}/commits?per_page=40"]) or []
    runs = gh_json(["run", "list", "-R", REPO, "--workflow", "deploy.yml", "-L", "15", "--json", "name,conclusion,status,createdAt,url"]) or []
    prs = agent_prs()
    return dict(prs=prs, rec=rec, calib=calib, tune=tune, srec=srec, trec=trec, pdate=(pname or "").replace(".json", ""),
                preds=preds or [], spreds=spreds or [], tpreds=tpreds or [], commits=commits, runs=runs)

def agent_prs():
    """Real development work: pull requests the office agents and the other AI platforms opened on footyalmanac.
    REST, not `gh pr list`: the GraphQL call returned nothing from the HQ workflow's token on 5 Oct 2026."""
    out = []
    for p in gh_json(["api", f"repos/{REPO}/pulls?state=all&per_page=50"]) or []:
        if not isinstance(p, dict): continue
        lab = {l["name"] for l in p.get("labels", [])}
        if "office-agent" not in lab: continue
        owner = next((l[6:] for l in lab if l.startswith("agent:")), None)
        platform = next((l[9:] for l in lab if l.startswith("platform:")), "office")
        if p.get("merged_at"): status = "shipped"
        elif p["state"] == "closed": status = "closed"
        elif "hold" in lab: status = "on hold"
        elif "needs-owner" in lab: status = "waiting for Douglas"
        else: status = "checking"
        out.append({"n": p["number"], "title": p["title"], "url": p["html_url"], "owner": owner, "platform": platform,
                    "status": status, "opened": p["created_at"], "merged": p.get("merged_at"),
                    "closed": p.get("closed_at")})
    return out

def pr_line(p): return f"PR #{p['n']} {p['title'].split('] ',1)[-1]} ({p['status']})"

LOCK = threading.Lock()
CACHE = {"d": None, "at": 0}
CACHE_TTL = 300  # 5 minutes

def build_standup(trigger):
    """Build standup with improved caching and error handling."""
    with LOCK:
        now = time.time()
        # Use cached data if fresh and complete
        if CACHE["d"] and CACHE["d"].get("preds") and (now - CACHE["at"]) < CACHE_TTL:
            print(f"Using cached data ({int(now - CACHE['at'])}s old)", flush=True)
            d = CACHE["d"]
        else:
            d = gather()
            if not d["preds"] and CACHE["d"]:
                print("gather incomplete, using cached data", flush=True)
                d = CACHE["d"]
            elif d["preds"]:
                CACHE["d"] = d
                CACHE["at"] = now
                print("Data gathered and cached", flush=True)
        return _build(d, trigger)

def _build(d, trigger):
    rec, preds = d["rec"], d["preds"]
    L = []
    def say(a, y, t, b="None."): L.append({"agent": a, "yesterday": y, "today": t, "blockers": b})

    leagues = len({p["league"] for p in preds})
    listed = sorted([p for p in preds if p.get("list")], key=lambda p: -p["confidence"])
    unrated = sum(1 for p in preds if p.get("unrated"))
    day = (rec.get("days") or [{}])[0]
    ov, lst = rec.get("overall", {}), rec.get("list", {})
    bands = rec.get("bands", [])
    gap = max(bands, key=lambda b: abs(b["hit"] - b["expected"])) if bands else None
    weak = sorted([(v["accuracy"], v["name"], v["n"]) for v in (rec.get("byLeague") or {}).values() if v.get("n", 0) >= 30])
    misses = []
    for g in ((rec.get("listDays") or [{}])[0].get("games") or []):
        if g.get("ok") is False:
            misses.append(f"{g['home']} v {g['away']} ({pct(g['confidence'])}, finished {g['result'][0]}-{g['result'][1]})")
    runs = d["runs"]; ok = sum(1 for r in runs[:10] if r.get("conclusion") == "success")
    failed = [r for r in runs[:10] if r.get("conclusion") == "failure"]
    msgs = [c["commit"]["message"].split("\n")[0] for c in d["commits"]]
    exp_msgs = [m for m in msgs if any(k in m.lower() for k in ["test", "retune", "rejected", "tune"])]
    by_sport = {k: v for k, v in (d["srec"].get("bySport") or {}).items() if v}
    tov = d["trec"].get("overall") or {}
    focus = f"Lift accuracy in {weak[0][1]} ({pct(weak[0][0])} over {weak[0][2]} games)" if weak else "Hold calibration steady"

    say("chief", f"Model record: {pct(ov.get('accuracy'))} over {ov.get('n',0)} graded games; Daily List {pct(lst.get('accuracy'))} ({lst.get('correct',0)}/{lst.get('n',0)}).",
        f"Focus: {focus}.", "None." if not failed else f"{len(failed)} failed pipeline run(s).")
    say("scout", f"Swept {len(preds)} football fixtures across {leagues} competitions for {d['pdate']}, plus {len(d['spreds'])} other-sport and {len(d['tpreds'])} tennis matches.",
        "Next sweep at 13:00 for late-added fixtures and kick-off changes.")
    say("quality", f"{unrated} unrated fixtures in today's slate; {leagues} competitions matched to a rated team pool.",
        "Recheck club-name matching for new API-Football leagues.", "None." if unrated == 0 else f"{unrated} fixtures need team ratings.")
    say("source", f"Coverage is API-Football plus free sources; {ok}/{min(10,len(runs))} recent builds pulled data cleanly.",
        "Watch API rate limits during the 03:00 and 13:00 sweeps.")
    c = d["calib"].get("check", {})
    say("ratings", f"Calibration refit {d['calib'].get('fitted','?')}: log loss {c.get('fitted','?')} vs shipped {c.get('shipped','?')} (delta {c.get('delta','?')}).",
        f"Rate today's {len(preds)} fixtures; overall log loss is {ov.get('logLoss','?')}.")
    tr = d["tune"]
    say("experiment", (f"Weekly retune {tr.get('generated','?')} {'passed' if tr.get('pass') else 'failed'} its gates. " if tr else "") + (f"Latest test: {exp_msgs[0]}." if exp_msgs else ""),
        "Overnight at 23:30: backtest one change aimed at the weakest league.")
    sport_txt = ", ".join(f"{k.upper()} {v['correct']}/{v['n']}" for k, v in by_sport.items()) or "no graded games yet"
    say("sports", f"Other sports: {sport_txt}. Tennis {pct(tov.get('accuracy'))} over {tov.get('n',0)} matches (expected {pct(tov.get('expected'))}).",
        "Build up NBA and rugby graded history before they go on the board.",
        "NBA and rugby have no graded games yet." if not by_sport.get("nba") else "None.")
    say("auditor", f"Graded {day.get('date','last day')}: {day.get('correct',0)}/{day.get('n',0)} correct ({pct(day.get('accuracy'))})." + (f" Daily List misses: {'; '.join(misses[:3])}." if misses else ""),
        "Grade early kick-offs at 13:00 and the full day at 23:30.")
    if gap:
        say("calib", f"Biggest calibration gap: picks at {pct(gap['from'])}-{pct(gap['to'])} won {pct(gap['hit'])} vs {pct(gap['expected'])} expected ({gap['n']} games).",
            "Track tiers: " + ", ".join(f"{t['name']} {pct(t['hit'])} vs {pct(t['expected'])}" for t in rec.get("tiers", [])[:3]) + ".")
    else:
        say("calib", "No calibration bands available.", "Rebuild bands after grading.")
    top = "; ".join(f"{p['home']} v {p['away']} {pct(p['confidence'])}" for p in listed[:3])
    say("curator", f"Daily List for {d['pdate']}: {len(listed)} picks. Top: {top or 'none'}.",
        "Re-rank at 13:00 if any team news shifts confidence.")
    say("engineer", f"{ok}/{min(10,len(runs))} recent 'Rebuild and publish' runs green.",
        "Keep the build ahead of the 03:00 sweep.", "None." if not failed else f"Failed: {failed[0]['name']} {failed[0]['createdAt'][:16]}")

    prs = d.get("prs") or []
    for line in L:
        mine = [p for p in prs if p["owner"] == line["agent"] and p["status"] not in ("closed",)][:1]
        if mine: line["today"] += f" Dev work: {pr_line(mine[0])}."
    shipped = [p for p in prs if p["status"] == "shipped"]
    tiers = {t["name"]: t for t in rec.get("tiers", [])}
    strong = tiers.get("Strong", {})
    maxgap = max((abs(b["hit"] - b["expected"]) for b in bands), default=None)
    def obj(owner, name, actual, target, fmt="pct", higher=True):
        if actual is None: status = "no data"
        else:
            ok = actual >= target if higher else actual <= target
            near = (actual >= target * 0.93) if higher else (actual <= target * 1.25)
            status = "on track" if ok else ("at risk" if near else "behind")
        return {"owner": owner, "name": name, "actual": actual, "target": target, "fmt": fmt, "higher": higher, "status": status}
    OBJ = [
        obj("curator", "Daily List hit rate", lst.get("accuracy"), 0.70),
        obj("chief", "Overall hit rate", ov.get("accuracy"), 0.55),
        obj("ratings", "Strong tier hit rate", strong.get("hit"), 0.80),
        obj("calib", "Largest calibration gap", maxgap, 0.05, higher=False),
        obj("scout", "Competitions covered today", leagues, 150, fmt="num"),
        obj("quality", "Unrated fixtures", unrated, 0, fmt="num", higher=False),
        obj("source", "Clean data pulls (last 10)", ok / max(1, min(10, len(runs))), 0.95),
        obj("engineer", "Builds green (last 10)", ok / max(1, min(10, len(runs))), 1.0),
        obj("sports", "Tennis hit vs expected", (tov.get("accuracy") or 0) - (tov.get("expected") or 0) if tov else None, 0.0, fmt="pt"),
        obj("experiment", "Weekly retune passed", 1 if tr.get("pass") else 0, 1, fmt="bool"),
        obj("auditor", "Graded days in record", len(rec.get("days") or []), 14, fmt="num"),
    ]
    import org as ORG
    org_path = os.path.join(DATA, "org.json")
    org = ORG.load(org_path)
    org, new_hire = ORG.review(d, org, datetime.now(UK).date().isoformat(), None) if trigger.startswith(("scheduled", "on demand")) else (org, None)
    if new_hire:
        json.dump(org, open(org_path, "w"), indent=1)
    for h in org["hires"]: NAMES[h["id"]] = h["name"]
    hl, hobj = ORG.lines_and_objectives(d, org)
    L.extend(hl); OBJ.extend(hobj)
    if new_hire:
        dept = (org["departments"].get(new_hire["d"]) or {}).get("name")
        L.append({"agent": "chief", "yesterday": f"New hire: {new_hire['name']} joins as {new_hire['role']}. {new_hire['reason']}",
                  "today": f"{new_hire['name']} owns one KPI from today: {hobj[-1]['name']}." + (f" New department: {dept}." if dept and org['departments'][new_hire['d']].get('opened') == new_hire['hired'] else ""),
                  "blockers": "None.", "hire": new_hire["id"]})
    def margin(o):
        if o["actual"] is None or o["status"] != "on track": return -9
        a, t = o["actual"], o["target"]
        return (a - t) / (abs(t) or 1) if o["higher"] else (t - a) / (abs(t) or 1)
    star = max(OBJ, key=margin)
    hits = [g for g in ((rec.get("listDays") or [{}])[0].get("games") or []) if g.get("ok")]
    misses_g = [g for g in ((rec.get("listDays") or [{}])[0].get("games") or []) if g.get("ok") is False]
    L.append({"agent": "chief", "yesterday": f"Shout-out: {NAMES.get(star['owner'], star['owner'])} for '{star['name']}' — ahead of target.", "today": "Keep encouraging each other: every objective owner posts one learning in the playback.", "blockers": "None.", "kudos": star["owner"]})
    s = {"id": int(time.time() * 1000), "time": datetime.now(UK).isoformat(), "trigger": trigger, "lines": L,
         "objectives": OBJ, "star": star["owner"],
         "wins": [f"{g['home']} v {g['away']} ({pct(g['confidence'])}) finished {g['result'][0]}-{g['result'][1]}" for g in sorted(hits, key=lambda g: -g["confidence"])[:5]],
         "dev": prs[:12], "shipped": [pr_line(p) + f" by {NAMES.get(p['owner'], p['owner'])}" for p in shipped[:6]],
         "lessons": ([f"Daily List miss: {m}" for m in misses[:3]] +
                     ([f"Calibration: {pct(gap['from'])}-{pct(gap['to'])} band won {pct(gap['hit'])} vs {pct(gap['expected'])} expected"] if gap else []) +
                     ([f"Weakest league: {weak[0][1]} at {pct(weak[0][0])} over {weak[0][2]} games"] if weak else [])),
         "stats": {"fixtures": len(preds), "competitions": leagues, "listPicks": len(listed),
                   "overallAcc": ov.get("accuracy"), "listAcc": lst.get("accuracy"), "listN": lst.get("n"),
                   "graded": ov.get("n"), "logLoss": ov.get("logLoss"), "dayAcc": day.get("accuracy"), "dayDate": day.get("date"),
                   "tennisAcc": tov.get("accuracy"), "runsOk": ok, "runsTotal": min(10, len(runs)),
                   "tiers": rec.get("tiers", []), "bands": bands,
                   "days": [{"date": x["date"], "acc": x["accuracy"], "n": x["n"]} for x in (rec.get("days") or [])[:14]],
                   "weak": [{"name": w[1], "acc": w[0], "n": w[2]} for w in weak[:5]],
                   "top": [{"m": f"{p['home']} v {p['away']}", "c": p["confidence"], "lg": p["league"]} for p in listed[:8]]}}
    STATE["standups"].insert(0, s); STATE["standups"] = STATE["standups"][:120]
    _save("standups.json", STATE["standups"])
    return s

def build_report(period="day"):
    s = build_standup(f"{period} playback")
    STATE["standups"].pop(0); _save("standups.json", STATE["standups"])
    since = datetime.now(UK) - (timedelta(days=7) if period == "week" else timedelta(days=1))
    recent = [x for x in STATE["standups"] if datetime.fromisoformat(x["time"]) >= since]
    trend = [{"time": x["time"], "listAcc": x["stats"].get("listAcc"), "overallAcc": x["stats"].get("overallAcc")} for x in recent]
    chats = [c for c in STATE["chats"] if datetime.fromisoformat(c["time"]) >= since][:20]
    r = {"id": int(time.time() * 1000), "time": datetime.now(UK).isoformat(), "period": period,
         "objectives": s["objectives"], "star": s["star"], "wins": s["wins"], "lessons": s["lessons"],
         "dev": s.get("dev", []), "shipped": [x for x in s.get("shipped", []) if True],
         "standups": len(recent), "trend": trend, "chats": chats, "stats": s["stats"],
         "next": [o["name"] + " — " + o["owner"] for o in s["objectives"] if o["status"] in ("behind", "at risk")][:5]}
    STATE["reports"].insert(0, r); STATE["reports"] = STATE["reports"][:60]; _save("reports.json", STATE["reports"])
    return r


NAMES = {"chief": "Luke", "scout": "Ava", "quality": "Cory", "source": "Raj", "ratings": "Ben", "experiment": "Mia",
         "sports": "Theo", "auditor": "Susie", "calib": "Andrew", "curator": "Nina", "engineer": "Allan"}
SPOTS = ["the north water cooler", "the water cooler by Validation", "the canteen water cooler", "the coffee bar", "the canteen", "the aquarium"]

def make_chats(s, n=2):
    """Water-cooler chats grounded in today's numbers; saved so the playback can quote them."""
    st, ob = s["stats"], s.get("objectives", [])
    weak = (st.get("weak") or [None])[0]; top = (st.get("top") or [None])[0]
    lean = next((t for t in st.get("tiers", []) if t["name"] == "Lean"), None)
    behind = [o for o in ob if o["status"] != "on track"]
    star = s.get("star")
    pool = [
        [("curator", f"Daily List is at {pct(st.get('listAcc'))}. 70% is in reach."), ("ratings", "Let's get there. I'll flag any shaky Strong picks before 04:00.")],
        [("scout", f"{st.get('competitions')} competitions swept and zero unrated fixtures."), ("ratings", "Great sweep, that makes my job much easier.")],
        [("engineer", f"Builds are {st.get('runsOk')}/{st.get('runsTotal')} green."), ("source", "Nice. Let's keep the pipeline ahead of the 03:00 sweep.")],
        [("sports", "Tennis is a different beast, surface matters so much."), ("experiment", "Agreed. Surface Elo is the next thing I want to test.")],
    ]
    if weak: pool.append([("auditor", f"{weak['name']} is still our weak spot at {pct(weak['acc'])}."), ("experiment", "I'll queue a home-advantage backtest for that league tonight."), ("quality", "Send me the misses and I'll check the club matching too.")])
    if lean: pool.append([("calib", f"Lean tier is winning {pct(lean['hit'])} vs {pct(lean['expected'])} expected."), ("ratings", "So we're under-confident there. Could promote some Leans to Firm."), ("experiment", "Worth an experiment. I'll draft it for Friday.")])
    if top: pool.append([("curator", f"Have you seen {top['m']} at {pct(top['c'])}? Biggest mismatch on the board."), ("scout", "That's exactly the best-v-worst game we're built to find.")])
    if star: pool.append([("chief", f"Congrats on Agent of the Week, {NAMES.get(star, star)}!"), (star, "Thanks! It's the whole team's data that gets us there.")])
    for o in ob:
        if o["owner"].startswith("h") and o["owner"] in NAMES:
            pool.append([("chief", f"How's the first stretch going, {NAMES[o['owner']]}?"), (o["owner"], f"Good. My KPI is '{o['name']}' and it's {o['status']} today."), ("auditor", "Shout if you need the graded misses, I keep them all.")])
            break
    if behind: pool.append([("chief", f"We've got {len(behind)} objectives not yet on track."), (behind[0]["owner"], f"I own '{behind[0]['name']}'. A second pair of eyes on yesterday's misses would help."), ("auditor", "I'm on it after the 13:00 grading.")])
    out = []
    for lines in random.sample(pool, min(n, len(pool))):
        c = {"time": datetime.now(UK).isoformat(), "spot": random.choice(SPOTS), "lines": [{"a": a, "t": t} for a, t in lines]}
        out.append(c)
    STATE["chats"] = out + STATE["chats"]; STATE["chats"] = STATE["chats"][:200]; _save("chats.json", STATE["chats"])
    return out

SITE_BASE = "https://douglasbakeronline.github.io/footyalmanac/"
SITE_DATA = SITE_BASE + "data.json"

def write_picks():
    """The next seven days of picks from footyalmanac's published site data, for the Picks desk. No AI tokens."""
    import urllib.request
    try:
        with urllib.request.urlopen(SITE_DATA, timeout=60) as r: d = json.load(r)
    except Exception as e:
        print("picks: could not fetch site data:", e); return
    days = []
    for day in d.get("days", []):
        games = []
        for g in sorted(day.get("games", []), key=lambda g: -(g.get("confidence") or 0)):
            p = g.get("p") or {}
            side = max(p, key=p.get) if p else "h"
            acc = g.get("accuracy") or {}
            games.append({"t": g.get("time"), "ko": g.get("kickoff"), "lg": g.get("league"), "lgName": g.get("leagueName"),
                          "country": g.get("country"), "h": g["home"]["name"], "a": g["away"]["name"], "side": side,
                          "pick": {"h": g["home"]["name"], "a": g["away"]["name"], "d": "Draw"}[side],
                          "c": g.get("confidence"), "p": p, "score": g.get("score"), "btts": g.get("btts"), "o25": g.get("over25"),
                          "hit": acc.get("hit"), "hitN": acc.get("n"), "celtic": bool(g.get("celtic")),
                          "list": bool(g.get("list")), "reserve": bool(g.get("reserve")), "unrated": bool(g.get("unrated"))})
        days.append({"date": day["date"], "count": len(games), "games": games})
    # The site's Daily List spans every sport: add tennis and the other sports' list and reserve picks,
    # so the office never shows "0 picks" on a day the site has some (5 Oct 2026).
    extra = {}
    for g in other_sport_picks():
        extra.setdefault(g.pop("date"), []).append(g)
    for day in days:
        day["games"] = sorted(day["games"] + extra.pop(day["date"], []), key=lambda g: -(g.get("c") or 0))
        day["count"] = len(day["games"])
    for date in sorted(extra):
        days.append({"date": date, "count": len(extra[date]), "games": sorted(extra[date], key=lambda g: -(g.get("c") or 0))})
    days.sort(key=lambda d: d["date"])
    _save("picks.json", {"generated": d.get("generated"), "fetched": datetime.now(UK).isoformat(),
                         "bar": (d.get("list") or {}).get("min"), "days": days, "yesterday": list_yesterday()})


def _site_js(name):
    """window.__X__={...}; published by the site build -> dict."""
    import urllib.request
    try:
        with urllib.request.urlopen(SITE_BASE + name, timeout=60) as r: txt = r.read().decode("utf-8")
        return json.loads(txt[txt.index("=") + 1:].strip().rstrip(";"))
    except Exception as e:
        print(f"picks: could not read {name}:", e); return {}


def other_sport_picks():
    out = []
    for m in (_site_js("tennis-data.js").get("matches") or []):
        if not (m.get("list") or m.get("reserve")): continue
        out.append({"date": m.get("date"), "t": m.get("time"), "lg": m.get("tour"), "lgName": f"{m.get('tour')} · {m.get('tournament')}",
                    "sport": "tennis", "h": m.get("playerA"), "a": m.get("playerB"), "side": "h" if m.get("pick") == m.get("playerA") else "a",
                    "pick": m.get("pick"), "c": m.get("confidence"), "hit": (m.get("accuracy") or {}).get("hit"),
                    "hitN": (m.get("accuracy") or {}).get("n"), "list": bool(m.get("list")), "reserve": bool(m.get("reserve"))})
    for code, sp in ((_site_js("sports-data.js").get("sports")) or {}).items():
        for g in sp.get("games") or []:
            if not (g.get("list") or g.get("reserve")) or not g.get("when"): continue
            ko = datetime.fromisoformat(g["when"].replace("Z", "+00:00")).astimezone(UK)
            out.append({"date": ko.date().isoformat(), "t": ko.strftime("%H:%M"), "ko": g["when"], "lg": code, "lgName": g.get("label") or sp.get("name"),
                        "sport": code, "h": g.get("home"), "a": g.get("away"), "side": "h" if g.get("pick") == g.get("home") else "a",
                        "pick": g.get("pick"), "c": g.get("confidence"), "hit": (g.get("accuracy") or {}).get("hit"),
                        "hitN": (g.get("accuracy") or {}).get("n"), "list": bool(g.get("list")), "reserve": bool(g.get("reserve"))})
    return out


def list_yesterday():
    """Yesterday's Daily List across every sport, graded, from the three record files."""
    day = (datetime.now(UK).date() - timedelta(days=1)).isoformat()
    rows = []
    for f, sport in (("record.json", "football"), ("tennis-record.json", "tennis"), ("sports-record.json", None)):
        for d in ((raw(f) or {}).get("days") or []):
            if d.get("date") != day: continue
            for g in d.get("games", []):
                if not g.get("list"): continue
                h = g.get("home") or g.get("playerA"); a = g.get("away") or g.get("playerB")
                pick = g.get("pick")
                if sport == "football": pick = {"h": h, "a": a, "d": "Draw"}.get(pick, pick)
                sc = g.get("result") if sport == "football" else g.get("score")
                rows.append({"sport": sport or (g.get("label") or "other"), "h": h, "a": a, "pick": pick, "c": g.get("confidence"),
                             "ok": g.get("ok"), "score": sc if isinstance(sc, list) else None,
                             "note": g.get("note") if sport == "tennis" else None})
    graded = [r for r in rows if r["ok"] is not None]
    return {"date": day, "n": len(rows), "graded": len(graded), "won": sum(1 for r in graded if r["ok"]),
            "rows": sorted(rows, key=lambda r: (r["ok"] is not False, -(r["c"] or 0)))}

def write_activity():
    cm = gh_json(["api", f"repos/{REPO}/commits?per_page=20"]) or []
    runs = gh_json(["run", "list", "-R", REPO, "-L", "10", "--json", "name,conclusion,createdAt,url"]) or []
    _save("activity.json", {"prs": agent_prs(), "fetched": datetime.now(UK).isoformat(),
        "commits": [{"sha": c["sha"][:7], "msg": c["commit"]["message"].split("\n")[0], "date": c["commit"]["author"]["date"], "url": c["html_url"]} for c in cm if isinstance(c, dict)],
        "runs": runs})

def work_summary(item, s):
    st = s["stats"]
    return {"Fixture sweep": f"Swept {st['fixtures']:,} fixtures across {st['competitions']} competitions.",
            "Predictions ranked": f"Daily List built: {st['listPicks']} picks, top {st['top'][0]['m'] if st.get('top') else 'n/a'}.",
            "Midday refresh": f"Refreshed fixtures and graded early results; last day {pct(st.get('dayAcc'))}.",
            "Results & experiments": f"Day graded; overall {pct(st.get('overallAcc'))}, Daily List {pct(st.get('listAcc'))}."}.get(item["name"], item["desc"])

def run(slot=None, force=False):
    now = datetime.now(UK); today = now.date().isoformat()
    done = {e["key"] for e in STATE["events"]}
    due = []
    if slot:
        due = ([i for i in RHYTHM if i["kind"] == "saturday" and i.get("dow") == {"preview": 4, "final": 5, "review": 6}.get(STAGE or "", now.weekday())][:1] or [i for i in RHYTHM if i["kind"] == "saturday"][:1]) if slot == "saturday" else [i for i in RHYTHM if i["kind"] == slot or i["t"] == slot] [:1] or [{"t": now.strftime("%H:%M"), "kind": slot, "name": slot, "who": "all", "desc": "On-demand run"}]
    else:
        for item in RHYTHM:
            h, m = map(int, item["t"].split(":"))
            at = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if "dow" in item and now.weekday() != item["dow"]: continue
            if timedelta(0) <= now - at <= timedelta(minutes=95) and f"{today}-{item['t']}" not in done:
                due.append(item)
    if not due:
        print("Nothing due at", now.strftime("%H:%M"), "UK"); write_activity(); write_picks(); return
    for item in due:
        key = f"{today}-{item['t']}" + ("-manual-" + now.strftime("%H%M%S") if slot else "")
        kind = item["kind"]
        print("Running", item["name"], kind, flush=True)
        if kind == "standup":
            s = build_standup("on demand" if slot else f"scheduled {item['t']}"); _save("latest.json", s); make_chats(s, 2); summary = f"{len(s['lines'])} updates, {sum(o['status']=='on track' for o in s['objectives'])}/{len(s['objectives'])} objectives on track."
        elif kind == "report":
            r = build_report("week" if (now.weekday() == 6 and not slot) or item.get("period") == "week" else "day"); summary = f"{r['period'].title()} playback: {sum(o['status']=='on track' for o in r['objectives'])}/{len(r['objectives'])} on track; star {NAMES.get(r['star'])}."
        elif kind in ("briefing", "refresh"):
            import markets as MK
            b = MK.run(kind)
            summary = f"{len(b['groups'])} groups of five posted" + (f", Steady at {b['groups'][0]['odds']:.2f}" if b["groups"] else "") + "."
        elif kind == "saturday":
            import saturday as SAT
            write_picks()
            stage = STAGE or {4: "preview", 5: "final", 6: "review"}.get(item.get("dow"), SAT.stage_for(now))
            b = SAT.build(stage, now, _load("picks.json", {}), raw("record.json") or {}, NAMES)
            b["issue"] = SAT.post(b, NAMES)
            hist = [x for x in _load("saturday.json", []) if not (x["date"] == b["date"] and x["stage"] == b["stage"])]
            _save("saturday.json", ([b] + hist)[:24])
            summary = next((l["text"] for l in b["lines"] if l["agent"] in ("curator", "auditor")), b["lines"][0]["text"])
        else:
            s = build_standup("work"); STATE["standups"].pop(0); _save("standups.json", STATE["standups"]); make_chats(s, 1); summary = work_summary(item, s)
            _save("latest.json", s)
        STATE["events"].insert(0, {"key": key, "time": now.isoformat(), "t": item["t"], "name": item["name"], "kind": kind, "who": item["who"], "summary": summary})
    STATE["events"] = STATE["events"][:300]; _save("events.json", STATE["events"])
    _save("rhythm.json", {"rhythm": RHYTHM, "updated": now.isoformat()})
    write_activity(); write_picks()

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--slot", default="", help="standup | report | work | blank for schedule")
    ap.add_argument("--period", default="day")
    ap.add_argument("--stage", default="", help="saturday slot: preview | final | review (default by weekday)")
    a = ap.parse_args()
    if a.slot == "report" and a.period == "week":
        RHYTHM = [dict(i, period="week") if i["kind"] == "report" else i for i in RHYTHM]
    STAGE = a.stage or None
    run(a.slot or None)
