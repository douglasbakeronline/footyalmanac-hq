"""The office's Daily List covers every sport, and yesterday's list is graded across all three records."""
import os, sys, unittest
from datetime import datetime, timedelta
from unittest import mock
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
import office as O


class AllSports(unittest.TestCase):
    def test_yesterday_merges_three_records(self):
        y = (datetime.now(O.UK).date() - timedelta(days=1)).isoformat()
        recs = {
            "record.json": {"days": [{"date": y, "games": [{"home": "A", "away": "B", "pick": "h", "confidence": .9, "ok": True, "result": [2, 0], "list": True},
                                                         {"home": "C", "away": "D", "pick": "a", "confidence": .6, "ok": False, "list": False}]}]},
            "tennis-record.json": {"days": [{"date": y, "games": [{"playerA": "X", "playerB": "Y", "pick": "X", "confidence": .85, "ok": False, "list": True, "note": "Y bt X"}]}]},
            "sports-record.json": {"days": [{"date": y, "games": [{"home": "S", "away": "T", "pick": "S", "label": "NFL", "confidence": .8, "ok": None, "list": True, "score": None}]}]},
        }
        with mock.patch.object(O, "raw", side_effect=lambda f: recs.get(f)):
            out = O.list_yesterday()
        self.assertEqual((out["n"], out["graded"], out["won"]), (3, 2, 1))
        self.assertEqual(out["rows"][0]["pick"], "X")              # misses first
        self.assertIn("A", [r["pick"] for r in out["rows"]])        # football h -> team name
        self.assertEqual({r["sport"] for r in out["rows"]}, {"football", "tennis", "NFL"})

    def test_other_sports_list_and_reserve_only(self):
        tennis = {"matches": [{"date": "2026-10-06", "time": "09:00", "tour": "ATP", "tournament": "Tokyo", "playerA": "P", "playerB": "Q",
                               "pick": "Q", "confidence": .81, "list": True, "reserve": False},
                              {"date": "2026-10-06", "playerA": "R", "playerB": "S", "pick": "R", "confidence": .55, "list": False, "reserve": False}]}
        sports = {"sports": {"rugby": {"name": "Rugby", "games": [{"when": "2026-10-09T18:45Z", "label": "Premiership", "home": "L", "away": "G",
                                                                    "pick": "L", "confidence": .76, "list": True, "reserve": False}]}}}
        with mock.patch.object(O, "_site_js", side_effect=lambda n: tennis if n.startswith("tennis") else sports):
            out = O.other_sport_picks()
        self.assertEqual([g["pick"] for g in out], ["Q", "L"])
        self.assertEqual(out[0]["side"], "a")
        self.assertEqual(out[1]["date"], "2026-10-09")
        self.assertEqual(out[1]["t"], "19:45")                       # UK time (BST)


if __name__ == "__main__":
    unittest.main()
