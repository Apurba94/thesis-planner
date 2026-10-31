import datetime
import os
import shutil
import tempfile
import tkinter as tk
import unittest
import zipfile
from unittest import mock

from thesis_planner import app as A
from thesis_planner import appkit as ak
from thesis_planner import plan as pl

TODAY = "2026-03-02"            # a Monday


def ch(title="C", target=1000, words=0, status="Not started", due=None, position=1):
    return {"title": title, "target": target, "words": words, "status": status, "due": due, "position": position}


class TestProgress(unittest.TestCase):
    def test_totals(self):
        p = pl.progress([ch(target=1000, words=500, status="First draft"), ch(target=1000, words=1500, status="Final")])
        self.assertEqual((p["target"], p["words"], p["left"]), (2000, 2000, 500))      # overflow on one chapter does not cancel the other
        self.assertEqual(p["fraction"], 0.75)
        self.assertEqual(p["stage"], 0.75)
        self.assertEqual(pl.progress([])["fraction"], 0)

    def test_working_days(self):
        self.assertEqual(pl.working_days("2026-03-02", "2026-03-08", 5), 5)
        self.assertEqual(pl.working_days("2026-03-02", "2026-03-08", 7), 7)
        self.assertEqual(pl.working_days("2026-03-07", "2026-03-08", 5), 0)
        self.assertEqual(pl.working_days("2026-03-02", "2026-03-15", 3), 6)

    def test_pace_and_projection(self):
        sessions = [{"day": pl.add_days(TODAY, -i), "words": 100} for i in range(28)] + [{"day": "2025-01-01", "words": 9999}]
        self.assertEqual(pl.recent_pace(sessions, TODAY), 100)
        self.assertEqual(pl.projected_finish(1000, 100, TODAY), pl.add_days(TODAY, 10))
        self.assertEqual(pl.projected_finish(0, 0, TODAY), TODAY)
        self.assertIsNone(pl.projected_finish(1000, 0, TODAY))
        self.assertEqual(pl.required_pace(1000, TODAY, "2026-03-06"), 200)
        self.assertIsNone(pl.required_pace(1000, TODAY, "2026-01-01"))

    def test_status_days_late(self):
        sessions = [{"day": TODAY, "words": 280}]              # 10 words a day
        st = pl.status_line([ch(target=1000)], sessions, TODAY, pl.add_days(TODAY, 50))
        self.assertEqual(st["days_late"], 50)


class TestBurndown(unittest.TestCase):
    def test_reconstruction(self):
        chapters = [ch(target=1000, words=300)]
        sessions = [{"day": "2026-03-01", "words": 100}, {"day": "2026-03-02", "words": 100}]
        b = pl.burndown(chapters, sessions, "2026-02-28", "2026-03-10", "2026-03-02")
        self.assertEqual(b["actual"], [(0, 900), (1, 800), (2, 700)])       # 100 words existed before logging began
        self.assertEqual(b["ideal"], [(0, 1000), (10, 0)])


class TestSchedule(unittest.TestCase):
    def test_proportional_and_ordered(self):
        chapters = [ch("A", 2000, position=1), ch("B", 6000, position=2), ch("Done", 9000, status="Final", position=3)]
        rows, free = pl.schedule(chapters, TODAY, pl.add_days(TODAY, 100))
        self.assertEqual([r["chapter"] for r in rows], ["A", "B"])
        a = pl.days_between(rows[0]["start"], rows[0]["finish"])
        b = pl.days_between(rows[1]["start"], rows[1]["finish"])
        self.assertAlmostEqual(b / a, 3, delta=0.2)
        self.assertEqual(free, pl.add_days(TODAY, 85))                     # 15% buffer
        self.assertLessEqual(rows[-1]["finish"], free)
        self.assertEqual(rows[0]["finish"], rows[1]["start"])

    def test_short_time(self):
        rows, _ = pl.schedule([ch("A"), ch("B")], TODAY, pl.add_days(TODAY, 2))
        self.assertEqual(len(rows), 2)
        for r in rows:
            self.assertGreater(r["finish"], r["start"])


