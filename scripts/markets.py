"""Markets & Groupings desk: Douglas's daily briefing and three groups of five. No AI tokens.

Oscar (Odds Analyst) prices every candidate leg:
  1. football-data.co.uk fixtures.csv, free, UK bookmakers, the bigger European divisions
  2. The Odds API (only if the ODDS_API_KEY secret is set), UK bookmakers, tennis, rugby, NFL and more football
  3. otherwise the model's fair price (1 / probability), always labelled as an estimate

Jade (Accumulator Strategist) builds three groups of five from today's model picks that have not started:
  Steady    combined odds 2.5 to 4
  Balanced  combined odds 4 to 7
  Stretch   combined odds 7 to 14
Each group maximises the model's chance that all five win, inside its odds band, with no leg used twice,
at most two very short legs (under 1.20) and a mix of sports where the board allows it.

briefing  07:45 UK  yesterday, today (impactful games and why), tomorrow, groups. Posted as a GitHub issue.
refresh   12:30 and 17:00 UK  regroups from games still to start; posted as a comment on the day's issue.
grade     every office run  settles group legs from footyalmanac's graded records.
"""
import csv, io, itertools, json, math, os, re, sys, urllib.request
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import slip as S

UK = S.UK; HQ = S.HQ
DATA = S.DATA
GROUPS = os.path.join(DATA, "groups.json")
BRIEF = os.path.join(DATA, "briefing.json")
BANDS = [("Steady", 2.5, 4.0), ("Balanced", 4.0, 7.0), ("Stretch", 7.0, 14.0)]
MAJOR_FB = {"en.1", "en.2", "en.3", "en.4", "sco.1", "es.1", "de.1", "it.1", "fr.1", "nl.1", "pt.1", "be.1", "tr.1"}
BIG_COMP = ("Nations League", "World Cup", "Champions League", "Europa League", "Conference League", "Euro", "Copa")
UA = {"User-Agent": "Mozilla/5.0 (footyalmanac-hq markets desk)"}
pct = S.pct

def fetch(url, timeout=60):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), dict(r.headers)

def load(path, default):
    try: return json.load(open(path))
    except Exception: return default

# ---------- the board ----------
def legs_for(dates):
    """Model picks (the side the model favours) for the given UK dates, with context for the 'why'."""
    out = []
    try: site = json.loads(fetch(S.SITE)[0])
    except Exception: site = {}
    for day in site.get("days") or []:
        if day["date"] not in dates: continue
        for g in day.get("games", []):
            p = g.get("p") or {}
            if not p or g.get("unrated"): continue
            side = max(p, key=p.get)
            if side == "d": continue
            h, a = g["home"], g["away"]; team = (h if side == "h" else a)["name"]; opp = (a if side == "h" else h)["name"]
            acc = g.get("accuracy") or {}
            out.append({"sport": "football", "event": f"{h['name']} v {a['name']}", "comp": g.get("leagueName"), "lg": g.get("league"),
                        "country": g.get("country"), "tier": g.get("tier"), "when": g.get("kickoff"), "date": day["date"],
                        "selection": team, "opp": opp, "side": side, "home": h["name"], "away": a["name"], "p": p[side],
                        "modelPick": team, "list": bool(g.get("list")), "reserve": bool(g.get("reserve")),
                        "hit": acc.get("hit"), "hitN": acc.get("n"), "score": g.get("score"), "xg": g.get("xg"),
                        "rankH": h.get("worldRank"), "rankA": a.get("worldRank"), "status": "pending"})
    for g in S.latest("predictions-sports") or []:
        t = S.uk(g.get("when") or "")
        if not t or t.date().isoformat() not in dates: continue
        team = g.get("pick"); home = team == g["home"]
        acc = g.get("accuracy") or {}
        out.append({"sport": g["sport"], "event": f"{g['home']} v {g['away']}", "comp": g.get("label"), "when": g.get("when"),
                    "date": t.date().isoformat(), "selection": team, "opp": g["away"] if home else g["home"],
                    "p": g.get("confidence"), "modelPick": team, "tierName": g.get("tier"), "list": bool(g.get("list")),
                    "hit": acc.get("hit"), "hitN": acc.get("n"), "id": g.get("id"),
                    "elo": [g.get("eloH"), g.get("eloA")] if home else [g.get("eloA"), g.get("eloH")], "homeSide": home,
                    "form": "".join(x.get("r", "") for x in (g.get("formH") if home else g.get("formA")) or [])[:5], "status": "pending"})
    for g in S.latest("predictions-tennis") or []:
        if g.get("date") not in dates and not g.get("time"): continue
        when = f"{g['date']}T{g['time']}:00Z" if g.get("time") else None
        t = S.uk(when) if when else None
        d = t.date().isoformat() if t else g.get("date")
        if d not in dates: continue
        a_pick = g.get("pick") == g["playerA"]
        acc = g.get("accuracy") or {}
        out.append({"sport": "tennis", "event": f"{g['playerA']} v {g['playerB']}", "comp": f"{g.get('tournament')} {g.get('round') or ''}".strip(),
                    "tour": g.get("tour"), "when": when, "date": d, "selection": g.get("pick"), "opp": g["playerB"] if a_pick else g["playerA"],
                    "p": g.get("confidence"), "modelPick": g.get("pick"), "tierName": g.get("tier"), "list": bool(g.get("list")),
                    "hit": acc.get("hit"), "hitN": acc.get("n"), "id": g.get("id"),
                    "rank": [g.get("rankA"), g.get("rankB")] if a_pick else [g.get("rankB"), g.get("rankA")], "status": "pending"})
    return out

