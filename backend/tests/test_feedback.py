import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import feedback  # noqa: E402


class Record(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.original = feedback.STORE
        feedback.STORE = Path(self.tmp.name) / "nested" / "feedback.jsonl"
        self.addCleanup(lambda: setattr(feedback, "STORE", self.original))

    def stored(self):
        return [json.loads(line) for line in feedback.STORE.read_text().splitlines() if line.strip()]

    def test_stores_rating_comment_and_run_context(self):
        entry = feedback.record({
            "rating": 4, "comment": "  add specific energy  ",
            "context": {"formula": "consumption_delta", "from": "2026-09-01", "to": "2026-09-07",
                        "shift": "07:00 – 07:00", "targets": 3, "shifts": 21,
                        "counts": {"PASS": 18, "WARN": 1, "NO_DATA": 2, "ERROR": 0}},
        }, token="Bearer abc")
        self.assertEqual(entry["rating"], 4)
        self.assertEqual(entry["comment"], "add specific energy")
        self.assertEqual(entry["formula"], "consumption_delta")
        self.assertEqual((entry["pass"], entry["noData"]), (18, 2))
        self.assertEqual(len(entry["submitter"]), 8)
        self.assertNotIn("abc", json.dumps(entry))          # never the token itself
        self.assertEqual(self.stored(), [entry])

    def test_same_token_gives_the_same_submitter_id(self):
        a = feedback.record({"rating": 5}, token="Bearer abc")
        b = feedback.record({"rating": 1}, token="Bearer abc")
        c = feedback.record({"rating": 1}, token="Bearer other")
        self.assertEqual(a["submitter"], b["submitter"])
        self.assertNotEqual(a["submitter"], c["submitter"])

    def test_rating_or_comment_alone_is_enough(self):
        self.assertIsNone(feedback.record({"comment": "just a note"})["rating"])
        self.assertEqual(feedback.record({"rating": 3})["comment"], "")

    def test_rejects_empty_and_out_of_range(self):
        with self.assertRaisesRegex(ValueError, "rating or a note"):
            feedback.record({"comment": "   "})
        for bad in (0, 6, "high"):
            with self.assertRaisesRegex(ValueError, "1 to 5"):
                feedback.record({"rating": bad})

    def test_comment_is_capped(self):
        entry = feedback.record({"comment": "x" * 5000})
        self.assertEqual(len(entry["comment"]), feedback.MAX_COMMENT)

    def test_csv_export_has_a_header_and_one_row_per_entry(self):
        feedback.record({"rating": 5, "comment": "great"})
        feedback.record({"comment": "line\nbreak"})
        rows = feedback.export_csv().splitlines()
        self.assertTrue(rows[0].startswith("time,rating,comment"))
        self.assertIn("great", feedback.export_csv())
        self.assertEqual(len(self.stored()), 2)

    def test_export_is_empty_but_valid_before_any_feedback(self):
        self.assertEqual(feedback.export_csv().splitlines()[0].split(",")[0], "time")


if __name__ == "__main__":
    unittest.main()


class WebhookPayload(unittest.TestCase):
    TEAMS = "https://prod-12.westus.logic.azure.com:443/workflows/abc/triggers/manual/paths/invoke?sig=x"
    SLACK = "https://hooks.slack.com/services/T000/B000/xxxx"
    ENTRY = {"rating": 2, "comment": "Run-hours looks high", "formula": "run_hours",
             "from": "2026-09-10", "to": "2026-09-16", "targets": 4}

    def test_teams_workflow_url_gets_an_adaptive_card(self):
        payload = feedback.build_payload(self.ENTRY, self.TEAMS)
        card = payload["attachments"][0]["content"]
        self.assertEqual(payload["type"], "message")
        self.assertEqual(card["type"], "AdaptiveCard")
        texts = [b["text"] for b in card["body"]]
        self.assertIn("Run-hours looks high", texts)
        self.assertTrue(any("Newton feedback" in t for t in texts))

    def test_slack_url_gets_plain_text(self):
        payload = feedback.build_payload(self.ENTRY, self.SLACK)
        self.assertEqual(set(payload), {"text"})
        self.assertIn("Run-hours looks high", payload["text"])

    def test_format_can_be_forced(self):
        feedback.WEBHOOK_FORMAT = "card"
        self.addCleanup(lambda: setattr(feedback, "WEBHOOK_FORMAT", ""))
        self.assertIn("attachments", feedback.build_payload(self.ENTRY, self.SLACK))

    def test_a_rating_with_no_comment_still_builds(self):
        for url in (self.TEAMS, self.SLACK):
            payload = feedback.build_payload({"rating": 5, "comment": "", "formula": None}, url)
            self.assertTrue(payload)


class Settings(unittest.TestCase):
    def tearDown(self):
        for key in list(os.environ):
            if key.lower().startswith("feedback_test"):
                del os.environ[key]

    def test_exact_name_wins(self):
        os.environ["FEEDBACK_TEST_KEY"] = "exact"
        os.environ["Feedback_Test_Key"] = "other"
        self.assertEqual(feedback.setting("FEEDBACK_TEST_KEY"), "exact")

    def test_wrong_case_is_still_found(self):
        os.environ["Feedback_Test_Key"] = "typed by hand"
        self.assertEqual(feedback.setting("FEEDBACK_TEST_KEY"), "typed by hand")

    def test_missing_returns_the_default(self):
        self.assertEqual(feedback.setting("FEEDBACK_TEST_ABSENT", "fallback"), "fallback")
