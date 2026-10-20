"""Tests for the HQ planner (scripts/planner.py)."""
import os, sys, unittest
from datetime import date

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
import planner as P
import office as O

TODAY = date(2026, 10, 20)


def fb(n, conf, won, league="en.1", day="2026-10-15", **kw):
    rows = []
    for i in range(n):
        rows.append(dict({"league": league, "date": day, "confidence": conf, "expected": conf, "ok": i < won,
                          "p": [conf, 0.2, 1 - conf - 0.2], "actual": "h" if i < won else "a", "pick": "h",
                          "verified": "verified", "list": False, "reserve": False}, **kw))
    return rows


def files(graded=(), **extra):
    f = {"record-graded.json": {"graded": list(graded)}, "record.json": {}, "tennis-record.json": {},
         "sports-record.json": {}, "groupings-record.json": {}, "predictions": []}
    f.update(extra)
    return f


class TestGap(unittest.TestCase):
    def test_on_quote_is_zero(self):
        g = P.gap([(0.8, True)] * 8 + [(0.8, False)] * 2)
        self.assertEqual(g["won"], 8); self.assertAlmostEqual(g["z"], 0.0)

    def test_shortfall_is_negative(self):
        self.assertLess(P.gap([(0.8, True)] * 60 + [(0.8, False)] * 40)["z"], -4)

    def test_empty(self):
        self.assertEqual(P.gap([])["n"], 0)

    def test_football_quote_uses_expected(self):
        # score.py quotes a predicted-draw row at pick-or-draw, so that is what it must be judged against
        self.assertEqual(P.fq({"confidence": 0.52, "expected": 0.76}), 0.76)
        self.assertEqual(P.fq({"confidence": 0.52}), 0.52)


class TestPlan(unittest.TestCase):
    def keys(self, b): return [t["key"] for t in b["tasks"]]

    def test_list_shortfall_tops_the_backlog(self):
        rows = fb(40, 0.82, 26, list=True)              # 65% landed against 82% quoted
        b = P.plan(files(rows), today=TODAY)
        self.assertEqual(b["tasks"][0]["key"], "hq-list-football")
        self.assertEqual(b["tasks"][0]["owner"], "curator")
        self.assertIn("Rule 1", b["tasks"][0]["brief"])

    def test_list_on_quote_makes_no_task(self):
        b = P.plan(files(fb(40, 0.8, 32, list=True)), today=TODAY)
        self.assertNotIn("hq-list-football", self.keys(b))

    def test_old_rows_fall_outside_the_window(self):
        b = P.plan(files(fb(40, 0.82, 20, list=True, day="2026-08-01")), today=TODAY)
        self.assertNotIn("hq-list-football", self.keys(b))

    def test_band_gap_either_direction(self):
        b = P.plan(files(fb(300, 0.66, 250)), today=TODAY)     # lands far above its quote
        t = next(t for t in b["tasks"] if t["key"] == "hq-band-65")
        self.assertIn("over", t["title"]); self.assertEqual(t["owner"], "calib")

    def test_championship_goes_to_champ(self):
        b = P.plan(files(fb(80, 0.6, 30, league="en.2")), today=TODAY)
        self.assertEqual(next(t for t in b["tasks"] if t["key"] == "hq-league-en.2")["owner"], "champ")

    def test_roadmap_drops_once_shipped(self):
        b = P.plan(files(), today=TODAY, done={"hq-own-band"})
        self.assertNotIn("hq-own-band", self.keys(b)); self.assertIn("hq-tennis-surface", self.keys(b))

    def test_roadmap_ranks_below_measured_gaps(self):
        b = P.plan(files(fb(40, 0.82, 26, list=True)), today=TODAY)
        self.assertEqual(b["tasks"][-1]["metric"], "roadmap"); self.assertNotEqual(b["tasks"][0]["metric"], "roadmap")

    def test_every_owner_is_a_real_agent(self):
        b = P.plan(files(fb(40, 0.82, 26, list=True) + fb(80, 0.6, 30, league="en.2")), today=TODAY)
        for t in b["tasks"]: self.assertIn(t["owner"], P.OWNERS)

    def test_groups_legs_before_the_rule_are_ignored(self):
        leg = {"status": "lost", "p": 0.8, "event": "A v B"}
        days = [{"date": "2026-10-10", "groups": [{"name": "Steady", "legs": [dict(leg, event=f"E{i}") for i in range(60)]}]}]
        b = P.plan(files(**{"groupings-record.json": {"days": days}}), today=TODAY)
        self.assertNotIn("hq-groups-legs", self.keys(b))

    def test_unrated_fixtures(self):
        preds = [{"league": "hr.1", "unrated": True}] * 12 + [{"league": "en.1"}] * 50
        t = next(t for t in P.plan(files(predictions=preds), today=TODAY)["tasks"] if t["key"] == "hq-unrated")
        self.assertEqual(t["owner"], "quality"); self.assertIn("hr.1 (12)", t["brief"])


class TestOutcomes(unittest.TestCase):
    def test_classify(self):
        self.assertEqual(O.classify(["RELEASES.md", "engine.py"]), "model")
        self.assertEqual(O.classify(["RELEASES.md", "sources.py", "tests/test_x.py"]), "data")
        self.assertEqual(O.classify(["RELEASES.md", "tests/test_x.py"]), "tests")
        self.assertEqual(O.classify(["RELEASES.md", "claude/note.md", "tools/x.py"]), "evidence")
        self.assertEqual(O.classify(["international.json"]), "model")


if __name__ == "__main__":
    unittest.main()
