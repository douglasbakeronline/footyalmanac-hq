"""The Chief of Staff's hiring desk. No AI tokens: rules over footyalmanac's real numbers.

Each stand-up, Luke checks where the business is short-handed. If a gap has a
clear owner-less cause, he hires a specialist (at most one a day, at most six
in total, one desk each in the Expansion Wing) or opens a new department.
Every hire gets one KPI, a reason and a hire date, and reports at every
stand-up from then on. Saved in docs/data/org.json.
"""
import json, os
from datetime import datetime

CAP = 6
NAMES = ["Priya", "Tom", "Leah", "Omar", "Grace", "Sam", "Ellie", "Kofi", "Hannah", "Marco", "Zara", "Finn"]
LOOKS = [("#e8b996", "#2b1d14"), ("#b07c58", "#16100c"), ("#f2d0b4", "#8a5a2e"), ("#8d5a3b", "#0f0b08"),
         ("#f0c8a8", "#c9a15a"), ("#d6a27e", "#3d2a1c")]
NEW_DEPTS = {
    "multi": {"name": "Multi-sport", "c": "#ffb86b"},
    "growth": {"name": "Growth & Support", "c": "#7fb2ff"},
    "markets": {"name": "Markets & Groupings", "c": "#f0b35a"},
}

def pct(x): return "–" if x is None else f"{x*100:.0f}%"

def load(path):
    try:
        with open(path) as f: return json.load(f)
    except Exception: return {"hires": [], "departments": {}, "log": []}

def metric(h, d):
    """(actual, target, higher, fmt, text) for a hire's KPI from today's data."""
    rec = d["rec"]; k = h["kpi"]
    if k["type"] == "league":
        v = (rec.get("byLeague") or {}).get(k["code"]) or {}
        a = v.get("accuracy")
        return a, k["target"], True, "pct", f"{v.get('name', k['code'])}: {pct(a)} over {v.get('n', 0)} graded games (target {pct(k['target'])}), {v.get('drawnOut', 0)} drawn out."
    if k["type"] == "draws":
        t = {x["name"]: x for x in rec.get("tiers") or []}.get("Strong") or {}
        a = (t.get("drawnOut", 0) / t["n"]) if t.get("n") else None
        return a, k["target"], False, "pct", f"Strong tier: {t.get('drawnOut', 0)} of {t.get('n', 0)} calls drawn out ({pct(a)}, target {pct(k['target'])} or less)."
    if k["type"] == "builds":
        runs = d["runs"][:10]; ok = sum(1 for r in runs if r.get("conclusion") == "success")
        a = ok / len(runs) if runs else None
        return a, k["target"], True, "pct", f"{ok}/{len(runs)} recent builds green (target {pct(k['target'])})."
    if k["type"] == "sport":
        v = (d["srec"].get("bySport") or {}).get(k["code"]) or {}
        a = (v["correct"] / v["n"]) if v.get("n") else None
        return a, k["target"], True, "pct", f"{k['code'].upper()}: {v.get('correct', 0)}/{v.get('n', 0)} correct ({pct(a)}, target {pct(k['target'])})."
    if k["type"] == "listhit":
        v = rec.get("list") or {}
        a = v.get("accuracy")
        return a, k["target"], True, "pct", f"Daily List {pct(a)} over {v.get('n', 0)} picks: the proof we take to market (target {pct(k['target'])})."
    if k["type"] in ("priced", "grouplegs"):
        import markets as M
        share, hit, n = M.kpis()
        if k["type"] == "priced":
            return share, k["target"], True, "pct", (f"{pct(share)} of today's picks carry a live bookmaker price (target {pct(k['target'])})." if share is not None else "No prices collected yet.")
        return hit, k["target"], True, "pct", (f"Group legs won: {pct(hit)} of {n} settled over 30 days (target {pct(k['target'])})." if hit is not None else "No group legs settled yet.")
    return None, k.get("target"), True, "pct", "No data yet."

NEXT = {
    "league": "Review every miss in the league with Mia and queue one tested change.",
    "draws": "Tag drawn-out Strong calls by league and draw probability for the next experiment.",
    "builds": "Trace each failed build to its cause and add a guard.",
    "sport": "Grow graded history before the sport goes on the board.",
    "listhit": "Prepare the launch story from the published, graded record.",
    "priced": "Price every candidate leg before the 07:45 briefing and flag anything still on an estimate.",
    "grouplegs": "Build today's three groups of five and review every losing leg in the playback.",
}