# ---------- Oscar: prices ----------
def nm(s): return re.sub(r"\b(fc|afc|cf|sc|ac|club|united|utd|city|town|the)\b", "", S.norm(s)).replace("  ", " ").strip()
def close(a, b): a, b = nm(a), nm(b); return a == b or (a and b and (a in b or b in a)) or SequenceMatcher(None, a, b).ratio() >= 0.78

def price_football_data(legs):
    try: txt = fetch("https://www.football-data.co.uk/fixtures.csv")[0].decode("utf-8-sig", "ignore")
    except Exception as e: print("football-data:", e); return 0
    rows = list(csv.DictReader(io.StringIO(txt))); n = 0
    for l in legs:
        if l["sport"] != "football" or l.get("odds"): continue
        dd = "/".join(reversed(l["date"].split("-")))
        for r in rows:
            if r.get("Date") != dd or not close(r.get("HomeTeam", ""), l["home"]) or not close(r.get("AwayTeam", ""), l["away"]): continue
            k = "H" if l["side"] == "h" else "A"
            try: avg = float(r.get(f"Avg{k}") or 0); best = float(r.get(f"Max{k}") or 0); b365 = float(r.get(f"B365{k}") or 0)
            except ValueError: continue
            if avg > 1:
                l.update(odds=round(avg, 2), best=round(best, 2) if best > 1 else None, b365=round(b365, 2) if b365 > 1 else None,
                         oddsSrc="UK bookmaker average (football-data.co.uk)"); n += 1
            break
    return n

ODDS_KEYS = {"tennis": ("tennis_atp", "tennis_wta"), "rugby": ("rugbyunion",), "nfl": ("americanfootball_nfl",), "mlb": ("baseball_mlb",)}
FB_KEYS = {"Premier League|England": "soccer_epl", "Championship|England": "soccer_efl_champ", "League One|England": "soccer_england_league1",
           "League Two|England": "soccer_england_league2", "Premiership|Scotland": "soccer_spl", "Nations League": "soccer_uefa_nations_league",
           "La Liga": "soccer_spain_la_liga", "Bundesliga|Germany": "soccer_germany_bundesliga", "Serie A|Italy": "soccer_italy_serie_a",
           "Ligue 1": "soccer_france_ligue_one", "Champions League": "soccer_uefa_champs_league", "Europa League": "soccer_uefa_europa_league"}

