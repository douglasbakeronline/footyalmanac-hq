# The groupings problem, in numbers

**Question (Douglas):** make the Odds tab groupings win consistently, every day.

**Answer up front: consistency is not achievable, and the current system is
losing money. Both statements are backed by the project's own graded record
below. The honest goal is not "pick groups that win" — it is "quote the true
probability, and only publish a group when the price is on the right side of it".

## The record

`groupings-record.json`, 55 settled groups, 268 graded legs:

| Band | Groups | Won | Actual win% | Expected win% | Returned/Staked |
|---|---|---|---|---|---|
| Steady | 24 | 3 | 12.5% | 38.7% | 0.34 |
| Balanced | 16 | 5 | 31.2% | 31.0% | 1.30 |
| Stretch | 15 | 1 | 6.7% | 23.7% | 0.47 |
| **Total** | **55** | **9** | **16.4%** | **32.4%** | **0.66** |

Staked 55 units, returned 36.15. **ROI −34.3%.** The model expected 17.8 wins
and delivered 9.

## Why: one number

Mean quoted leg probability **79.4%**. Actual leg hit rate **72.4%**.
That is **7.0 points of overconfidence per leg.**

Every group is a 5-fold, so the error compounds five times:

| Legs | Model says | Reality | Gap |
|---|---|---|---|
| 2 | 63.0% | 52.4% | +10.6% |
| 3 | 50.0% | 37.9% | +12.1% |
| 5 | 31.5% | 19.9% | +11.6% |

A 5-fold the board calls 31% is really about 20%. At 20%, **4 days in 5 lose
by design.** No selection method fixes that; it is the arithmetic of five legs.

Put plainly: to have a 50/50 chance of seeing at least one winning group you
need to play ~3 days. To have a 50/50 chance in a *single* day you would need
legs at ~87% each — which barely exists in the priced market.

## The second problem: prices aren't prices

Of 268 graded legs, **92 (34.3%) carry an estimated price**, flagged `est: true`,
not a live bookmaker price. The Odds tab presents these alongside real prices.
Any ROI calculated on estimates is fiction — it is the model grading its own
homework.

## What can actually be fixed

1. **Kill the 7-point overconfidence.** Fit a per-band temperature on settled
   legs. This alone takes the quoted 31.5% 5-fold to ~20%, which is honest and
   makes the "Steady/Balanced/Stretch" labels mean what they say.

2. **Publish expected value, not win probability.** A 3-leg group at 3.9 with a
   true 27% is +EV and worth publishing even though it loses 73% of the time.
   A 5-leg group at 2.5 with a true 20% is −EV and should not be published at
   all, however attractive the price looks.

3. **Raise the price floor.** Refuse to build a group whose combined live price
   is below the inverse of its true probability. Right now nothing enforces this.

4. **Cap estimated-price exposure.** No group should contain more than one
   `est: true` leg, or the published ROI is unmeasurable.

5. **Report the record honestly.** The site should show "9 of 55 groups won,
   −34% ROI" rather than implying daily success. Every extra week of hiding it
   costs credibility that is harder to win back than accuracy is to fix.

## The instruction to give HQ

Stated as an operating rule HQ can implement and be held to:

> The Odds tab publishes three groups a day only when each group is
> positive expected value at its live combined price. Compute true probability
> by applying the per-band calibrated leg probabilities (not raw model output);
> publish only if `true_prob × decimal_odds > 1.05`. If no group clears the bar,
> publish nothing and say so. Never publish a group containing more than one
> estimated price. Report the rolling 30-day ROI on every briefing.

That last clause — "publish nothing and say so" — is the part that makes it a
real strategy instead of a gambling product. On the current record it would
have published very few groups, which is the correct outcome.
