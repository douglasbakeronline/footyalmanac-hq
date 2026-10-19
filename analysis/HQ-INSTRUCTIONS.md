# HQ operating instructions: suggestions, banding, confidence, groupings

Written against the real graded record on 2026-10-05. Every number below is
measured, not estimated. Read `analysis-hypothesis.md` and
`analysis-groupings.md` for the workings.

---

## 1. Squad-size hypothesis: no signal, do not build on it

Across 10 two-way sports, players-per-side does not predict skill
(Spearman rho = −0.31 on accuracy-minus-base-rate, p = 0.39; rho = −0.09 on
log loss, p = 0.82). Raw accuracy appears to climb with roster size only
because base rates climb. **Stop using squad size as a grouping or
confidence input.**

---

## 2. Where confidence should actually come from

Ranked by measured value:

1. **Market disagreement.** The most trustworthy signal in the pipeline, and
   `predictability.py --market` already tests it. A pick the bookmaker has on
   the *other* side is the single most reliable downweight available.
2. **Draw exposure (football).** 391 of 944 draw reads were drawn out. Any
   football pick within 0.06 of the draw probability gets demoted one tier.
3. **Calibration tier.** Football tiers are sound and should be trusted:
   Strong 78.1% (expected 78.0%), Firm 71.0% (68.0%), Lean 64.8% (64.6%).
   **Do not re-fit these.** They are already calibrated.
4. **Price availability.** A leg with `est: true` is a guess. It should carry
   less weight, not the same weight.

### What NOT to do

A per-sport temperature looked promising (NHL's high band is off by 11.7
points) but **fails on held-out data: 1 of 9 sports improves, 8 are flat or
worse.** The existing gate in `sports.py` that rejects these calibrations is
correct and should stay. The high-band NHL error is real but a single
temperature cannot fix it without breaking the mid bands — it needs a
band-specific correction, which needs more settled data before it can be
fitted honestly.

---

## 3. The instruction for the odds/groupings tab

The current record: **9 won of 55 groups (16.4%) against a quoted 32.4%.**
Day-clustered bootstrap on the gap: **95% CI [−27.5%, −4.5%], p = 0.003.**
ROI −34.3% on 55 units staked.

The overconfidence is real and it is structural, not bad luck. 268 graded legs
hit 72.4% against a quoted 79.4% — 7 points of overconfidence per leg, which
compounds to ~12 points on a 5-fold.

### This is now enforced in code, not prose

`scripts/groupings_review.py` runs at 23:40 UK every night, after grading. It
measures quoted-vs-landed on every settled leg and group, bootstraps the gap
clustered by day, and writes `docs/data/groupings-review.json`.

`scripts/markets.py` reads that file and applies it:

- every published chance is reduced by the measured haircut (currently 7.2%);
- a group whose expected value at its real price falls below +5% is **not
  published at all**;
- the daily briefing names the haircut and anything held back.

The loop is closed: last night's grading sets this morning's probabilities, and
the review re-measures itself every night. If the model drifts, the haircut
moves with it. If it becomes calibrated, the haircut goes to zero and the
adjustment switches off by itself.

Guards, so this cannot misfire:
- under 20 settled groups it makes **no** claim and adjusts nothing;
- a gap inside the bootstrap CI is treated as noise and ignored;
- if the model turns out *under*confident the sign flips and probabilities are
  raised instead.

### What this does NOT do

It does not make the groups win. After the honest haircut the mean edge per leg
is **−0.026** — the desk has no edge against the price at all. The review's
standing advice, until that number turns positive, is **do not publish**. That
is the correct output and it is what the briefing now says.

Turning it into a profitable product needs a better model or better prices, not
a better filter. The review loop exists so that when either of those happens,
the desk notices within a day rather than a quarter.

### Why rule 3 is the important one

"Consistently picking groups that win" is not achievable at 5 legs. At the
observed 72.4% leg rate, a 5-fold wins **19.9%** of the time. Four days in five
lose. To win a 5-fold on 50% of days you need legs at ~87% each, which does not
exist at a price worth taking.

The realistic target is **positive expected value**, which means losing most
days while the price paid exceeds the true probability. On the current record
the EV gate would have published very few of those 55 groups — and that is the
point. Fewer, better-priced groups is the fix, not better guessing.

### If Douglas wants frequent winners specifically

That is a different product and it should be labelled as such:

| Goal | Config | Realistic hit rate |
|---|---|---|
| Win most days | 2-leg groups, 85%+ legs | 70–75% per day, thin margin |
| Positive long-run EV | 3–4 legs, 55–70% legs, priced | 35–45% per day |
| Lottery ticket | 5-leg, 70%+ legs | ~20% per day (current) |

Pick one and put it on the tab. Trying to have all three is how the current
−34% happened.

---

## 4. Coverage: the real reason suggestions feel thin

**79.6% of graded football games (4,456 of 5,601) fall in the "No read"
tier.** The model has no opinion on four fixtures in five. That is a bigger
constraint on the product than any confidence tweak.

The fix is coverage, not confidence: widen the rated team pool, and accept a
slightly worse log loss per fixture in exchange for having a view on more
fixtures. This is a model change, not a banding change — flagging it as the
prerequisite for everything in section 3 actually mattering at scale.

---

## 5. Honesty on the site

The Odds tab should state the record plainly, every day: groups won, groups
settled, and ROI. It currently presents estimated prices (`est: true`, 34.3%
of legs) alongside live ones without distinguishing them in the summary.

The credibility cost of an unstated −34% is larger than the cost of stating it.
