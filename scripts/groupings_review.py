"""
Groupings review: the learning loop for the Odds tab.

Runs after every grading pass. Compares what the desk QUOTED with what actually
LANDED, and writes a verdict the stand-up reads out. It does not change the
model - it tells HQ, every day, whether the model is currently worth trusting
and by how much.

Why this exists (2026-10-19): the record showed 9 wins from 55 settled groups,
ROI -34%, against a quoted 32% win rate. Day-clustered bootstrap put the gap at
[-27.5%, -4.5%], p=0.003. That is not variance, it is a model error, and it is
the kind of thing that must be surfaced daily rather than discovered quarterly.

Reading the output
------------------
  gap      = actual hit rate minus quoted probability. Negative = overconfident.
  haircut  = the SHORTFALL. Subtract this from every published probability.
  ev_ratio = mean(calibrated_p * odds - 1). Below zero means the desk is
             pricing groups worse than the bookmaker is. No filter fixes that;
             the model has to change.

The bar for the desk to publish at all is ev_ratio > 0 over 30 settled days.
Below that the honest output is "no edge, do not publish", which is why the
verdict field exists rather than just a number.

Usage
    python3 scripts/groupings_review.py
    python3 scripts/groupings_review.py --json
"""
import json
import math
import os
import random
import sys
from collections import defaultdict

DATA = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs", "data")
OUT_NAME = "groupings-review.json"

# A gap is only called real if the day-clustered CI excludes zero AND the
# effect is bigger than this. Below 2 points is noise, not a finding.
MIN_REAL_GAP = 0.02
MIN_GROUPS = 20          # settled groups before any claim is made
BOOTSTRAP = 20000
SEED = 11


def load(name, default):
    try:
        with open(os.path.join(DATA, name)) as f:
            return json.load(f)
    except Exception:
        return default


def _by_day(groups):
    """Cluster by date: five legs on one day share fixtures, so they are not
    independent samples. Every CI in here resamples days, not legs."""
    out = defaultdict(list)
    for g in groups:
        for leg in g.get("legs") or []:
            d = (leg.get("when") or "")[:10]
            if d:
                out[d].append(leg)
    return [v for v in out.values() if v]


def bootstrap_gap(day_clusters, iters=BOOTSTRAP, seed=SEED):
    """95% CI and P(gap >= 0) for hit-rate minus quoted-probability."""
    if len(day_clusters) < 3:
        return None
    rng = random.Random(seed)
    out = []
    n = len(day_clusters)
    for _ in range(iters):
        flat = []
        for _ in range(n):
            flat.extend(day_clusters[rng.randrange(n)])
        if not flat:
            continue
        won = sum(1 for l in flat if l.get("status") == "won")
        quoted = sum(l.get("p") or 0 for l in flat) / len(flat)
        out.append(won / len(flat) - quoted)
    if not out:
        return None
    out.sort()
    return {
        "lo": round(out[int(0.025 * len(out))], 4),
        "hi": round(out[int(0.975 * len(out))], 4),
        "pNotReal": round(sum(1 for x in out if x >= 0) / len(out), 4),
    }


