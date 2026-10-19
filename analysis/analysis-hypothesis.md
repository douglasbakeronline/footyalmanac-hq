# Hypothesis test: does squad size predict predictability?

**Question (Douglas):** sports with more players per team should be easier to call,
because collective form is more reliable than individual form.

**Data:** `douglasbakeronline/footyalmanac` at commit on 2026-10-05.
Real held-out ("check") seasons, not training data. 758–5,814 fixtures per sport.

## Verdict: the hypothesis is not supported.

Spearman correlation across 10 two-way sports:

| Test | rho | p | Result |
|---|---|---|---|
| players vs accuracy-minus-base-rate | −0.309 | 0.39 | not significant |
| players vs log loss (lower=better) | −0.091 | 0.82 | no relationship |

Both point very slightly the *wrong* way, and both are indistinguishable from chance.
n=10 sports is small, so the honest statement is "no evidence for it", not "disproven".
But there is certainly no useful signal to build a strategy on.

## The table that matters

| Sport | Players | n | Accuracy | Base rate | Skill | LogLoss |
|---|---|---|---|---|---|---|
| Tennis | 1 | 758 | 61.2% | 50.0% | +11.2 | 0.6511 |
| NBA | 5 | 1,322 | 68.4% | 54.5% | +13.9 | 0.6004 |
| NCAA BB | 5 | 5,814 | 71.3% | 64.4% | +6.9 | 0.5523 |
| WNBA | 5 | 531 | 69.7% | 53.9% | +15.7 | 0.5995 |
| NHL | 6 | 1,429 | 54.9% | 56.6% | −1.6 | 0.6907 |
| MLB | 9 | 3,643 | 55.0% | 52.7% | +2.3 | 0.6855 |
| NFL | 11 | 332 | 64.3% | 54.7% | +9.5 | 0.6387 |
| College FB | 11 | 1,097 | 72.3% | 58.4% | +13.9 | 0.5423 |
| Rugby League | 13 | 298 | 63.4% | 55.2% | +8.2 | 0.6517 |
| Rugby Union | 15 | 733 | 70.5% | 68.9% | +1.6 | 0.5612 |

If roster size drove predictability, the right-hand column would climb steadily
from Tennis to Rugby Union. It doesn't: Tennis sits near the top, Rugby Union
near the bottom, and NHL/MLB sit at the floor with 6 and 9 players.

**The confound:** raw accuracy rises with roster size only because *base rates*
rise (bigger rosters → stronger home advantage / more lopsided matchups).
Once you subtract each sport's own base rate, the effect disappears.

## What actually separates a callable fixture

Not roster size. The real signals in this data:

1. **Calibration error, per sport.** NHL over-prices its picks by 5.8 points,
   MLB by 3.0, NFL by 2.6. CFB and Rugby Union *under*-price by 3.0 and 2.0.
   That's a correctable, sport-specific fix — re-fit the temperature per sport
   rather than globally. This is the single highest-value change available.

2. **Draw exposure in football.** 391 of 944 draw reads were drawn out. The
   Strong tier has 26 drawn-out calls from 228 (11.4%).

3. **Confidence tier, and it works.** Football tiers are well calibrated:
   Strong 78.1% hit vs 78.0% expected; Firm 71.0% vs 68.0%; Lean 64.8% vs 64.6%.

4. **But the tiers cover almost nothing.** 4,456 of 5,601 graded football games
   (79.6%) fall in "No read". The model has no opinion on four fixtures in five.
   That, not squad size, is why suggestions feel thin.

## Consequence for banding and confidence

Per-sport temperature is the lever. Because log loss is not comparable across
2-way and 3-way sports, the current single global calibration is wrong for at
least six of the nine sports. NHL and MLB are being quoted as if they were as
predictable as CFB.

**Recommended change:** fit and store a temperature `T` per sport in
`sports.json` (the file already has a `cal` field per sport, currently `null`
for most). Apply it before banding. Expected effect: reduces the 5.8-point NHL
overstatement to near zero, which improves every downstream band and group.