def price_odds_api(legs, budget=8):
    key = os.environ.get("ODDS_API_KEY")
    if not key: return 0, None
    base = "https://api.the-odds-api.com/v4/sports"
    try: sports = json.loads(fetch(f"{base}?apiKey={key}")[0])
    except Exception as e: print("odds api:", e); return 0, None
    active = [s["key"] for s in sports if s.get("active")]
    want = []
    for l in legs:
        if l.get("odds"): continue
        if l["sport"] == "football":
            for pat, k in FB_KEYS.items():
                parts = pat.split("|")
                if parts[0] in (l.get("comp") or "") and (len(parts) == 1 or parts[1] == l.get("country")) and k in active and k not in want: want.append(k)
        else:
            for pre in ODDS_KEYS.get(l["sport"], ()):
                want += [k for k in active if k.startswith(pre) and k not in want]
    n, left = 0, None
    for k in want[:budget]:
        try:
            body, hdr = fetch(f"{base}/{k}/odds?apiKey={key}&regions=uk&markets=h2h&oddsFormat=decimal")
            left = hdr.get("x-requests-remaining") or hdr.get("X-Requests-Remaining")
            events = json.loads(body)
        except Exception as e: print("odds api", k, e); continue
        for ev in events:
            for l in legs:
                if l.get("odds"): continue
                names = [l["selection"], l["opp"]]
                if not (any(close(ev.get("home_team", ""), x) for x in names) and any(close(ev.get("away_team", ""), x) for x in names)): continue
                prices = [o["price"] for b in ev.get("bookmakers", []) for m in b.get("markets", []) if m.get("key") == "h2h"
                          for o in m.get("outcomes", []) if close(o.get("name", ""), l["selection"])]
                if prices:
                    l.update(odds=round(sum(prices) / len(prices), 2), best=round(max(prices), 2), oddsSrc=f"UK bookmaker average ({len(prices)} books, The Odds API)"); n += 1
        if left and left.isdigit() and int(left) < 20: break
    return n, left

def price(legs):
    a = price_football_data(legs); b, left = price_odds_api(legs)
    for l in legs:
        if not l.get("odds") and l.get("p"):
            l.update(odds=round(1 / l["p"], 2), oddsSrc="estimate: model fair price, no market price yet", est=True)
        l["implied"] = round(1 / l["odds"], 4) if l.get("odds") else None
    priced = sum(1 for l in legs if not l.get("est"))
    return {"footballData": a, "oddsApi": b, "oddsApiLeft": left, "priced": priced, "total": len(legs)}

# ---------- Jade: groups ----------
def pool(legs, now, used=()):
    soon = now + timedelta(minutes=15)
    c = [l for l in legs if l.get("p") and l["p"] >= 0.55 and l.get("odds") and 1.05 <= l["odds"] <= 2.6
         and (S.uk(l["when"]) if l.get("when") else now + timedelta(hours=1)) > soon
         and (l.get("hit") is None or l["hit"] >= 0.6) and key(l) not in used and bettable(l)]
    c.sort(key=lambda l: -l["p"])
    # keep a spread of prices so the bands can be met
    short = [l for l in c if l["odds"] < 1.3][:14]; mid = [l for l in c if 1.3 <= l["odds"] < 1.7][:14]; long_ = [l for l in c if l["odds"] >= 1.7][:10]
    return short + mid + long_

def bettable(l):
    """Legs Douglas can realistically find at a UK bookmaker: anything with a real price, the Daily List and reserves,
    other sports and tennis, and football in the bigger competitions."""
    if not l.get("est") or l["sport"] != "football": return True
    comp = l.get("comp") or ""
    return l.get("lg") in MAJOR_FB or any(k in comp for k in BIG_COMP) or "friendly" in comp.lower() or (l.get("tier") == 1 and l.get("country") in TOP_COUNTRIES)

TOP_COUNTRIES = {"England", "Scotland", "Spain", "Germany", "Italy", "France", "Netherlands", "Portugal", "Belgium", "Turkey", "Greece",
                 "Austria", "Switzerland", "Denmark", "Norway", "Sweden", "USA", "Brazil", "Argentina", "Mexico", "Japan", "Australia"}

def key(l): return f"{l['sport']}|{l['event']}"

def build_groups(legs, now):
    used, groups = set(), []
    for name, lo, hi in BANDS:
        c = [l for l in pool(legs, now, used)]
        best = None
        for combo in itertools.combinations(c, 5):
            o = math.prod(l["odds"] for l in combo)
            if not (lo <= o <= hi): continue
            if sum(l["odds"] < 1.2 for l in combo) > 2: continue
            if len({l["event"] for l in combo}) < 5: continue
            p = math.prod(l["p"] for l in combo)
            sports = len({l["sport"] for l in combo}); comps = max(sum(1 for x in combo if x.get("comp") == l.get("comp")) for l in combo)
            score = p * (1 + 0.04 * (sports - 1)) * (0.97 if comps > 2 else 1)
            if not best or score > best[0]: best = (score, combo, o, p)
        if not best: continue
        _, combo, o, p = best
        legs5 = sorted([dict(l) for l in combo], key=lambda l: l.get("when") or "9")
        mkt = math.prod(l["implied"] for l in legs5 if l.get("implied"))
        groups.append({"name": name, "band": [lo, hi], "odds": round(o, 2), "p": round(p, 4), "marketP": round(mkt, 4),
                       "estimated": sum(1 for l in legs5 if l.get("est")), "legs": legs5, "status": "pending"})
        used |= {key(l) for l in combo}
    return groups

