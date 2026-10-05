# Footyalmanac CEO Chat - Cloudflare Worker

This Worker powers the "CEO" tab on the live site (docs/index.html). It receives
chat messages from the browser, pulls live business context from the public
`docs/data/*.json` files, and calls OpenAI to respond in character as Elena.

## Deployment

Deployed manually via Cloudflare API (not wrangler CLI, to avoid requiring
local Node setup). To redeploy after editing `worker.js`:

```bash
# Requires a Cloudflare API token with Workers Scripts: Edit permission
export CF_TOKEN="your-token-here"
export CF_ACCOUNT_ID="ea1ca6242dbf5a33997d448ddb28c7df"

curl -X PUT \
  "https://api.cloudflare.com/client/v4/accounts/${CF_ACCOUNT_ID}/workers/scripts/footyalmanac-ceo" \
  -H "Authorization: Bearer ${CF_TOKEN}" \
  -F "metadata={\"main_module\":\"worker.js\",\"compatibility_date\":\"2024-01-01\"};type=application/json" \
  -F "worker.js=@worker.js;type=application/javascript+module"
```

## Secrets

The Worker needs `OPENAI_API_KEY` set as a secret (not in code):

```bash
curl -X PUT \
  "https://api.cloudflare.com/client/v4/accounts/${CF_ACCOUNT_ID}/workers/scripts/footyalmanac-ceo/secrets" \
  -H "Authorization: Bearer ${CF_TOKEN}" \
  -H "Content-Type: application/json" \
  -d '{"name":"OPENAI_API_KEY","text":"sk-...","type":"secret_text"}'
```

Secrets persist across redeploys of the script itself - you only need to set
this once unless rotating the key.

## Live URL

`https://footyalmanac-ceo.douglasbakeronline.workers.dev`

Called from `docs/index.html` (search for `CEO_API` constant).

## Important design notes

- **Elena does NOT have access to AI/LLM spend data.** There is no system
  anywhere that tracks OpenAI/Anthropic token costs. The prompt explicitly
  instructs her to refuse and redirect to the real billing dashboards rather
  than guess - a hallucination that happened in testing and was fixed in the
  prompt's "HARD RULES" section. Do not remove that guard without building
  real spend tracking first (would require an OpenAI *Admin* key, which is
  different from and more sensitive than a regular project API key).
- **Today's picks come from `picks.json`** via `todaysTopPicks()` - filters
  for `list:true` or confidence >= 60%, sorted by confidence, top 5.
- CORS is locked to `https://douglasbakeronline.github.io` only.
