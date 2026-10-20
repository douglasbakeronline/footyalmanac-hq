# Footyalmanac HQ

The AI agent office for [footyalmanac](https://github.com/douglasbakeronline/footyalmanac)
(the Sports Almanac prediction site). A team of named agents runs the business's
daily rhythm: stand-ups, KPIs, a daily briefing with five-leg groups, Saturday
picks, slip tracking and a business playback, all shown in a 3D office.

- **Live office:** https://douglasbakeronline.github.io/footyalmanac-hq/
- **Prediction site and models:** [footyalmanac](https://github.com/douglasbakeronline/footyalmanac). Read its README first: it holds the project's objective, the current numbers and the improvement priorities.
- **Owner:** Douglas Baker. UK English, no em dashes, direct.

> **Picking this up as an AI?** HQ **reports on and plans for** the prediction
> site. It **never** makes predictions, changes probabilities or grades results:
> it ranks the gaps between quoted and landed into a backlog
> (`scripts/planner.py`, `docs/data/backlog.json`) that footyalmanac's agents work. Every
> number comes from footyalmanac's published files. To make the predictions
> better, work in footyalmanac. Work here to make the reporting clearer,
> cheaper or more useful. The code on `main` is the source of truth; where
> this file disagrees with it, trust the code.

---

## How it fits together

```
footyalmanac (site, every rebuild)
  data.json, record*.json, calibration, predictions, groupings.json, groupings.py
        |  read over HTTPS (public GitHub Pages and raw.githubusercontent.com)
        v
footyalmanac-hq  scripts/*.py  ->  docs/data/*.json  ->  docs/index.html (3D office)
        |                               \
        |                                -> GitHub issues: daily briefing, Saturday picks, slips
        v
.github/workflows/office.yml commits docs/data/ as footyalmanac-hq[bot]
```

- No secrets are needed for the normal path. `ODDS_API_KEY` is passed to the
  run but is only used in the fallback below.
- `main` isn't branch-protected here, and the bot commits to it many times a day.
  Pull before you push, and prefer a PR for anything beyond docs.

## The daily rhythm (`.github/workflows/office.yml`)

GitHub cron is UTC, so each UK slot is listed twice (BST and GMT).

| UK time | Run |
|---|---|
| 03:00 | Fixture sweep |
| 03:30 | Predictions ranked |
| 04:00 | Morning stand-up |
| 07:45 | Daily briefing issue (results, key games, groups) |
| 12:30 | Groups refresh (comment on the briefing) |
| 13:00 / 13:30 | Midday refresh, afternoon stand-up |
| 17:00 | Evening groups |
| 23:30 | Results and experiments |
| 23:45 | Daily playback (weekly on Sundays) |
| Fri 18:00 | Saturday picks preview (issue) |
| Sat 07:00 | Saturday picks final |
| Sun 07:30 | Saturday picks graded, issue closed |

Run any slot by hand: Actions, then Office rhythm, then Run workflow. The slots
are `standup`, `report`, `work`, `saturday`, `slip`, `briefing`, `refresh` and
`ceo`.

## Scripts

| File | What it does |
|---|---|
| `scripts/office.py` | Main entry (`--slot`). Reads the site's data and writes stand-ups, objectives, KPIs, playbacks and water-cooler chats to `docs/data/`. Agent names are in `NAMES`. |
| `scripts/markets.py` | Oscar and Jade: daily briefing and five-leg groups. |
| `scripts/slip.py` | Matches the owner's slips to published picks and settles them from graded records. |
| `scripts/saturday.py` | Saturday picks preview, final and review. |
| `scripts/planner.py` | The planner: ranks every quoted-versus-landed gap by z-score and writes `docs/data/backlog.json`, which footyalmanac's `agents/pick_task.py` reads each morning (four agents a day). Runs inside each scheduled stand-up. |
| `scripts/org.py` | Luke's hiring desk: adds a specialist when a KPI gap has no owner (at most one a day, six in total). State is in `docs/data/org.json`. |
| `scripts/performance_monitor.py` | Build-health and run-time KPIs. |
| `scripts/ceo.py` | Offline placeholder, kept for the tests. The real Elena is footyalmanac's `ceo.yml` (see "Elena, the CEO" below). |
| `docs/index.html` | The 3D office. The Picks tab answers questions like "Saturday picks" from published predictions, using no AI tokens. It only reads `docs/data/*.json`. |
| `cloudflare-worker/` | The old CEO chat backend (OpenAI). **Unused since 20 Oct 2026:** the CEO tab now briefs the real Elena on GitHub. It stays deployed on Cloudflare until Douglas removes it; nothing calls it. |
| `tests/` | `test_office.py`, `test_picks_all_sports.py` |

## Groups (Oscar and Jade)

- **Main path:** HQ downloads the site's `groupings.json` (the priced pool) and
  the site's own `groupings.py` from footyalmanac `main`. It then regroups
  only games still to start, using the site's rules. So any rule change on the
  site reaches HQ with no change here.
- **Current rules (since 19 Oct 2026):** a leg's chance is the lower of its
  tested rate and the bookmaker's fair chance. Only bookmaker-priced legs are
  used. Football prices come from API-Football, US sports from ESPN, and tennis
  and rugby from The Odds API. From 4 to 18 Oct, 8 of 48 groups won against
  15.9 expected; the fix is described in footyalmanac's `RELEASES.md`.
- **Fallback only:** if the site's groupings are missing or stale,
  `markets.py` prices the picks itself: football-data.co.uk for the bigger
  divisions, and The Odds API if `ODDS_API_KEY` is set here (capped at 8 calls
  a run). HQ has no `ODDS_API_KEY` secret today; it lives in footyalmanac,
  where it does the real work. Adding it here would share the same 500 free
  credits a month.
- **The Groups & Odds Desk (20 Oct 2026):** Jade leads, Oscar prices, Kofi
  (value) tests whether the model has any edge over bookmaker prices, and
  Hannah (leg selection) finds which legs land at or above their quote. All
  four are working agents in footyalmanac's sprint, and one of them works every
  day (`agents/pick_task.py` `DESK`). The planner gives them tasks by sport,
  price range and group band.
- **KPIs:** Oscar, legs with a live price. Jade, groups won minus expected.
  Kofi, legs landed minus quoted. Hannah, the average leg chance, which only
  counts if Kofi's stays honest. All from the site's graded groups since the
  honest-chance rule (19 Oct).
- Groups lose to the bookmakers' margin on average, and the briefing should
  never suggest otherwise.

## Team, KPIs and hiring

- **Core agents:** Luke (chief of staff), Ava (scout), Cory (quality), Raj
  (source), Ben (ratings), Mia (experiment), Theo (sports), Susie (auditor),
  Andrew (calibration), Nina (curator) and Allan (engineer). The Expansion Wing
  holds Priya (Championship) and the Groups & Odds Desk (Oscar, Jade, Kofi,
  Hannah); Omar (CFB) reports only.
- **Who does real work:** every agent above except Omar has a place in
  footyalmanac's daily sprint and opens pull requests there. Each day five run
  on the most urgent backlog tasks, plus one from the desk.

## Elena, the CEO

Ask her anything, or ask for a change, from the CEO tab: it opens a GitHub issue
labelled `ceo` on footyalmanac for you to submit. footyalmanac's `ceo.yml` runs
Claude as Elena on the whole repository. She answers on the issue, ships what is
clear and safe through the same `open_pr.sh` and merge gate as the agents, and
delegates bigger work as `office-backlog` issues the next sprint works first.
Follow-up comments continue the thread. Only Douglas's words reach her.
- **Team tab:** each agent's KPI today, its target, status, 14-day trend and
  days on track. Tap an agent for today's done, next and blockers, the last 7
  days, PRs and Agent of the Week days.
- **Hiring triggers (`org.py`):**
  - weakest league under 45% over 60+ games: league specialist
  - Strong calls drawn 15%+ of the time: draw-risk analyst
  - 80% or fewer recent builds green: reliability engineer
  - another sport with 50+ graded games: analyst
  - Daily List at 70%+ over 100+ picks: Growth Lead
- The office agents that **open PRs on footyalmanac** are defined in that
  repo's `agents/` (sprint tasks, merge gate). HQ's agents here only report.

## Your slip

Tell the agents what you've backed and they'll give their read and settle it as
results come in. You can ask in chat, open an issue labelled `my-slip` (one
selection per line), or run the `slip` slot. Each leg is matched to the
published pick and shown with its probability and the combined chance. Susie
settles legs from the graded records at each run and closes the issue when
everything is in.

## Run and test locally

```bash
python3 tests/test_office.py                     # tests
python3 scripts/office.py --slot standup         # a stand-up
python3 -m http.server -d docs 8080              # preview the office
```

More detail is in [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md).

## Where HQ can improve

1. **Report against the project's objective.** The site's README defines it:
   coverage of every daily fixture, a Daily List that lands at least 80%, and
   quotes that match what lands. Stand-ups and playbacks should lead with those
   three numbers and the quoted-versus-landed gap, not raw win counts.
2. **Elena's reach.** She can't change `.github/`, `agents/`, `CLAUDE.md` or
   `AGENTS.md` (nor can any agent); those still need Douglas.
3. **Briefing honesty.** Show each group's honest chance next to its odds,
   and say plainly that groups lose on average.
4. **KPIs that can't be gamed.** Done for the desk (20 Oct). Omar's KPI and
   the hiring desk's triggers still use raw hit rates.
5. **Stale numbers.** Every figure is copied from the site at run time. Never
   hard-code a rate or a bar here.

## Copyright

Copyright (c) 2026 Douglas Baker. All rights reserved. This repository is
proprietary: no licence is granted to copy, modify, distribute or use any part
of it without written permission. See [LICENSE](LICENSE).
