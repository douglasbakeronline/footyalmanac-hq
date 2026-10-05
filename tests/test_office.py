"""Unit tests for footyalmanac-hq office functions."""
import unittest
import json
import sys
import os
from datetime import datetime

# Add scripts to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import org

class TestOrgFunctions(unittest.TestCase):
    """Test the hiring desk and org management functions."""
    
    def setUp(self):
        """Set up test data."""
        self.sample_data = {
            "rec": {
                "overall": {"accuracy": 0.51, "n": 1258},
                "list": {"accuracy": 0.71, "n": 31, "correct": 22},
                "byLeague": {
                    "en.2": {"accuracy": 0.37, "n": 76, "name": "England Championship"},
                    "es.1": {"accuracy": 0.58, "n": 120, "name": "Spain La Liga"}
                },
                "tiers": [
                    {"name": "Strong", "n": 100, "drawnOut": 10, "hit": 0.75, "expected": 0.80}
                ]
            },
            "runs": [
                {"conclusion": "success"} for _ in range(8)
            ] + [{"conclusion": "failure"} for _ in range(2)],
            "srec": {
                "bySport": {
                    "nfl": {"n": 55, "correct": 30}
                }
            },
            "prs": []
        }
        
        self.empty_org = {
            "hires": [],
            "departments": {},
            "log": []
        }
    
    def test_pct_formatting(self):
        """Test percentage formatting helper."""
        self.assertEqual(org.pct(0.5), "50%")
        self.assertEqual(org.pct(0.7142), "71%")
        self.assertEqual(org.pct(None), "–")
    
    def test_candidates_weak_league(self):
        """Test that weak league triggers hiring."""
        candidates = org.candidates(self.sample_data, self.empty_org)
        self.assertGreater(len(candidates), 0)
        
        # First candidate should be England Championship specialist
        key, dept, role, kpi, reason = candidates[0]
        self.assertEqual(key, "league-en.2")
        self.assertIn("Championship", role)
        self.assertEqual(kpi["type"], "league")
    
    def test_candidates_no_duplicates(self):
        """Test that we don't hire the same role twice."""
        org_with_hire = {
            "hires": [{
                "id": "h1",
                "key": "league-en.2",
                "kpi": {"type": "league", "code": "en.2"}
            }],
            "departments": {},
            "log": []
        }
        
        candidates = org.candidates(self.sample_data, org_with_hire)
        keys = [c[0] for c in candidates]
        self.assertNotIn("league-en.2", keys)
    
    def test_review_hiring_limit(self):
        """Test that hiring respects the cap."""
        org_at_cap = {
            "hires": [{"id": f"h{i}", "key": f"test-{i}", "hired": "2026-10-01"} for i in range(org.CAP)],
            "departments": {},
            "log": []
        }
        
        updated_org, new_hire = org.review(self.sample_data, org_at_cap, "2026-10-05", None)
        self.assertIsNone(new_hire)
        self.assertEqual(len(updated_org["hires"]), org.CAP)
    
    def test_review_one_per_day(self):
        """Test that only one hire happens per day."""
        org_with_today = {
            "hires": [{"id": "h1", "key": "test", "hired": "2026-10-05"}],
            "departments": {},
            "log": []
        }
        
        updated_org, new_hire = org.review(self.sample_data, org_with_today, "2026-10-05", None)
        self.assertIsNone(new_hire)
    
    def test_metric_league_type(self):
        """Test metric calculation for league specialist."""
        hire = {
            "id": "h1",
            "kpi": {"type": "league", "code": "en.2", "target": 0.50}
        }
        
        actual, target, higher, fmt, text = org.metric(hire, self.sample_data)
        self.assertEqual(actual, 0.37)
        self.assertEqual(target, 0.50)
        self.assertTrue(higher)
        self.assertEqual(fmt, "pct")
        self.assertIn("Championship", text)
    
    def test_lines_and_objectives(self):
        """Test generation of standup lines and objectives for hires."""
        test_org = {
            "hires": [{
                "id": "h1",
                "name": "Priya",
                "role": "Championship Specialist",
                "kpi": {"type": "league", "code": "en.2", "target": 0.50}
            }],
            "departments": {},
            "log": []
        }
        
        lines, objectives = org.lines_and_objectives(self.sample_data, test_org)
        
        self.assertEqual(len(lines), 1)
        self.assertEqual(len(objectives), 1)
        
        # Check line structure
        self.assertEqual(lines[0]["agent"], "h1")
        self.assertIn("yesterday", lines[0])
        self.assertIn("today", lines[0])
        self.assertIn("blockers", lines[0])
        
        # Check objective structure
        obj = objectives[0]
        self.assertEqual(obj["owner"], "h1")
        self.assertIsNotNone(obj["actual"])
        self.assertEqual(obj["target"], 0.50)
        self.assertEqual(obj["status"], "behind")  # 37% < 50%


class TestCEOAgent(unittest.TestCase):
    """Test CEO agent functionality."""
    
    def setUp(self):
        """Set up CEO test environment."""
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))
        import ceo
        self.ceo = ceo
    
    def test_ceo_profile(self):
        """Test CEO profile is properly defined."""
        profile = self.ceo.CEO_PROFILE
        self.assertEqual(profile["id"], "ceo")
        self.assertEqual(profile["name"], "Elena")
        self.assertIn("role", profile)
        self.assertIn("responsibilities", profile)
    
    def test_build_prompt(self):
        """Test prompt building includes context."""
        context = {
            "latest": {"accuracy": 0.51},
            "org": {"hires": [], "departments": {}},
            "standups": [],
            "reports": []
        }
        
        prompt = self.ceo.build_prompt("What's our current accuracy?", context)
        self.assertIn("Elena", prompt)
        self.assertIn("CEO", prompt)
        self.assertIn("What's our current accuracy?", prompt)


class TestDataIntegrity(unittest.TestCase):
    """Test data file integrity and structure."""
    
    def setUp(self):
        """Set up paths."""
        self.data_dir = os.path.join(os.path.dirname(__file__), '..', 'docs', 'data')
    
    def test_org_json_structure(self):
        """Test org.json has required structure."""
        if os.path.exists(os.path.join(self.data_dir, 'org.json')):
            with open(os.path.join(self.data_dir, 'org.json')) as f:
                org_data = json.load(f)
            
            self.assertIn("hires", org_data)
            self.assertIn("departments", org_data)
            self.assertIn("log", org_data)
            
            # Check hire structure
            for hire in org_data["hires"]:
                self.assertIn("id", hire)
                self.assertIn("name", hire)
                self.assertIn("role", hire)
                self.assertIn("kpi", hire)
                self.assertIn("hired", hire)
    
    def test_standups_json_structure(self):
        """Test standups.json has required structure."""
        if os.path.exists(os.path.join(self.data_dir, 'standups.json')):
            with open(os.path.join(self.data_dir, 'standups.json')) as f:
                standups = json.load(f)
            
            self.assertIsInstance(standups, list)
            
            if standups:
                standup = standups[0]
                self.assertIn("time", standup)
                self.assertIn("lines", standup)
                
                # Check line structure
                if standup["lines"]:
                    line = standup["lines"][0]
                    self.assertIn("agent", line)
                    self.assertIn("yesterday", line)
                    self.assertIn("today", line)


if __name__ == '__main__':
    unittest.main()
