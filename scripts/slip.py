"""Douglas's slip: tell the agents what you've backed. No AI tokens.

add    match each selection to footyalmanac's published picks (football, other sports, tennis),
       record it in docs/data/slips.json, and post the agents' read as a GitHub issue (label my-slip)
grade  settle legs from footyalmanac's graded records; comment on the issue as legs land and close it when done

Selections are names as you'd write them ("Coco Gauff", "Hamilton", "Lions"), one per line or comma separated.
"""
import argparse, json, os, re, subprocess, sys, unicodedata, urllib.request
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

UK = ZoneInfo("Europe/London")
HQ = "douglasbakeronline/footyalmanac-hq"
FA = "douglasbakeronline/footyalmanac"
SITE = "https://douglasbakeronline.github.io/footyalmanac/data.json"
DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "data")
PATH = os.path.join(DATA, "slips.json")

def pct(x): return "–" if x is None else f"{x*100:.0f}%"
def norm(s): return re.sub(r"[^a-z0-9 ]", "", unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()).strip()

def gh(args, inp=None):
    try:
        r = subprocess.run(["gh"] + args, capture_output=True, text=True, timeout=90, input=inp)
        return r.stdout.strip() if r.returncode == 0 else None
    except Exception: return None

def raw(path):
    out = gh(["api", f"repos/{FA}/contents/{path}", "-H", "Accept: application/vnd.github.raw"])
    try: return json.loads(out) if out else None
    except Exception: return None

def latest(folder):
    ls = gh(["api", f"repos/{FA}/contents/{folder}", "--jq", "[.[].name] | sort | last"])
    return raw(f"{folder}/{ls}") if ls else None

def uk(iso):
    try: return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(UK)
    except Exception: return None

def candidates():
    """Every pick footyalmanac has published for the next few days, as (names, leg)."""
    out = []
    try:
        with urllib.request.urlopen(SITE, timeout=60) as r: site = json.load(r)
    except Exception: site = {}
    for day in (site.get("days") or [])[:3]:
        for g in day.get("games", []):
            p = g.get("p") or {}; h, a = g["home"]["name"], g["away"]["name"]
            when = g.get("kickoff")
            for side, team in (("h", h), ("a", a)):
                out.append(([team], {"sport": "football", "event": f"{h} v {a}", "comp": g.get("leagueName"), "when": when,
                                     "selection": team, "side": side, "p": p.get(side), "modelPick": {"h": h, "a": a, "d": "Draw"}[max(p, key=p.get)] if p else None,
                                     "modelConf": g.get("confidence"), "list": bool(g.get("list")), "reserve": bool(g.get("reserve")),
                                     "hit": (g.get("accuracy") or {}).get("hit"), "home": h, "away": a, "date": day["date"]}))
    for g in latest("predictions-sports") or []:
        for team in (g["home"], g["away"]):
            p = g["pHome"] if team == g["home"] else 1 - g["pHome"]
            out.append(([team], {"sport": g["sport"], "event": f"{g['home']} v {g['away']}", "comp": g.get("label"), "when": g.get("when"),
                                 "selection": team, "p": round(p, 4), "modelPick": g.get("pick"), "modelConf": g.get("confidence"),
                                 "tier": g.get("tier"), "list": bool(g.get("list")), "hit": (g.get("accuracy") or {}).get("hit"), "id": g.get("id")}))
    for g in latest("predictions-tennis") or []:
        for who, key in ((g["playerA"], "a"), (g["playerB"], "b")):
            names = [who] + [n for n in (g.get("espn") or []) if norm(n.split()[-1]) == norm(who.split()[-1])]
            when = f"{g['date']}T{g['time']}:00Z" if g.get("time") else None
            out.append((names, {"sport": "tennis", "event": f"{g['playerA']} v {g['playerB']}", "comp": f"{g.get('tournament')} {g.get('round') or ''}".strip(),
                                "when": when, "selection": who, "p": (g.get("p") or {}).get(key), "modelPick": g.get("pick"),
                                "modelConf": g.get("confidence"), "tier": g.get("tier"), "list": bool(g.get("list")),
                                "hit": (g.get("accuracy") or {}).get("hit"), "id": g.get("id"), "date": g.get("date")}))
    return out

