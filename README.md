# Footyalmanac HQ

The AI agent office for [footyalmanac](https://github.com/douglasbakeronline/footyalmanac): eleven agents who run the prediction business's daily rhythm, hold stand-ups, chat at the water cooler and present a business playback.

## How it works
- `scripts/office.py` reads footyalmanac's public data (record, calibration, predictions, builds) and writes stand-ups, objectives, playbacks and chats to `docs/data/`.
- `.github/workflows/office.yml` runs it on the UK rhythm and commits the results:

| UK time | Run |
|---|---|
| 03:00 | Fixture sweep |
| 03:30 | Predictions ranked |
| 04:00 | Morning stand-up |
| 13:00 | Midday refresh |
| 13:30 | Afternoon stand-up |
| 23:30 | Results & experiments |
| 23:45 | Daily playback (weekly on Sundays) |
| Fri 18:00 | Saturday picks preview (GitHub issue) |
| Sat 07:00 | Saturday picks final, after the morning build |
| Sun 07:30 | Saturday picks graded, issue closed |

- `docs/index.html` is the 3D office. The Picks tab answers questions like "Saturday picks" or "Sunday Premier League" straight from footyalmanac's published predictions, so it uses no AI tokens. It only reads `docs/data/*.json`, so it can be hosted anywhere static.

## Run something now
Actions → Office rhythm → Run workflow → pick `standup`, `report` or `work`.

## Local preview
```
python -m http.server -d docs 8080
```

## Team, KPIs and hiring

- **Team tab:** every agent's KPI today (now vs target, status, 14-day trend, days on track). Tap an agent, in the tab or in the office, for their profile: today's done/next/blockers, the last 7 days of work, development PRs and Agent of the Week days.
- **Luke's hiring desk** (`scripts/org.py`, no AI tokens): at each stand-up the Chief of Staff checks for a gap nobody owns full-time and hires one specialist, at most one a day and six in total, each with one KPI and a stated reason:
  - weakest league under 45% over at least 60 games: league specialist
  - Strong calls drawn out 15% or more: draw risk analyst
  - 80% or fewer recent builds green: reliability engineer
  - another sport with 50 or more graded games: analyst, and a new Multi-sport department
  - Daily List at 70% or better over 100 or more picks: Growth Lead, and a new Growth & Support department

  Hires sit in the Expansion Wing, join stand-ups, playback and chats, and appear on the objectives wall. State is in `docs/data/org.json`. Delete an entry to let someone go.
- **Mobile:** the office fills the screen and turns side-on to fit a phone. Room tags and room buttons are compact, and "Team & reports" jumps to the panel.

## Your slip

Tell the agents what you've backed and they'll give their read, show it on the home screen and settle it as results come in. Three ways:
- Ask in chat.
- Open an issue labelled `my-slip` with one selection per line.
- Run the Office rhythm workflow with slot `slip` and your selections.

Each leg is matched to footyalmanac's published pick, with our probability, whether the model agrees and the combined chance. Susie settles legs from the graded records at each office run and closes the issue when everything is in.

## Markets & Groupings (Oscar and Jade)

Every morning at 07:45 UK you get a daily briefing as a GitHub issue (so it lands in your email): yesterday's results, today's most important games and why, tomorrow's, and three groups of five. Groups are refreshed at 12:30 and 17:00 from games still to start, as comments on the same issue. The home screen and Picks tab show the latest.

- Steady: combined odds 2.5 to 4. Balanced: 4 to 7. Stretch: 7 to 14.
- Each group is the five model picks with the best chance of all winning inside its odds band, no leg used twice, at most two very short legs, mixed sports where possible.
- Prices: UK bookmaker averages from football-data.co.uk for the bigger football divisions. Add a free key from the-odds-api.com as the repo secret `ODDS_API_KEY` to price tennis, rugby, NFL and more football. Anything without a price uses the model's fair price, marked with a star.
- Group legs are settled from footyalmanac's graded records; Oscar's KPI is the share of legs with a live price, Jade's is the share of group legs that win.