# ---------- briefing ----------
def impact(l):
    s = (l.get("p") or 0) * 2 + (1 if l.get("list") else 0)
    if l["sport"] == "football":
        comp = l.get("comp") or ""
        s += 3 if (l.get("lg") in MAJOR_FB or any(k in comp for k in BIG_COMP)) else 1.2 if l.get("tier") == 1 else 0.3
    elif l["sport"] == "tennis":
        r = [x for x in (l.get("rank") or []) if x]
        s += 2 + (1.5 if r and min(r) <= 10 else 0.75 if r and min(r) <= 30 else 0)
    else:
        s += {"nfl": 2.5, "rugby": 2.2, "mlb": 1.8}.get(l["sport"], 1.5)
    return s

def why(l):
    bits = [f"{pct(l['p'])} {l['selection']}"]
    if l["sport"] == "football":
        if l.get("score"): bits.append(f"likely {l['score'][0]}-{l['score'][1]}")
        if l.get("xg"): bits.append(f"xG {l['xg'][0]:.1f} v {l['xg'][1]:.1f}")
        if l.get("rankH") and l.get("rankA"): bits.append(f"world ranks {l['rankH']} v {l['rankA']}")
    elif l["sport"] == "tennis":
        r = l.get("rank") or []
        if r and r[0] and r[1]: bits.append(f"ranked {r[0]} v {r[1]}")
    else:
        e = l.get("elo") or []
        if len(e) == 2 and e[0] and e[1]: bits.append(f"rating {e[0]} v {e[1]}")
        if l.get("form"): bits.append(f"form {l['form']}")
        bits.append("at home" if l.get("homeSide") else "away")
    if l.get("hit") is not None: bits.append(f"calls at this level won {pct(l['hit'])} ({l.get('hitN')})")
    if not l.get("est") and l.get("odds"): bits.append(f"market {l['odds']:.2f} ({pct(l['implied'])})")
    return ", ".join(bits)

def yesterday(dt):
    y = (dt - timedelta(days=1)).isoformat()
    rec, srec, trec = S.raw("record.json") or {}, S.raw("sports-record.json") or {}, S.raw("tennis-record.json") or {}
    f = next((d for d in rec.get("days") or [] if d.get("date") == y), None)
    ld = next((d for d in rec.get("listDays") or [] if d.get("date") == y), None)
    t = next((d for d in trec.get("days") or [] if d.get("date") == y), None)
    s = next((d for d in srec.get("days") or [] if d.get("date") == y), None)
    out = {"date": y}
    if f: out["football"] = {"n": f["n"], "correct": f["correct"], "acc": f["accuracy"]}
    if ld:
        g = ld.get("games") or []; out["list"] = {"n": len(g), "won": sum(1 for x in g if x.get("ok")),
                                                  "misses": [f"{x['home']} v {x['away']} {x['result'][0]}-{x['result'][1]}" for x in g if x.get("ok") is False][:4]}
    if t: out["tennis"] = {"n": t["n"], "correct": t["correct"], "acc": t["accuracy"]}
    if s: out["sports"] = {"n": s["n"], "correct": s["correct"], "acc": s["accuracy"]}
    gs = [x for x in load(GROUPS, []) if x.get("date") == y]
    if gs:
        allg = [g for x in gs for g in x["groups"]]
        out["groups"] = {"n": len(allg), "landed": sum(1 for g in allg if g["status"] == "won"),
                         "legs": sum(len(g["legs"]) for g in allg), "legsWon": sum(1 for g in allg for l in g["legs"] if l.get("status") == "won")}
    return out

def fmt_when(l):
    t = S.uk(l["when"]) if l.get("when") else None
    return t.strftime("%H:%M") if t else "tbc"

def group_md(g):
    lines = [f"**{g['name']}** · combined odds {g['odds']:.2f} · all five land on tested rates {pct(g['p'])}"
             + (f" · bookmakers imply {pct(g['marketP'])}" if g["estimated"] == 0 else (f" · {g['estimated']} of 5 prices are estimates" if g['estimated'] != 1 else " · 1 of 5 prices is an estimate")),
             "", "| UK | Selection | Event | Odds | Tested chance |", "|---|---|---|---|---|"]
    for l in g["legs"]:
        lines.append(f"| {fmt_when(l)} | {l['selection']} | {l['event']} ({l.get('comp') or l['sport']}) | {l['odds']:.2f}{' est.' if l.get('est') else ''} | {pct(l['p'])} |")
    return "\n".join(lines)