def match(sel, cands, now):
    q = norm(sel)
    def score(names):
        best = 0
        for n in names:
            n = norm(n)
            if n == q: best = max(best, 3)
            elif re.search(rf"\b{re.escape(q)}\b", n): best = max(best, 2)
        return best
    hits = [(score(n), leg) for n, leg in cands]
    hits = [(s, l) for s, l in hits if s]
    if not hits: return None
    def soon(l):
        t = uk(l["when"]) if l.get("when") else None
        return abs((t - now).total_seconds()) if t else 9e9
    hits.sort(key=lambda x: (-x[0], soon(x[1])))
    return dict(hits[0][1], asked=sel)

def load():
    try: return json.load(open(PATH))
    except Exception: return []

def save(slips):
    json.dump(slips, open(PATH, "w"), indent=1, ensure_ascii=False)

def leg_line(l):
    t = uk(l["when"]) if l.get("when") else None
    when = t.strftime("%a %H:%M") if t else "time tbc"
    agree = "agrees" if l.get("modelPick") == l["selection"] else f"model prefers {l.get('modelPick')}"
    status = {"won": "WON", "lost": "LOST", "void": "VOID"}.get(l.get("status"), "")
    return f"| {l['selection']} | {l['event']} | {l.get('comp') or ''} | {when} | {pct(l.get('p'))} | {agree} | {status} |"

def read_out(s):
    legs = [l for l in s["legs"] if l.get("p") is not None]
    acc = 1.0
    for l in legs: acc *= l["p"]
    weakest = min(legs, key=lambda l: l["p"]) if legs else None
    against = [l for l in legs if l.get("modelPick") != l["selection"]]
    unmatched = [l["asked"] for l in s["legs"] if l.get("p") is None]
    fb = [l for l in legs if l["sport"] == "football"]; ten = [l for l in legs if l["sport"] == "tennis"]; oth = [l for l in legs if l["sport"] not in ("football", "tennis")]
    lines = [
        ("Nina (Daily Board)", f"Got it, {len(s['legs'])} selections logged. All {len(legs) - len(against)} matched legs agree with our model." if not against else
         f"Logged. {len(against)} leg{'s' if len(against) > 1 else ''} go against our model: " + ", ".join(f"{l['selection']} ({pct(l['p'])})" for l in against) + "."),
        ("Andrew (Calibration)", f"If the legs are independent and our probabilities are right, all {len(legs)} land together about {pct(acc)} of the time. "
         f"The weakest link is {weakest['selection']} at {pct(weakest['p'])}." if weakest else "No probabilities to combine."),
    ]
    if fb: lines.append(("Ben (Ratings)", "Football: " + "; ".join(f"{l['selection']} {pct(l['p'])}{' (Daily List)' if l.get('list') else ' (reserve)' if l.get('reserve') else ''}" for l in fb) + "."))
    if ten or oth: lines.append(("Theo (New Sports)", "; ".join(f"{l['selection']} {pct(l['p'])} ({l.get('tier') or 'no tier'})" for l in ten + oth) + ". Tennis times are scheduled starts and can slip."))
    if unmatched: lines.append(("Cory (Data Quality)", "I couldn't find these in today's published picks: " + ", ".join(unmatched) + ". Tell me the opponent and I'll match them."))
    lines.append(("Susie (Auditor)", "I'll settle each leg from the graded records as results come in and post the outcome here."))
    return lines, acc

def body(s):
    lines, acc = read_out(s)
    t = ["Douglas has gone with these. The agents' read:", "",
         "| Selection | Event | Competition | UK time | Our probability | Model | Result |", "|---|---|---|---|---|---|---|"]
    t += [leg_line(l) for l in s["legs"]]
    t += ["", *[f"**{who}:** {txt}" for who, txt in lines], "",
          "Probabilities are footyalmanac's published model numbers, not bookmaker odds. This is information, not betting advice."]
    return "\n".join(t)

