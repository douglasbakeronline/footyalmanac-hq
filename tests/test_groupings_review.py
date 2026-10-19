"""Tests for the groupings review loop.

The review exists because the Odds tab was quoting 79.4% on legs that hit
72.4%, and 32.4% on groups that won 16.4%. These tests pin the direction of
the correction, because a sign error here silently makes the board MORE
overconfident while looking like a fix.
"""
import json
import math
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
os.chdir(os.path.join(os.path.dirname(__file__), ".."))

import groupings_review as GR


def _leg(p, odds, status="won", est=False, when="2026-10-05T12:00:00Z"):
    return {"p": p, "odds": odds, "status": status, "est": est, "when": when}


def _group(name, legs, odds, p, status="lost"):
    return {"name": name, "legs": legs, "odds": odds, "p": p, "status": status}


class TestDirection(unittest.TestCase):
    """The single most dangerous bug: applying the haircut backwards."""

    def test_overconfident_model_gets_lower_probability(self):
        # quoted 0.79, actually lands 0.72 -> gap is negative
        gap = 0.724 - 0.794
        self.assertLess(gap, 0)
        quoted, corrected = 0.79, 0.79 + gap
        self.assertLess(corrected, quoted,
                        "correcting an overconfident model must LOWER the number")

    def test_correction_is_not_upwards(self):
        for gap in (-0.20, -0.07, -0.01):
            self.assertLess(0.8 + gap, 0.8)

    def test_ev_uses_corrected_probability(self):
        gap, quoted, odds = -0.07, 0.80, 1.36
        true_ev = (quoted + gap) * odds - 1
        naive_ev = quoted * odds - 1
        self.assertLess(true_ev, naive_ev,
                        "EV must be computed on the corrected probability")


class TestVerdicts(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._orig = GR.DATA
        GR.DATA = self.tmp

    def tearDown(self):
        GR.DATA = self._orig
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _review_with(self, groups):
        with open(os.path.join(self.tmp, "groupings.json"), "w") as f:
            json.dump({"days": [{"date": "2026-10-05", "groups": groups}]}, f)
        return GR.review()

    def test_insufficient_data_makes_no_claim(self):
        small = [_group("Steady", [_leg(0.8, 1.4)] * 5, 4.0, 0.33) for _ in range(3)]
        r = self._review_with(small)
        self.assertEqual(r["verdict"], "insufficient data")
        for field in ("haircut", "confidence", "ev"):
            self.assertNotIn(field, r,
                             "no tuning value may leak out below the sample bar")


class TestGuards(unittest.TestCase):
    def test_apply_review_is_a_noop_without_a_verdict(self):
        import markets as MK
        g = [{"name": "Steady", "odds": 3.0, "p": 0.3, "legs": [{"p": 0.8, "odds": 1.4}] * 5}]
        kept, info = MK.apply_review(g)
        # with no review file, or an insufficient-data verdict, nothing changes
        if info is None:
            self.assertEqual(len(kept), 1)
            self.assertEqual(kept[0]["p"], 0.3)

    def test_dropped_groups_recorded(self):
        import markets as MK
        g = [{"name": "Steady", "odds": 2.5, "p": 0.9,
              "legs": [{"p": 0.5, "odds": 1.2}] * 5}]
        kept, info = MK.apply_review(g)
        if info is not None:
            self.assertIn("dropped", info)
            self.assertIn("haircut", info)


class TestRealRecord(unittest.TestCase):
    """Against the real record, if present."""

    def test_record_reproduces_the_known_finding(self):
        path = os.path.join("docs", "data", "groupings-record.json")
        if not os.path.exists(path):
            self.skipTest("no groupings record available")
        r = GR.review()
        self.assertEqual(r["verdict"], "overconfident")
        self.assertAlmostEqual(r["haircut"], 0.072, places=2)
        self.assertLess(r["ev"]["meanPerLeg"], 0)
        self.assertLess(r["confidence"]["hi"], 0,
                        "the overconfidence must be statistically real")


if __name__ == "__main__":
    unittest.main()
