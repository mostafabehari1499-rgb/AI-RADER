"""Offline unit tests for AI RADAR. No network. Run: python -m unittest discover -s tests"""
import json
import tempfile
import unittest
from pathlib import Path


class TestNormalize(unittest.TestCase):
    def test_make_event_schema(self):
        from engine.processors.normalize import make_event, validate_event, normalize_title
        ev = make_event("Hello World!", "https://x.com/a", "GitHub", "github", "desc", "me", "2026-01-01", ["t"], {"k": 1})
        self.assertEqual(validate_event(ev), [])
        self.assertEqual(ev["category"], "OTHER")
        self.assertIn("hello world", normalize_title("Hello, WORLD!"))

    def test_bad_source_type(self):
        from engine.processors.normalize import make_event
        with self.assertRaises(ValueError):
            make_event("t", "u", "s", "nope")


class TestDedup(unittest.TestCase):
    def _ev(self, title, url, source="GitHub", st="github"):
        from engine.processors.normalize import make_event
        return make_event(title, url, source, st, "d" * 50)

    def test_same_repo_clusters(self):
        from engine.processors.deduplicate import deduplicate
        a = self._ev("cool project", "https://github.com/o/xyz-7b", "GitHub", "github")
        b = self._ev("cool project release", "https://huggingface.co/o/xyz-7b", "Hugging Face", "huggingface")
        # force same canonical key via same repo-ish? use identical HF url host fallback:
        # directly test model-name clustering:
        from engine.processors.normalize import make_event
        m1 = make_event("XYZ-7B released", "https://huggingface.co/a/xyz-7b", "Hugging Face", "huggingface", "x")
        m2 = make_event("XYZ-7B weights out", "https://github.com/a/other", "GitHub", "github", "y")
        uniq, removed = deduplicate([m1, m2])
        self.assertEqual(len(uniq), 1)
        self.assertEqual(removed, 1)
        self.assertGreaterEqual(len(uniq[0]["merged_sources"]), 2)

    def test_distinct_stays(self):
        from engine.processors.deduplicate import deduplicate
        uniq, removed = deduplicate([
            self._ev("alpha model release", "https://example.com/a"),
            self._ev("totally different robot paper", "https://example.com/b"),
        ])
        self.assertEqual(len(uniq), 2)
        self.assertEqual(removed, 0)


class TestClassify(unittest.TestCase):
    def test_mcp_and_model(self):
        from engine.processors.normalize import make_event
        from engine.processors.classify import classify_event
        ev = make_event("New MCP server for agents", "https://github.com/a/b", "GitHub", "github", "agent mcp")
        classify_event(ev, {"mcp": ["MCP", "AGENT"], "agent": ["AGENT"]})
        self.assertIn(ev["category"], ("MCP", "AGENT", "GITHUB"))
        ev2 = make_event("XYZ-7B open weights LLM", "https://huggingface.co/a/xyz-7b", "Hugging Face", "huggingface", "")
        classify_event(ev2, {"llm": ["MODEL"]})
        self.assertEqual(ev2["category"], "MODEL")


class TestScore(unittest.TestCase):
    def test_importance_and_trend(self):
        from engine.processors.normalize import make_event
        from engine.processors.score import score_all, importance_level
        from engine.processors.normalize import utcnow_iso
        ev = make_event("Big official release", "https://github.com/o/r", "GitHub", "github",
                        "x", published_at=utcnow_iso(), tags=["official-release", "open-source"],
                        raw_data={"stars": 20000})
        ev["merged_sources"] = ["GitHub", "Hugging Face", "YouTube"]
        ev["experiment"] = {"can_test_free": True}
        score_all([ev])
        self.assertGreaterEqual(ev["importance_score"], 75)
        self.assertEqual(importance_level(ev["importance_score"]), ev["importance_level"])
        self.assertIn(ev["trend_status"], ("STABLE", "RISING", "HOT", "VIRAL"))

    def test_levels(self):
        from engine.processors.score import importance_level
        self.assertEqual(importance_level(95), "BREAKING")
        self.assertEqual(importance_level(80), "HIGH")
        self.assertEqual(importance_level(65), "IMPORTANT")
        self.assertEqual(importance_level(50), "NORMAL")
        self.assertEqual(importance_level(10), "LOW")


class TestExperiment(unittest.TestCase):
    def test_space_detected(self):
        from engine.processors.normalize import make_event
        from engine.processors.experiment_finder import find_experiments
        ev = make_event("Demo", "https://huggingface.co/spaces/a/b", "HF", "huggingface", "")
        r = find_experiments(ev)
        self.assertTrue(r["can_test_free"])
        self.assertTrue(any(o["type"] == "huggingface_space" for o in r["options"]))

    def test_no_fabrication(self):
        from engine.processors.normalize import make_event
        from engine.processors.experiment_finder import find_experiments
        ev = make_event("Paper", "https://arxiv.org/abs/1234", "arXiv", "arxiv", "theory only")
        r = find_experiments(ev)
        self.assertFalse(r["can_test_free"])


class TestTelegram(unittest.TestCase):
    def test_format_alert_no_crash(self):
        from engine.processors.normalize import make_event
        from engine.notifications.telegram import format_alert, format_digest
        ev = make_event("XYZ-7B", "https://example.com/m", "Hugging Face", "huggingface", "open llm")
        ev.update({"importance_score": 91, "importance_level": "BREAKING",
                   "trend_status": "HOT", "category": "MODEL",
                   "importance_reasons": ["Official release"],
                   "experiment": {"can_test_free": False, "options": [], "note": "none"},
                   "ai": {"summary_ar": "ملخص", "why": "مهم", "content_formats": ["LIVE TEST"]}})
        msg = format_alert(ev)
        self.assertIn("AI RADAR", msg)
        d = format_digest([ev])
        self.assertIn("RADAR", d)


class TestStorage(unittest.TestCase):
    def test_merge_and_cap(self):
        from engine.processors.normalize import make_event
        from engine.storage import json_store
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            from datetime import datetime, timedelta, timezone
            now = datetime.now(timezone.utc)
            evs = []
            for i in range(3):
                e = make_event(f"T{i}", f"https://x.com/{i}", "GitHub", "github", "d")
                e["id"] = f"id{i}"
                e["discovered_at"] = (now - timedelta(days=i)).isoformat()
                evs.append(e)
            json_store.merge_events(root, evs)
            all_ev = json.loads((root / "data" / "events.json").read_text(encoding="utf-8"))
            self.assertEqual(len(all_ev), 3)
            # re-merge same → no dup
            json_store.merge_events(root, evs)
            all_ev2 = json.loads((root / "data" / "events.json").read_text(encoding="utf-8"))
            self.assertEqual(len(all_ev2), 3)


class TestConfig(unittest.TestCase):
    def test_load(self):
        from engine.config import load_config, ROOT
        cfg = load_config(ROOT)
        self.assertIn("telegram_min_score", cfg)
        self.assertIsInstance(cfg["telegram_min_score"], int)


if __name__ == "__main__":
    unittest.main()