def compose(stage, now, b):
    y = b["yesterday"]; L = [f"Good {'morning' if now.hour < 12 else 'afternoon' if now.hour < 18 else 'evening'} Douglas. {now.strftime('%A %d %B')}, {now.strftime('%H:%M')} UK.", ""]
    if stage == "briefing":
        L += ["### Yesterday"]
        yl = []
        if y.get("list"): yl.append(f"Daily List {y['list']['won']}/{y['list']['n']}" + (f" (misses: {', '.join(y['list']['misses'])})" if y['list']['misses'] else ""))
        if y.get("football"): yl.append(f"football overall {pct(y['football']['acc'])} of {y['football']['n']}")
        if y.get("tennis"): yl.append(f"tennis {y['tennis']['correct']}/{y['tennis']['n']}")
        if y.get("sports"): yl.append(f"other sports {y['sports']['correct']}/{y['sports']['n']}")
        if y.get("groups"): yl.append(f"groups landed {y['groups']['landed']}/{y['groups']['n']}, legs won {y['groups']['legsWon']}/{y['groups']['legs']}")
        L += ["**Susie (Auditor):** " + ("; ".join(yl) + "." if yl else "No graded results for yesterday yet."), ""]
        L += ["### Today: what matters and why"]
        L += [f"- **{l['event']}** ({l.get('comp') or l['sport']}, {fmt_when(l)}): {why(l)}" for l in b["impactful"]]
        L += ["", f"**Nina (Daily Board):** {b['counts']['today']} games rated by the model today, {b['counts']['list']} on the Daily List.", ""]
        if b.get("tomorrow"):
            L += ["### Tomorrow", *[f"- **{l['event']}** ({l.get('comp') or l['sport']}, {fmt_when(l)}): {why(l)}" for l in b["tomorrow"]], ""]
    L += [f"### {'Three groups of five' if stage == 'briefing' else 'Updated groups from games still to start'}"]
    pr = b["pricing"]
    gl = [l for g in b["groups"] for l in g["legs"]]
    L += [f"**Oscar (Odds Analyst):** {sum(1 for l in gl if not l.get('est'))} of the {len(gl)} legs below have a live bookmaker price ({pr['priced']} of today's {pr['total']} picks priced in all)"
          + ("; prices from the Sports Almanac's Odds tab: API-Football for football, ESPN for NFL and baseball, tennis and rugby on the model's fair price" if pr.get("site") else ("" if os.environ.get("ODDS_API_KEY") else "; tennis, rugby and smaller leagues use the model's fair price until an odds API key is added")) + ".", ""]
    if b["groups"]:
        L += ["**Jade (Accumulator Strategist):** Five tested picks per group, each with a short, a middle and (Balanced and Stretch) a longer price, no leg used twice. Chances are the tested hit rates at each pick's level. Steady lands most often; Stretch pays more. All groups are also on the [Odds tab](https://douglasbakeronline.github.io/footyalmanac/).", ""]
        for g in [g for g in b["groups"] if "alternative" not in g["name"]] or b["groups"]: L += [group_md(g), ""]
    else:
        L += ["**Jade (Accumulator Strategist):** Not enough strong picks left to start today to build a group inside the bands.", ""]
    L += ["Model probabilities are footyalmanac's own; our backtest says bookmakers still price football slightly better than the model, so treat these as informed suggestions, not value bets. Accumulators multiply the bookmaker margin. Not betting advice."]
    return "\n".join(L)

FA_GROUPINGS = "https://douglasbakeronline.github.io/footyalmanac/groupings.json"
FA_RULES = "https://raw.githubusercontent.com/douglasbakeronline/footyalmanac/main/groupings.py"

def site_groups(today, now):
    """Groups from the Sports Almanac's Odds tab rules and its priced pool (API-Football and ESPN prices),
    regrouped from games still to start. None if the site's groupings are missing or stale."""
    try:
        data = json.loads(fetch(FA_GROUPINGS + f"?t={int(now.timestamp())}")[0])
        pool = (data.get("pool") or {}).get(today)
        if not pool: return None
        import types
        G = types.ModuleType("fa_groupings"); G.__file__ = "fa_groupings.py"; exec(fetch(FA_RULES)[0].decode(), G.__dict__)
        groups = G.build_day(pool, now.astimezone(timezone.utc) + timedelta(minutes=20))
    except Exception as e:
        print("site groupings unavailable:", e); return None
    out = []
    for g in groups:
        legs5 = [dict(l, selection=l["pick"], modelPick=l["pick"], status="pending") for l in g["legs"]]
        out.append({"name": g["name"] + (" (alternative)" if g.get("rank") == "alternative" else ""), "band": g["band"], "odds": g["odds"],
                    "p": g["p"], "marketP": g["implied"], "estimated": g["estimates"], "legs": legs5, "status": "pending"})
    priced = sum(1 for l in pool if not l.get("est"))
    return out, {"priced": priced, "total": len(pool), "site": True, "generated": data.get("generated")}

