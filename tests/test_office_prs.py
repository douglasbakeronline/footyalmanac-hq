"""24 Nov 2026: agent_prs reads back far enough for the planner's 30-day rest."""
import os, sys, unittest
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import office

NOW = datetime(2026, 11, 24, 4, 0, tzinfo=timezone.utc)


def pr(n, days_ago, objective=None, merged=True, office_label=True):
    at = (NOW - timedelta(days=days_ago)).strftime("%Y-%m-%dT%H:%M:%SZ")
    labels = ([{"name": "office-agent"}] if office_label else []) + (
        [{"name": f"objective:{objective}"}] if objective else [])
    return {"number": n, "title": f"PR {n}", "html_url": f"u/{n}", "labels": labels, "state": "closed",
            "created_at": at, "merged_at": at if merged else None, "closed_at": at}


def pages_of(prs, size=100):
    calls = []
    def get(n):
        calls.append(n)
        return prs[(n - 1) * size: n * size]
    return get, calls


class AgentPrsWindow(unittest.TestCase):
    def setUp(self):
        self._pr_outcome_saved, self._cache = office.pr_outcome, dict(office.OUTCOMES)
        office.pr_outcome = lambda n: "evidence"
        office.OUTCOMES.clear()

    def tearDown(self):
        office.pr_outcome = self._pr_outcome_saved
        office.OUTCOMES.clear(); office.OUTCOMES.update(self._cache)

    def test_a_merge_a_week_back_is_still_seen_past_the_first_page(self):
        # 150 newer PRs (session PRs, unlabelled) sit in front of the 17 Nov merge
        prs = [pr(1000 - i, i * 0.04, office_label=False) for i in range(150)]
        prs += [pr(376, 7, "hq-tennis-surface")] + [pr(300 - i, 8 + i * 0.5) for i in range(100)]
        get, calls = pages_of(prs)
        out = office.agent_prs(get, now=NOW)
        self.assertIn("hq-tennis-surface", {p["objective"] for p in out})
        self.assertEqual(calls, [1, 2])

    def test_stops_once_a_page_reaches_past_the_window(self):
        prs = [pr(900 - i, i * 0.5) for i in range(400)]   # 200 days of PRs
        get, calls = pages_of(prs)
        office.agent_prs(get, now=NOW)
        self.assertEqual(calls, [1])                     # page 1 already reaches 49 days back

    def test_page_bound_and_empty_page(self):
        prs = [pr(900 - i, i * 0.001) for i in range(1000)]
        get, calls = pages_of(prs)
        office.agent_prs(get, now=NOW)
        self.assertEqual(len(calls), office.PR_PAGES)
        get, calls = pages_of([])
        self.assertEqual(office.agent_prs(get, now=NOW), [])

    def test_old_merges_are_not_classed_afresh(self):
        seen = []
        office.pr_outcome = lambda n: seen.append(n) or "evidence"
        office.OUTCOMES["50"] = "model"
        get, _ = pages_of([pr(60, 2), pr(55, 20), pr(50, 25)])
        out = {p["n"]: p["outcome"] for p in office.agent_prs(get, now=NOW)}
        self.assertEqual(seen, [60])
        self.assertEqual(out, {60: "evidence", 55: None, 50: "model"})


if __name__ == "__main__":
    unittest.main()
