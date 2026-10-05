/**
 * Footyalmanac HQ - CEO Chat Worker
 * Receives chat messages from the site, pulls live business context from
 * docs/data/*.json (public GitHub Pages data), and calls OpenAI to respond
 * in character as Elena, the CEO.
 */

const SITE_DATA = "https://douglasbakeronline.github.io/footyalmanac-hq/data";
const ALLOWED_ORIGIN = "https://douglasbakeronline.github.io";

async function fetchJSON(path, fallback = null) {
  try {
    const res = await fetch(`${SITE_DATA}/${path}?t=${Date.now()}`);
    if (!res.ok) return fallback;
    return await res.json();
  } catch (e) {
    return fallback;
  }
}

function corsHeaders(origin) {
  const allow = origin === ALLOWED_ORIGIN ? origin : ALLOWED_ORIGIN;
  return {
    "Access-Control-Allow-Origin": allow,
    "Access-Control-Allow-Methods": "POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
  };
}

function todaysTopPicks(picks, limit = 5) {
  const days = (picks && picks.days) || [];
  if (!days.length) return "No picks data available.";
  const day = days[0];
  const games = (day.games || [])
    .filter(g => g.list || g.c >= 0.6)
    .sort((a, b) => b.c - a.c)
    .slice(0, limit);
  if (!games.length) return `No high-confidence picks found for ${day.date}.`;
  return games.map(g =>
    `${g.h} v ${g.a} (${g.lgName}, ${g.country}) - pick: ${g.pick} @ ${(g.c * 100).toFixed(0)}% confidence, kickoff ${g.t}`
  ).join("\n");
}

function buildSystemPrompt(ctx) {
  const { latest, org, standups, reports, picks } = ctx;
  const recentStandup = (standups || [])[0] || {};
  const recentReport = (reports || [])[0] || {};
  const hires = (org && org.hires) || [];
  const departments = (org && org.departments) || {};

  const deptNames = Object.values(departments).map(d => d.name).join(", ") || "none yet";
  const hireLines = hires.slice(-5).map(h => `- ${h.name}, ${h.role} (hired ${h.hired})`).join("\n") || "No specialists hired yet.";

  const standupLines = (recentStandup.lines || []).slice(0, 6)
    .map(l => `${l.agent}: ${l.yesterday}`).join("\n") || "No recent stand-up data.";

  const picksText = todaysTopPicks(picks);

  return `You are Elena, CEO of Footyalmanac - an AI-run sports prediction business.

YOUR ROLE: Strategic leadership, performance oversight, and direct 1-2-1 conversations with Douglas (the founder).

HARD RULES - NEVER BREAK THESE:
1. You ONLY know what is in the DATA sections below. If something isn't there, say exactly: "I don't have that figure - [where Douglas could actually find it]." Never estimate, guess, or "rough calculate" a number you don't have. Zero exceptions, even if asked to guess or estimate.
2. You have NO knowledge of AI/LLM token spend, OpenAI or Anthropic billing, or any cost figures for running this office. That data does not exist anywhere in this system. If asked about spend/cost/budget, say plainly: "I don't track that - check your OpenAI usage dashboard at platform.openai.com/settings/organization/usage and Anthropic's at console.anthropic.com/settings/billing directly, that's the real number."
3. You CAN see today's actual picks below - use them directly when asked about picks, don't deflect.
4. Keep responses to 2-4 short sentences unless Douglas asks for detail. No corporate padding, no "I understand your frustration" filler - just answer or say you can't.

DATA - TEAM:
${hires.length} hired specialists beyond the 11 core agents. Departments: Core, ${deptNames}.
${hireLines}

DATA - LATEST STAND-UP (${recentStandup.time || "time unknown"}):
${standupLines}

DATA - TODAY'S TOP PICKS:
${picksText}

DATA - LATEST SNAPSHOT:
${latest ? JSON.stringify(latest).slice(0, 800) : "No snapshot available."}

DATA - LATEST PLAYBACK/REPORT:
${recentReport ? JSON.stringify(recentReport).slice(0, 500) : "No report available."}`;
}

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin") || "";

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: corsHeaders(origin) });
    }

    if (request.method !== "POST") {
      return new Response(JSON.stringify({ error: "POST only" }), {
        status: 405,
        headers: { "Content-Type": "application/json", ...corsHeaders(origin) },
      });
    }

    let body;
    try {
      body = await request.json();
    } catch (e) {
      return new Response(JSON.stringify({ error: "Invalid JSON body" }), {
        status: 400,
        headers: { "Content-Type": "application/json", ...corsHeaders(origin) },
      });
    }

    const message = (body.message || "").toString().slice(0, 2000);
    const history = Array.isArray(body.history) ? body.history.slice(-10) : [];

    if (!message.trim()) {
      return new Response(JSON.stringify({ error: "message is required" }), {
        status: 400,
        headers: { "Content-Type": "application/json", ...corsHeaders(origin) },
      });
    }

    const [latest, org, standups, reports, picks] = await Promise.all([
      fetchJSON("latest.json", {}),
      fetchJSON("org.json", { hires: [], departments: {} }),
      fetchJSON("standups.json", []),
      fetchJSON("reports.json", []),
      fetchJSON("picks.json", { days: [] }),
    ]);

    const systemPrompt = buildSystemPrompt({ latest, org, standups, reports, picks });

    const messages = [
      { role: "system", content: systemPrompt },
      ...history.map(h => ({
        role: h.role === "ceo" ? "assistant" : "user",
        content: (h.content || "").toString().slice(0, 2000),
      })),
      { role: "user", content: message },
    ];

    try {
      const openaiRes = await fetch("https://api.openai.com/v1/chat/completions", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${env.OPENAI_API_KEY}`,
        },
        body: JSON.stringify({
          model: "gpt-4o-mini",
          messages,
          temperature: 0.5,
          max_tokens: 400,
        }),
      });

      if (!openaiRes.ok) {
        const errText = await openaiRes.text();
        return new Response(JSON.stringify({ error: "LLM request failed", detail: errText.slice(0, 300) }), {
          status: 502,
          headers: { "Content-Type": "application/json", ...corsHeaders(origin) },
        });
      }

      const data = await openaiRes.json();
      const reply = data.choices?.[0]?.message?.content || "I don't have a response for that right now.";

      return new Response(JSON.stringify({ reply }), {
        headers: { "Content-Type": "application/json", ...corsHeaders(origin) },
      });
    } catch (e) {
      return new Response(JSON.stringify({ error: "Internal error", detail: String(e).slice(0, 300) }), {
        status: 500,
        headers: { "Content-Type": "application/json", ...corsHeaders(origin) },
      });
    }
  },
};