def candidates(d, org):
    """Hiring needs in priority order: (key, dept, role, kpi, reason)."""
    rec = d["rec"]; have = {h["key"] for h in org["hires"]}; out = []
    weak = sorted([(v["accuracy"], c, v) for c, v in (rec.get("byLeague") or {}).items() if v.get("n", 0) >= 60])
    spec = sum(1 for h in org["hires"] if h["kpi"]["type"] == "league")
    for acc, code, v in weak[:2]:
        if acc < 0.45 and spec < 2 and f"league-{code}" not in have:
            out.append((f"league-{code}", "model", f"{v['name']} Specialist",
                        {"type": "league", "code": code, "target": 0.50},
                        f"{v['name']} is at {pct(acc)} over {v['n']} games, the weakest league, and nobody owns it full-time."))
    t = {x["name"]: x for x in rec.get("tiers") or []}.get("Strong") or {}
    if t.get("n", 0) >= 30 and t.get("drawnOut", 0) / t["n"] >= 0.15 and "draws" not in have:
        out.append(("draws", "valid", "Draw Risk Analyst", {"type": "draws", "target": 0.10},
                    f"{t['drawnOut']} of {t['n']} Strong calls were drawn out ({pct(t['drawnOut']/t['n'])}): draws are our biggest single cause of misses."))
    runs = d["runs"][:10]; ok = sum(1 for r in runs if r.get("conclusion") == "success")
    if len(runs) >= 8 and ok / len(runs) <= 0.8 and "builds" not in have:
        out.append(("builds", "eng", "Reliability Engineer", {"type": "builds", "target": 1.0},
                    f"Only {ok}/{len(runs)} recent builds were green: Allan needs a second pair of hands on the pipeline."))
    for code, v in (d["srec"].get("bySport") or {}).items():
        if v and v.get("n", 0) >= 50 and f"sport-{code}" not in have:
            out.append((f"sport-{code}", "multi", f"{code.upper()} Analyst", {"type": "sport", "code": code, "target": 0.55},
                        f"{code.upper()} has {v['n']} graded games: enough history for a dedicated analyst and a Multi-sport department."))
    lst = rec.get("list") or {}
    if lst.get("n", 0) >= 100 and (lst.get("accuracy") or 0) >= 0.70 and "growth" not in have:
        out.append(("growth", "growth", "Growth Lead", {"type": "listhit", "target": 0.70},
                    f"The Daily List is at {pct(lst['accuracy'])} over {lst['n']} picks: the accuracy is proven, so we open Growth & Support."))
    return out

def review(d, org, today, history_days):
    """Hire at most one person today. Returns (org, new_hire or None)."""
    if len(org["hires"]) >= CAP or any(h["hired"] == today for h in org["hires"]):
        return org, None
    c = candidates(d, org)
    if not c:
        return org, None
    key, dept, role, kpi, reason = c[0]
    i = len(org["hires"])
    name = next(n for n in NAMES if n not in {h["name"] for h in org["hires"]})
    skin, hair = LOOKS[i % len(LOOKS)]
    new = {"id": f"h{i+1}", "key": key, "name": name, "role": role, "d": dept, "kpi": kpi, "reason": reason,
           "hired": today, "skin": skin, "hair": hair, "slot": i}
    if dept in NEW_DEPTS and dept not in org["departments"]:
        org["departments"][dept] = dict(NEW_DEPTS[dept], opened=today)
        org["log"].insert(0, {"date": today, "type": "department", "text": f"Opened a new department: {NEW_DEPTS[dept]['name']}."})
    org["hires"].append(new)
    org["log"].insert(0, {"date": today, "type": "hire", "text": f"Hired {name} as {role}. {reason}"})
    return org, new

def lines_and_objectives(d, org):
    lines, objs = [], []
    for h in org["hires"]:
        a, t, higher, fmt, text = metric(h, d)
        if a is None: status = "no data"
        else:
            ok = a >= t if higher else a <= t
            near = (a >= t * 0.93) if higher else (a <= t * 1.25)
            status = "on track" if ok else ("at risk" if near else "behind")
        lines.append({"agent": h["id"], "yesterday": text, "today": NEXT.get(h["kpi"]["type"], "Keep going."), "blockers": "None."})
        k = h["kpi"]
        label = {"league": f"{h['role'].replace(' Specialist', '')} hit rate", "draws": "Strong calls drawn out",
                 "builds": "Builds green (last 10)", "sport": f"{k.get('code', '').upper()} hit rate",
                 "listhit": "Daily List hit rate (launch)", "priced": "Legs with a live price",
                 "grouplegs": "Group legs won (30 days)"}.get(k["type"], h["role"] + " KPI")
        objs.append({"owner": h["id"], "name": label, "actual": a, "target": t, "fmt": fmt, "higher": higher, "status": status})
    return lines, objs
