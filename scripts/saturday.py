"""Saturday picks workflow. No AI tokens: built from footyalmanac's published predictions and record.

preview  Friday 18:00 UK   first look at Saturday, posted as a GitHub issue
final    Saturday 07:00 UK after the morning build, posted as an update on the issue
review   Sunday 07:30 UK   Saturday graded, posted on the issue, which is then closed
"""
import json, os, subprocess
from datetime import datetime, timedelta, date

HQ = "douglasbakeronline/footyalmanac-hq"
SITE = "https://douglasbakeronline.github.io/footyalmanac-hq/"
MAJORS = [("en.1", "Premier League"), ("en.2", "Championship"), ("en.3", "League One"), ("en.4", "League Two"),
          ("sco.1", "Scottish Premiership"), ("es.1", "La Liga"), ("de.1", "Bundesliga"), ("it.1", "Serie A"),
          ("fr.1", "Ligue 1"), ("nl.1", "Eredivisie"), ("pt.1", "Primeira Liga")]

def pct(x): return "–" if x is None else f"{x*100:.0f}%"

def target(stage, now):
    d = now.date()
    if stage == "review":
        return d - timedelta(days=(d.weekday() - 5) % 7 or 7) if d.weekday() != 5 else d - timedelta(days=7)
    return d + timedelta(days=(5 - d.weekday()) % 7)

def stage_for(now):
    return {4: "preview", 5: "final", 6: "review"}.get(now.weekday(), "preview")

def ko(g):
    from zoneinfo import ZoneInfo
    try: return datetime.fromisoformat(g["ko"].replace("Z", "+00:00")).astimezone(ZoneInfo("Europe/London")).strftime("%H:%M")
    except Exception: return g.get("t") or ""

def slim(g):
    return {k: g.get(k) for k in ("t", "ko", "lg", "lgName", "h", "a", "side", "pick", "c", "p", "score", "btts", "o25", "hit", "hitN", "celtic", "list", "reserve")}

def build(stage, now, picks, rec, names):
    sat = target(stage, now).isoformat()
    out = {"id": int(now.timestamp() * 1000), "time": now.isoformat(), "date": sat, "stage": stage}
    if stage == "review":
        ld = next((x for x in rec.get("listDays") or [] if x.get("date") == sat), None)
        dd = next((x for x in rec.get("days") or [] if x.get("date") == sat), None)
        games = (ld or {}).get("games") or []
        graded = [g for g in games if g.get("ok") is not None]
        right = sum(1 for g in graded if g["ok"])
        sats = [x for x in rec.get("listDays") or [] if date.fromisoformat(x["date"]).weekday() == 5]
        allg = [g for x in sats for g in x.get("games") or [] if g.get("ok") is not None]
        out.update(graded=len(graded), right=right, dayAcc=(dd or {}).get("accuracy"), dayN=(dd or {}).get("n"),
                   games=[{"m": f"{g['home']} v {g['away']}", "c": g.get("confidence"), "ok": g.get("ok"),
                           "res": g.get("result")} for g in games],
                   saturdays=len(sats), satHit=(sum(g["ok"] for g in allg) / len(allg)) if allg else None, satN=len(allg))
        misses = [g for g in out["games"] if g["ok"] is False]
        out["lines"] = [
            {"agent": "auditor", "text": f"Saturday's Daily List went {right}/{len(graded)}" + (f" ({pct(right/len(graded))})." if graded else ". Nothing graded yet.") + (f" All football that day: {pct(out['dayAcc'])} over {out['dayN']} games." if dd else "")},
            {"agent": "calib", "text": (f"Misses: " + "; ".join(f"{m['m']} at {pct(m['c'])}" + (f", finished {m['res'][0]}-{m['res'][1]}" if m.get('res') else "") for m in misses[:4]) + ".") if misses else "No Daily List misses to review."},
            {"agent": "chief", "text": f"Saturdays so far: {pct(out['satHit'])} over {out['satN']} Daily List picks across {out['saturdays']} Saturdays." if allg else "First Saturday on the record."}]
        return out
    day = next((d for d in picks.get("days", []) if d["date"] == sat), None)
    if not day:
        out["missing"] = True
        out["lines"] = [{"agent": "curator", "text": f"Saturday {sat} isn't in the published week yet. I'll try again at the next run."}]
        return out
    G = day["games"]; bar = picks.get("bar") or 0.8
    lst = [g for g in G if g["list"]]; res = [g for g in G if g["reserve"]]
    strong = [g for g in G if g["c"] >= 0.7 and not g["list"] and not g["reserve"]][:10]
    majors = []
    for code, name in MAJORS:
        lg = [g for g in G if g["lg"] == code]
        if lg: majors.append({"code": code, "name": name, "n": len(lg), "games": [slim(g) for g in lg[:3]]})
    btts = sorted(G, key=lambda g: -(g.get("btts") or 0))[:5]
    over = sorted(G, key=lambda g: -(g.get("o25") or 0))[:5]
    drawy = [g for g in lst + res if (g.get("p") or {}).get("d", 0) >= 0.22]
    celtic = [g for g in lst + res if g["celtic"]]
    comps = len({g["lg"] for g in G})
    bands = rec.get("bands") or []
    weak_band = min(bands, key=lambda b: b["hit"] - b["expected"]) if bands else None
    sats = [x for x in rec.get("listDays") or [] if date.fromisoformat(x["date"]).weekday() == 5]
    allg = [g for x in sats for g in x.get("games") or [] if g.get("ok") is not None]
    out.update(count=len(G), comps=comps, bar=bar, generated=picks.get("generated"),
               list=[slim(g) for g in lst], reserve=[slim(g) for g in res], strong=[slim(g) for g in strong],
               majors=majors, btts=[slim(g) for g in btts], over=[slim(g) for g in over])
    top = lst[0] if lst else (G[0] if G else None)
    L = [
        {"agent": "scout", "text": f"{len(G)} games across {comps} competitions on Saturday. " + (f"Big leagues: " + ", ".join(f"{m['name']} {m['n']}" for m in majors) + "." if majors else "No big-league games: it's an international break.")},
        {"agent": "curator", "text": f"Daily List: {len(lst)} picks ({sum(1 for g in lst if g['c'] >= bar)} at {pct(bar)} or more), {len(res)} more in reserve." + (f" Strongest: {top['h']} v {top['a']}, {top['pick']} at {pct(top['c'])}." if top else "")},
        {"agent": "ratings", "text": f"{sum(1 for g in G if g['c'] >= 0.7)} calls at 70% or more." + (f" Next strongest off the list: " + "; ".join(f"{g['h']} v {g['a']} {pct(g['c'])}" for g in strong[:3]) + "." if strong else "")},
        {"agent": "calib", "text": (f"Watch the {pct(weak_band['from'])}-{pct(weak_band['to'])} band: it has won {pct(weak_band['hit'])} vs {pct(weak_band['expected'])} expected over {weak_band['n']} games." if weak_band and weak_band['hit'] < weak_band['expected'] - 0.03 else "Calibration is holding: no band is well below its expected hit rate.") + (f" Draw risk on {len(drawy)} list/reserve picks (draw 22%+)." if drawy else "")},
        {"agent": "quality", "text": (f"{len(celtic)} list/reserve picks carry a Celtic's Law flag: " + "; ".join(f"{g['h']} v {g['a']}" for g in celtic[:3]) + "." if celtic else "No Celtic's Law flags on the list or reserve.") + f" {sum(1 for g in G if g.get('unrated'))} unrated games."},
        {"agent": "auditor", "text": f"Saturdays so far: Daily List {pct(sum(g['ok'] for g in allg)/len(allg))} over {len(allg)} picks." if allg else "No Saturday on the record yet."},
        {"agent": "chief", "text": ("Final board after the morning build." if stage == "final" else "Preview: the final board lands at 07:00 Saturday after the morning build.") + " Model probabilities only, no bookmaker prices."},
    ]
    out["lines"] = L
    return out

