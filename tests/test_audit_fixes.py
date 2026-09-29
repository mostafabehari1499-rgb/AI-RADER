"""Regression tests for audit fixes. Offline, no secrets, no network (localhost only)."""
import unittest


class TestDateParsing(unittest.TestCase):
    def test_rfc2822(self):
        from engine.processors.score import _parse_dt, _age_hours
        from engine.processors.normalize import make_event
        dt = _parse_dt("Mon, 28 Sep 2026 19:00:00 GMT")
        self.assertIsNotNone(dt)
        self.assertEqual(dt.year, 2026)
        # RSS item with real date must NOT fall back to discovered_at=now
        ev = make_event("t", "https://x.com/1", "Blog", "rss", "d",
                        published_at="Mon, 28 Sep 2026 19:00:00 GMT")
        age = _age_hours(ev)
        self.assertIsNotNone(age)
        self.assertGreater(age, 1.0)  # not "just now"

    def test_iso_still_works(self):
        from engine.processors.score import _parse_dt
        self.assertIsNotNone(_parse_dt("2026-09-29T10:00:00Z"))
        self.assertIsNone(_parse_dt(""))
        self.assertIsNone(_parse_dt("not a date"))


class TestFeedTimeout(unittest.TestCase):
    def test_refused_host_fails_fast(self):
        import time
        from engine.collectors.feedutil import fetch_feed
        t0 = time.time()
        with self.assertRaises(Exception):
            fetch_feed("http://127.0.0.1:9/nonexistent.xml", timeout=5)
        self.assertLess(time.time() - t0, 20,
                        "feed fetch must respect timeout, never hang")


class TestTrendBasis(unittest.TestCase):
    def test_single_run_signal_default(self):
        from engine.processors.normalize import make_event
        from engine.processors.score import score_all
        ev = make_event("t", "https://x.com/1", "S", "rss", "d")
        score_all([ev])
        self.assertEqual(ev["trend_basis"], "single-run-signal")

    def test_history_growth_bonus(self):
        from engine.processors.normalize import make_event
        from engine.processors.score import score_trend
        ev = make_event("t", "https://github.com/a/b", "GitHub", "github", "d",
                        raw_data={"stars": 20000})
        s0, _, b0 = score_trend(ev, None)
        s1, _, b1 = score_trend(ev, {"stars": 10000, "downloads": 0, "likes": 0, "sources": 1})
        self.assertEqual(b1, "history-compared")
        self.assertGreater(s1, s0)


class TestCreatorScore(unittest.TestCase):
    def test_fields_present(self):
        from engine.processors.normalize import make_event
        from engine.processors.summarize import _deterministic
        ev = make_event("XYZ test", "https://x.com/1", "S", "rss", "d")
        ev["category"] = "MODEL"
        ev["importance_score"] = 70
        ev["experiment"] = {"can_test_free": True, "options": [{"name": "Space"}]}
        ai = _deterministic(ev)
        self.assertIn("creator_opportunity_score", ai)
        self.assertTrue(0 <= ai["creator_opportunity_score"] <= 100)
        for k in ("content_angle", "target_audience", "experiment_angle",
                  "tutorial_angle", "comparison_angle"):
            self.assertTrue(ai.get(k), k)


class TestRetention(unittest.TestCase):
    def test_old_events_pruned(self):
        import tempfile
        from pathlib import Path
        from engine.processors.normalize import make_event
        from engine.storage import json_store
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            old = make_event("old", "https://x.com/old", "S", "rss", "d")
            old["id"] = "old1"
            old["discovered_at"] = "2020-01-01T00:00:00+00:00"
            new = make_event("new", "https://x.com/new", "S", "rss", "d")
            new["id"] = "new1"
            new["discovered_at"] = "2026-09-29T00:00:00+00:00"
            res = json_store.merge_events(root, [old, new], retention_days=90)
            ids = {e["id"] for e in res}
            self.assertIn("new1", ids)
            self.assertNotIn("old1", ids)


class TestConfig(unittest.TestCase):
    def test_new_vars(self):
        from engine.config import load_config, ROOT
        cfg = load_config(ROOT)
        self.assertEqual(cfg["gemini_model"], "gemini-2.0-flash")
        self.assertEqual(cfg["retention_days"], 90)


if __name__ == "__main__":
    unittest.main()
