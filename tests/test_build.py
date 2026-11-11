import json
import unittest
from datetime import datetime, timedelta, timezone

from deadahead import build, crypto
from deadahead.canvas import Canvas


class CryptoTest(unittest.TestCase):
    def test_roundtrip_and_wrong_passcode(self):
        blob = crypto.encrypt({"a": "MAT137 ✓"}, "correct horse battery")
        self.assertEqual(crypto.decrypt(blob, "correct horse battery"), {"a": "MAT137 ✓"})
        with self.assertRaises(Exception):
            crypto.decrypt(blob, "nope nope nope")
        self.assertNotIn("MAT137", json.dumps(blob))


class PlannerTest(unittest.TestCase):
    cv = Canvas("https://q.utoronto.ca", "x")

    def item(self, **kw):
        p = {
            "plannable_id": 5, "plannable_type": "assignment", "course_id": 1, "context_name": "MAT137Y1 Calculus",
            "plannable_date": "2026-11-12T04:59:00Z", "html_url": "/courses/1/assignments/5",
            "plannable": {"title": "Problem Set 4", "points_possible": 10},
            "submissions": {"submitted": False, "missing": False}, "planner_override": None,
        }
        p.update(kw)
        return p

    def test_normalizes_assignment(self):
        courses = {}
        i = build.normalize_planner_item(self.item(), self.cv, courses)
        self.assertEqual(i["title"], "Problem Set 4")
        self.assertEqual(i["url"], "https://q.utoronto.ca/courses/1/assignments/5")
        self.assertFalse(i["done"])
        self.assertEqual(courses["1"]["code"], "MAT137")

    def test_submitted_or_marked_complete_is_done(self):
        a = build.normalize_planner_item(self.item(submissions={"submitted": True}), self.cv, {})
        b = build.normalize_planner_item(self.item(planner_override={"marked_complete": True}), self.cv, {})
        self.assertTrue(a["done"] and b["done"])

    def test_skips_announcements_and_flags_tests(self):
        self.assertIsNone(build.normalize_planner_item(self.item(plannable_type="announcement"), self.cv, {}))
        q = build.normalize_planner_item(self.item(plannable={"title": "Term Test 2"}), self.cv, {})
        self.assertTrue(q["test"])


class SyllabusMergeTest(unittest.TestCase):
    def test_dedupes_items_quercus_already_has(self):
        now = datetime(2026, 11, 10, tzinfo=timezone.utc)
        q = [{"course": "1", "due": "2026-11-12T04:59:00Z", "title": "Problem Set 4"}]
        syl = [
            {"course": "1", "due": "2026-11-11T23:59:00-05:00", "title": "PS 4 due (Problem Set 4)"},
            {"course": "1", "due": "2026-11-19T09:00:00-05:00", "title": "Term Test 2", "kind": "test"},
            {"course": "1", "due": "2027-03-01T09:00:00-05:00", "title": "Far away"},
        ]
        out = build.merge_syllabus(list(q), syl, {}, now, now + timedelta(days=21))
        added = [i for i in out if i.get("source") == "syllabus"]
        self.assertEqual([i["title"] for i in added], ["Term Test 2"])
        self.assertTrue(added[0]["test"])

    def test_date_needs_timezone(self):
        with self.assertRaises(ValueError):
            build.parse_dt("2026-11-19T09:00:00")
        self.assertIsNotNone(build.parse_dt("2026-11-19T09:00:00-05:00"))


if __name__ == "__main__":
    unittest.main()