def run(stage):
    now = datetime.now(UK); today = now.date().isoformat(); tom = (now.date() + timedelta(days=1)).isoformat()
    legs = legs_for({today, tom})
    t_legs = [l for l in legs if l["date"] == today]; m_legs = [l for l in legs if l["date"] == tom]
    sg = site_groups(today, now)
    if sg:
        groups, pricing = sg
    else:
        pricing = price(t_legs)
        groups = build_groups(t_legs, now)
    upcoming = [l for l in t_legs if (S.uk(l["when"]) if l.get("when") else now) > now]
    b = {"time": now.isoformat(), "date": today, "stage": stage, "pricing": pricing,
         "counts": {"today": len(t_legs), "list": sum(1 for l in t_legs if l.get("list")), "tomorrow": len(m_legs)},
         "impactful": sorted([l for l in upcoming if l["p"] >= 0.6],  key=lambda l: -impact(l))[:6], "tomorrow": sorted([l for l in m_legs if l["p"] >= 0.6], key=lambda l: -impact(l))[:5],
         "groups": groups, "yesterday": yesterday(now.date()) if stage == "briefing" else (load(BRIEF, {}).get("yesterday") or {})}
    for l in b["impactful"] + b["tomorrow"]: l["why"] = why(l)
    text = compose(stage, now, b)
    S.gh(["label", "create", "briefing", "-R", HQ, "--color", "f0b35a", "--description", "Daily briefing and groups of five", "--force"])
    day = load(BRIEF, {})
    issue = day.get("issue") if day.get("date") == today else None
    if stage == "briefing" or not issue:
        url = S.gh(["issue", "create", "-R", HQ, "--title", f"Daily briefing, {now.strftime('%a %d %b')}", "--label", "briefing", "--body", text])
        issue = int(url.rstrip("/").split("/")[-1]) if url else None; b["url"] = url
        prev = day.get("issue")
        if prev and prev != issue: S.gh(["issue", "close", str(prev), "-R", HQ])
    else:
        S.gh(["issue", "comment", str(issue), "-R", HQ, "--body", text]); b["url"] = day.get("url")
    b["issue"] = issue; b["text"] = text
    hist = load(GROUPS, [])
    hist.insert(0, {"id": int(now.timestamp() * 1000), "date": today, "time": now.isoformat(), "stage": stage, "groups": groups})
    json.dump(hist[:120], open(GROUPS, "w"), indent=1, ensure_ascii=False)
    json.dump(b, open(BRIEF, "w"), indent=1, ensure_ascii=False)
    print(text); return b

def grade():
    hist = load(GROUPS, []); changed = False
    for run_ in hist[:30]:
        for g in run_["groups"]:
            if g["status"] != "pending": continue
            if S.settle(g["legs"]): changed = True
            st = [l.get("status") for l in g["legs"]]
            if "lost" in st: g["status"] = "lost"
            elif all(s in ("won", "void") for s in st): g["status"] = "won"
    if changed: json.dump(hist, open(GROUPS, "w"), indent=1, ensure_ascii=False)

def kpis():
    """For the Markets desk hires: share of legs with a real price today, leg hit rate in groups over 30 days."""
    b = load(BRIEF, {}); pr = b.get("pricing") or {}
    share = pr["priced"] / pr["total"] if pr.get("total") else None
    since = (datetime.now(UK).date() - timedelta(days=30)).isoformat()
    legs = [l for r in load(GROUPS, []) if r["date"] >= since for g in r["groups"] for l in g["legs"] if l.get("status") in ("won", "lost")]
    seen = {}
    for l in legs: seen[key(l)] = l["status"]
    hit = sum(1 for v in seen.values() if v == "won") / len(seen) if seen else None
    return share, hit, len(seen)

if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "briefing"
    if cmd == "grade": grade()
    else: run(cmd)