def review():
    record = load("groupings.json", {}) or load("groupings-record.json", {})
    days = record.get("days") or []

    groups = [g for d in days for g in (d.get("groups") or [])
              if g.get("status") in ("won", "lost")]
    legs = [l for g in groups for l in (g.get("legs") or [])
            if l.get("status") in ("won", "lost")]

    result = {
        "settledGroups": len(groups),
        "settledLegs": len(legs),
        "verdict": "insufficient data",
    }

    if not legs:
        _save(result)
        return result

    legWon = sum(1 for l in legs if l["status"] == "won")
    legQuoted = sum(l.get("p") or 0 for l in legs) / len(legs)
    legHit = legWon / len(legs)
    gap = legHit - legQuoted

    ci = bootstrap_gap(_by_day(groups))

    # calibrated probability and EV per leg.
    # gap is SIGNED: negative means the model quoted too high, so the honest
    # probability is p + gap (i.e. p - |gap|). Adding the signed gap is the
    # operation that lowers the number; p - gap would raise it.
    cal = [max((l.get("p") or 0) + gap, 0.01) for l in legs]
    evs = [c * (l.get("odds") or 0) - 1 for c, l in zip(cal, legs)]
    evRatio = sum(evs) / len(evs)
    posEv = sum(1 for e in evs if e > 0) / len(evs)

    grpWon = sum(1 for g in groups if g["status"] == "won")
    grpQuoted = sum(g.get("p") or 0 for g in groups) / len(groups)
    grpHit = grpWon / len(groups)

    result.update({
        "legs": {
            "n": len(legs), "hit": round(legHit, 4),
            "quoted": round(legQuoted, 4), "gap": round(gap, 4),
        },
        "groups": {
            "n": len(groups), "won": grpWon,
            "hit": round(grpHit, 4), "quoted": round(grpQuoted, 4),
            "gap": round(grpHit - grpQuoted, 4),
        },
        "haircut": round(-gap, 4),
        "confidence": ci,
        "ev": {
            "meanPerLeg": round(evRatio, 4),
            "sharePositive": round(posEv, 4),
        },
        "estimatedLegs": sum(1 for l in legs if l.get("est")),
    })

    # ---- the verdict: what HQ should actually do today ----
    if len(groups) < MIN_GROUPS:
        # Nothing here is trustworthy yet. Drop the measured fields so no
        # caller can accidentally apply a haircut derived from 3 groups.
        for k in ("haircut", "confidence", "ev", "legs", "groups", "byBand"):
            result.pop(k, None)
        result["verdict"] = "insufficient data"
        result["advice"] = (
            f"Only {len(groups)} settled groups. Need {MIN_GROUPS} before any "
            f"claim about calibration is trustworthy."
        )
    elif ci and ci["hi"] < 0 and abs(gap) >= MIN_REAL_GAP:
        result["verdict"] = "overconfident"
        result["advice"] = (
            f"Legs hit {legHit:.1%} against {legQuoted:.1%} quoted: overconfident "
            f"by {-gap:.1%} (95% CI {ci['lo']:+.1%} to {ci['hi']:+.1%}, "
            f"p={ci['pNotReal']:.3f}). Subtract {-gap:.1%} from every published "
            f"probability before banding. Mean EV per leg is {evRatio:+.3f}: "
            f"{'the desk has no edge and should not publish' if evRatio <= 0 else 'the desk still has an edge at current prices'}."
        )
    elif ci and ci["lo"] > 0 and abs(gap) >= MIN_REAL_GAP:
        result["verdict"] = "underconfident"
        result["advice"] = (
            f"Legs hit {legHit:.1%} against {legQuoted:.1%} quoted: the model is "
            f"UNDERselling itself by {gap:.1%}. Raise published probabilities, "
            f"and check the Stretch band first - it is probably too pessimistic."
        )
    else:
        result["verdict"] = "calibrated"
        result["advice"] = (
            f"Legs hit {legHit:.1%} against {legQuoted:.1%} quoted. Within noise. "
            f"Leave the calibration alone; changing it now would be fitting variance."
        )

    # ---- per-band, so a broken band is found without waiting for the total.
    # Only when the sample clears the bar; below it, no per-band claim either.
    if result["verdict"] != "insufficient data":
        bands = {}
        for g in groups:
            bands.setdefault(g.get("name"), []).append(g)
        result["byBand"] = {}
        for name, gs in bands.items():
            w = sum(1 for g in gs if g["status"] == "won")
            q = sum(g.get("p") or 0 for g in gs) / len(gs)
            result["byBand"][name] = {
                "n": len(gs), "won": w, "hit": round(w / len(gs), 4),
                "quoted": round(q, 4), "gap": round(w / len(gs) - q, 4),
            }

    _save(result)
    return result


def _out():
    """Resolved at call time, not import time, so tests that point DATA at a
    temp directory cannot write the real review file."""
    return os.path.join(DATA, OUT_NAME)


def _save(result):
    os.makedirs(DATA, exist_ok=True)
    path = _out()
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(result, f, indent=1)
    os.replace(tmp, path)


def main():
    r = review()
    if "--json" in sys.argv:
        print(json.dumps(r, indent=2))
        return
    print(f"Groupings review: {r['verdict'].upper()}")
    print()
    if r.get("groups"):
        g = r["groups"]
        print(f"  groups  {g['won']}/{g['n']} won = {g['hit']:.1%}  (quoted {g['quoted']:.1%}, gap {g['gap']:+.1%})")
    if r.get("legs"):
        l = r["legs"]
        print(f"  legs    {l['hit']:.1%} hit  (quoted {l['quoted']:.1%}, gap {l['gap']:+.1%})")
    if r.get("ev"):
        print(f"  edge    {r['ev']['meanPerLeg']:+.3f} per leg  ({r['ev']['sharePositive']:.0%} of legs +EV)")
    if r.get("confidence"):
        c = r["confidence"]
        print(f"  CI      [{c['lo']:+.1%}, {c['hi']:+.1%}]  p(not real)={c['pNotReal']:.3f}")
    print()
    print(f"  {r.get('advice', '')}")
    print()
    print(f"  written to {_out()}")


if __name__ == "__main__":
    main()
