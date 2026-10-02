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

- `docs/index.html` is the 3D office. It only reads `docs/data/*.json`, so it can be hosted anywhere static.

## Run something now
Actions → Office rhythm → Run workflow → pick `standup`, `report` or `work`.

## Local preview
```
python -m http.server -d docs 8080
```