def add(text, issue=None):
    now = datetime.now(UK)
    sels = [x.strip() for x in re.split(r"[\n,]+", text) if x.strip() and not x.strip().startswith("#")]
    cands = candidates()
    legs = [match(x, cands, now) or {"asked": x, "selection": x, "event": "not found", "p": None} for x in sels]
    for l in legs: l["status"] = "pending"
    legs.sort(key=lambda l: l.get("when") or "9")
    slips = load()
    s = {"id": int(now.timestamp() * 1000), "time": now.isoformat(), "legs": legs, "status": "open"}
    _, acc = read_out(s); s["combined"] = round(acc, 4)
    title = f"Douglas's slip, {now.strftime('%a %d %b')}: {len(legs)} selections"
    gh(["label", "create", "my-slip", "-R", HQ, "--color", "c8102e", "--description", "Douglas's selections for the agents to track", "--force"])
    if issue:
        gh(["issue", "comment", str(issue), "-R", HQ, "--body", body(s)]); s["issue"] = int(issue)
    else:
        url = gh(["issue", "create", "-R", HQ, "--title", title, "--label", "my-slip", "--body", body(s)])
        if url: s["issue"] = int(url.rstrip("/").split("/")[-1]); s["url"] = url
    slips.insert(0, s); save(slips[:60])
    print(body(s)); return s

def grade():
    slips = load(); open_ = [s for s in slips if s.get("status") == "open"]
    if not open_: return
    rec, srec, trec = raw("record.json") or {}, raw("sports-record.json") or {}, raw("tennis-record.json") or {}
    fb = {(norm(g["home"]), norm(g["away"])): g for d in rec.get("days") or [] for g in d.get("games") or []}
    sp = {str(g.get("id")): g for d in srec.get("days") or [] for g in d.get("games") or []}
    tn = {str(g.get("key")): g for d in trec.get("days") or [] for g in d.get("games") or []}
    for s in open_:
        newly = []
        for l in s["legs"]:
            if l.get("status") != "pending" or l.get("p") is None: continue
            res = None
            if l["sport"] == "football":
                g = fb.get((norm(l["home"]), norm(l["away"])))
                if g and g.get("result"):
                    h, a = g["result"]; win = "h" if h > a else "a" if a > h else "d"
                    res = ("won" if win == l["side"] else "lost", f"{h}-{a}")
            elif l["sport"] == "tennis":
                g = tn.get(str(l.get("id")))
                if g: res = ("void", "void") if g.get("void") else ("won" if norm(g.get("winner")) == norm(l["selection"]) else "lost", g.get("note") or g.get("winner"))
            else:
                g = sp.get(str(l.get("id")))
                if g and g.get("winner"): res = ("won" if norm(g["winner"]) == norm(l["selection"]) else "lost", "-".join(map(str, g.get("score") or [])))
            if res:
                l["status"], l["result"] = res; newly.append(l)
        done = all(l.get("status") != "pending" for l in s["legs"] if l.get("p") is not None)
        if newly and s.get("issue"):
            msg = "**Susie (Auditor):** " + "; ".join(f"{l['selection']} {l['status']} ({l['result']})" for l in newly) + "."
            if done:
                won = sum(l["status"] == "won" for l in s["legs"]); lost = sum(l["status"] == "lost" for l in s["legs"])
                msg += f"\n\nAll settled: {won} won, {lost} lost. " + ("The slip landed." if lost == 0 else "The slip didn't land; the misses go into tonight's playback as lessons.")
            gh(["issue", "comment", str(s["issue"]), "-R", HQ, "--body", msg])
        if done:
            s["status"] = "settled"
            if s.get("issue"): gh(["issue", "close", str(s["issue"]), "-R", HQ])
    save(slips)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["add", "grade"])
    ap.add_argument("--text"); ap.add_argument("--issue")
    a = ap.parse_args()
    if a.cmd == "add": add(a.text or sys.stdin.read(), a.issue)
    else: grade()