def markdown(b, names):
    d = datetime.fromisoformat(b["date"]).strftime("%a %-d %b")
    h = [f"## Saturday picks · {d} · {b['stage']}", ""]
    for l in b.get("lines", []): h.append(f"- **{names.get(l['agent'], l['agent'])}**: {l['text']}")
    def table(rows, title, val="c", lab=None):
        if not rows: return
        h.extend(["", f"### {title}", "", "| UK | Match | Pick | Chance | Tested |", "|---|---|---|---|---|"])
        for g in rows:
            flag = " ⚑" if g.get("celtic") else ""
            h.append(f"| {ko(g)} | {g['h']} v {g['a']}{flag} | {lab or g['pick']} | {pct(g[val])} | {pct(g.get('hit')) if val == 'c' else ''} |")
    if b["stage"] == "review":
        h.extend(["", "| Match | Chance | Result |", "|---|---|---|"])
        for g in b.get("games", []):
            r = f"{g['res'][0]}-{g['res'][1]}" if g.get("res") else "–"
            h.append(f"| {g['m']} | {pct(g['c'])} | {r} {'won' if g['ok'] else 'lost' if g['ok'] is False else 'pending'} |")
    elif not b.get("missing"):
        table(b["list"], f"Daily List ({len(b['list'])})")
        table(b["reserve"][:15], f"Reserve ({len(b['reserve'])})")
        table(b["strong"], "Other strong calls")
        for m in b["majors"]: table(m["games"], f"{m['name']} ({m['n']} games, top 3)")
        table(b["btts"], "Both teams to score (a lean, weaker than the winner board)", "btts", "BTTS")
        table(b["over"], "Over 2.5 goals", "o25", "Over 2.5")
        h.extend(["", "⚑ = Celtic's Law flag. Tested = how often calls at this level won in testing."])
    h.extend(["", f"[Open the Picks desk]({SITE}) · not betting advice"])
    return "\n".join(h)

def gh(args):
    return subprocess.run(["gh"] + args, capture_output=True, text=True)

def post(b, names):
    if not os.environ.get("GH_TOKEN"): print("no GH_TOKEN, not posting"); return None
    title = f"Saturday picks · {datetime.fromisoformat(b['date']).strftime('%a %-d %b %Y')}"
    gh(["label", "create", "saturday-picks", "-R", HQ, "--color", "62d68f", "--force"])
    found = json.loads(gh(["issue", "list", "-R", HQ, "--label", "saturday-picks", "--state", "all", "--search", title,
                           "--json", "number,title,url,state"]).stdout or "[]")
    found = [i for i in found if i["title"] == title]
    body = markdown(b, names)
    if not found:
        r = gh(["issue", "create", "-R", HQ, "--title", title, "--label", "saturday-picks", "--body", body])
        url = r.stdout.strip().splitlines()[-1] if r.returncode == 0 else None
        print(r.stderr.strip() or f"issue {url}")
        return url
    i = found[0]
    if b["stage"] == "final": gh(["issue", "edit", str(i["number"]), "-R", HQ, "--body", body])
    gh(["issue", "comment", str(i["number"]), "-R", HQ, "--body", body])
    if b["stage"] == "review": gh(["issue", "close", str(i["number"]), "-R", HQ])
    return i["url"]