class TestRisks(unittest.TestCase):
    def test_messages(self):
        chapters = [ch("Late", 20000, 100, due="2026-01-01"), ch("Long", 1000, 1300, status="Final")]
        actions = [{"done": 0, "due": "2026-02-01", "text": "Fix it"}]
        rows = pl.risks(chapters, [{"day": TODAY, "words": 280}], [{"day": "2025-10-01"}], actions, TODAY, pl.add_days(TODAY, 5))
        text = " | ".join(m for _, m in rows)
        for needle in ("days late", "words every writing day", "Late was due", "Long is 30% over", "Overdue action: Fix it", "days ago"):
            self.assertIn(needle, text)
        self.assertEqual(rows[0][0], "danger")
        self.assertIn("has passed", pl.risks([], [], [], [], TODAY, "2026-01-01")[0][1])
        self.assertTrue(any("No words logged" in m for _, m in pl.risks([ch()], [], [], [], TODAY, pl.add_days(TODAY, 90))))

    def test_streak(self):
        s = [{"day": TODAY, "words": 5}, {"day": pl.add_days(TODAY, -1), "words": 5}, {"day": pl.add_days(TODAY, -2), "words": 0}]
        self.assertEqual(pl.streak(s, TODAY), 2)
        self.assertEqual(pl.streak(s, pl.add_days(TODAY, 1)), 2)
        self.assertEqual(pl.streak(s, pl.add_days(TODAY, 3)), 0)


class TestFiles(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def path(self, name, text):
        p = os.path.join(self.dir, name)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(text)
        return p

    def test_counts(self):
        self.assertEqual(pl.count_words("Hello, world! It's 2026 and well-known."), 6)
        self.assertEqual(pl.words_in_file(self.path("a.txt", "one two three")), 3)
        tex = "% comment here\n\\section{Intro}\nReal words here.\n\\begin{figure}ignored text\\end{figure}\n"
        self.assertEqual(pl.words_in_file(self.path("a.tex", tex)), 3)

    def test_docx(self):
        p = os.path.join(self.dir, "a.docx")
        xml = ('<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
               '<w:p><w:r><w:t>Four words </w:t></w:r><w:r><w:t>in here</w:t></w:r></w:p><w:p><w:r><w:t>and two</w:t></w:r></w:p></w:body></w:document>')
        with zipfile.ZipFile(p, "w") as z:
            z.writestr("word/document.xml", xml)
        self.assertEqual(pl.words_in_file(p), 6)

    def test_ics(self):
        text = pl.ics("2026-12-01", [ch("Intro, part 1", due="2026-06-01")])
        self.assertEqual(text.count("BEGIN:VEVENT"), 2)
        self.assertIn("Intro\\, part 1", text)


class TestGui(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        self.store = ak.Store(A.SCHEMA, os.path.join(self.dir, "t.sqlite3"), A.APP.APP_NAME)
        A.sample(self.store)
        try:
            self.app = A.APP(self.store)
        except tk.TclError as exc:
            self.skipTest(str(exc))
        self.errors = []
        self.app.report_callback_exception = lambda e, v, t: self.errors.append(repr(v))
        self.app.update()

    def tearDown(self):
        self.store.close()
        self.app.destroy()
        shutil.rmtree(self.dir, ignore_errors=True)
        self.assertEqual(self.errors, [])

    def test_every_screen_in_both_themes(self):
        for theme in ("Dark", "Light"):
            self.app.set_theme(theme)
            for t in self.app.titles():
                self.app.navigate(t)
                self.app.update()

    def test_count_from_file_logs_the_gain(self):
        self.app.navigate("Chapters")
        c = self.app.views["Chapters"]
        rid = self.store.list("chapter")[3]["id"]
        c.view.select(rid)
        p = os.path.join(self.dir, "draft.txt")
        with open(p, "w") as fh:
            fh.write("word " * 1500)
        n = self.store.count("session")
        self.assertEqual(c.apply_count(p), 1500)
        self.assertEqual(self.store.get("chapter", rid)["words"], 1500)
        self.assertEqual(self.store.count("session"), n + 1)
        self.assertEqual(self.store.list("session")[0]["words"], 600)
        with mock.patch("tkinter.messagebox.showerror") as err:
            self.assertIsNone(c.apply_count(os.path.join(self.dir, "missing.docx")))
        self.assertTrue(err.called)

    def test_plan_validation_and_schedule(self):
        self.app.navigate("Plan")
        p = self.app.views["Plan"]
        self.assertTrue(p.table.tree.get_children())
        p.deadline.set("soon")
        with mock.patch("tkinter.messagebox.showerror") as err:
            p.save()
        self.assertTrue(err.called)
        p.deadline.set("2020-01-01")
        p.save()
        self.assertFalse(p.table.tree.get_children())
        self.assertIn("future", p.info.cget("text"))

    def test_templates_and_empty(self):
        self.store.close()
        self.app.destroy()
        self.store = ak.Store(A.SCHEMA, os.path.join(self.dir, "e.sqlite3"), A.APP.APP_NAME)
        self.app = A.APP(self.store)
        self.app.report_callback_exception = lambda e, v, t: self.errors.append(repr(v))
        for t in self.app.titles():
            self.app.navigate(t)
            self.app.update()
        self.app.navigate("Chapters")
        self.app.views["Chapters"].add_template("Standard five-chapter thesis")
        self.assertEqual(self.store.count("chapter"), 5)


if __name__ == "__main__":
    unittest.main()
