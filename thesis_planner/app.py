"""Thesis Planner desktop program."""
import datetime
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from . import appkit as ak
from . import plan as pl
from .appkit import Entity, Field, ValidationError, entities

SCHEMA = entities(
    Entity("chapter", "Chapter", "Chapters", "title", [
        Field("position", "Order", "int", default=1, list_col=True, width=6),
        Field("title", "Title", required=True, list_col=True, width=28),
        Field("status", "Status", "choice", pl.STATUS, default="Not started", list_col=True, width=14),
        Field("target", "Target words", "int", default=10000, list_col=True, width=11),
        Field("words", "Words now", "int", default=0, list_col=True, width=10),
        Field("due", "Due", "date", list_col=True, width=11),
        Field("file", "Draft file"),
        Field("notes", "Notes", "long"),
    ], "position, id"),
    Entity("session", "Writing session", "Writing log", "day", [
        Field("day", "Date", "date", required=True, list_col=True, width=11),
        Field("chapter_id", "Chapter", "ref", ref="chapter", list_col=True, width=26),
        Field("words", "Words written", "int", default=0, list_col=True, width=11),
        Field("minutes", "Minutes", "int", list_col=True, width=8),
        Field("notes", "Notes", "long"),
    ], "day DESC, id DESC"),
    Entity("meeting", "Meeting", "Supervisor meetings", "topic", [
        Field("day", "Date", "date", required=True, list_col=True, width=11),
        Field("topic", "Topic", required=True, list_col=True, width=34),
        Field("agenda", "Agenda", "long"),
        Field("decisions", "Decisions", "long"),
    ], "day DESC, id DESC"),
    Entity("action", "Action", "Actions", "text", [
        Field("text", "Action", required=True, list_col=True, width=44),
        Field("meeting_id", "From meeting", "ref", ref="meeting", list_col=True, width=26),
        Field("due", "Due", "date", list_col=True, width=11),
        Field("done", "Done", "bool", list_col=True, width=6),
    ], "done, COALESCE(due, '9999'), id"),
)


def sample(store):
    today = datetime.date.today()
    day = lambda n: (today + datetime.timedelta(days=n)).isoformat()
    store.set_setting("deadline", day(240))
    store.set_setting("start", day(-60))
    store.set_setting("title", "Sample thesis on urban resilience")
    data = [("Introduction", "Revising", 8000, 6800), ("Literature review", "First draft", 18000, 15200), ("Methodology", "First draft", 12000, 5400),
            ("Results", "Outlining", 18000, 900), ("Discussion and conclusion", "Not started", 14000, 0)]
    ids = []
    for i, (t, st, target, w) in enumerate(data, 1):
        ids.append(store.insert("chapter", position=i, title=t, status=st, target=target, words=w, due=day(40 * i - 30)))
    for i in range(36):
        if i % 3 != 2:
            store.insert("session", day=day(-i), chapter_id=ids[i % 3], words=280 + (i * 37) % 300, minutes=90)
    m = store.insert("meeting", day=day(-12), topic="Review of the methods chapter", decisions="Add a section on sampling.")
    store.insert("action", text="Rewrite the sampling section", meeting_id=m, due=day(5))
    store.insert("action", text="Send the literature review draft", meeting_id=m, due=day(-3))


def settings(store):
    return store.get_setting("deadline") or None, int(store.get_setting("per_week", "5") or 5)


class Overview(ttk.Frame):
    title = "Overview"

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.scroll = ak.ScrollFrame(self)
        self.scroll.pack(fill="both", expand=True)

    def refresh(self):
        body = self.scroll.body
        for w in body.winfo_children():
            w.destroy()
        s = self.app.store
        today = ak.today()
        deadline, per_week = settings(s)
        ch, se, me, ac = s.list("chapter"), s.list("session"), s.list("meeting"), s.list("action")
        st = pl.status_line(ch, se, today, deadline, per_week)
        p = st["progress"]
        left = "%d days" % pl.days_between(today, deadline) if deadline else "not set"
        ak.tiles(body, [("Words written", "{:,}".format(p["words"]), "of {:,}".format(p["target"])),
                        ("Finished", "%d%%" % (100 * p["stage"]), "weighted by chapter stage"),
                        ("Time left", left, deadline or "set a date in Plan"),
                        ("Needed per writing day", "%d" % st["needed"] if st["needed"] is not None else "-", "your recent pace is %d a day" % st["pace"]),
                        ("Writing streak", "%d days" % pl.streak(se, today), "")]).pack(fill="x", pady=(0, 8))
        cols = ttk.Frame(body)
        cols.pack(fill="both", expand=True)
        cols.columnconfigure(0, weight=3, uniform="c")
        cols.columnconfigure(1, weight=2, uniform="c")
        a = ak.panel(cols, "Burndown: words left")
        a.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self.chart = tk.Canvas(a, height=int(250 * self.app.scale), bg=self.app.colors["panel"], highlightthickness=0)
        self.chart.pack(fill="both", expand=True)
        self.chart.bind("<Configure>", lambda e: self.draw())
        finish = st["finish"]
        note = "Projected finish: %s" % finish if finish else "Log some writing to see a projected finish."
        if st["days_late"] is not None:
            note += "  (%d days %s the deadline)" % (abs(st["days_late"]), "after" if st["days_late"] > 0 else "before")
        ttk.Label(a, text=note, style="PanelMuted.TLabel").pack(anchor="w", pady=(6, 0))
        b = ak.panel(cols, "Attention")
        b.grid(row=0, column=1, sticky="nsew")
        rows = pl.risks(ch, se, me, ac, today, deadline, per_week)
        if not rows:
            ttk.Label(b, text="Nothing needs attention.", style="PanelMuted.TLabel").pack(anchor="w")
        for level, msg in rows[:8]:
            style = {"danger": "Danger.TLabel", "warning": "Warning.TLabel"}.get(level, "Info.TLabel")
            ttk.Label(b, text=msg, style=style, wraplength=int(360 * self.app.scale)).pack(anchor="w", pady=1)
        c = ak.panel(body, "Chapters")
        c.pack(fill="x", pady=(8, 0))
        for x in ch:
            row = ttk.Frame(c, style="Panel.TFrame")
            row.pack(fill="x", pady=1)
            ttk.Label(row, text=ak.short(x["title"], 34), style="Panel.TLabel", width=34).pack(side="left")
            ak.bar(row, min(1.0, (x["words"] or 0) / max(1, x["target"] or 1)), self.app.colors, width=220, color=self.app.colors["accent"]).pack(side="left", padx=6)
            ttk.Label(row, text="{:,} / {:,}".format(x["words"] or 0, x["target"] or 0), style="PanelMuted.TLabel", width=18).pack(side="left")
            ttk.Label(row, text=x["status"], style="PanelMuted.TLabel").pack(side="left")

    def draw(self):
        c, col, sc = self.chart, self.app.colors, self.app.scale
        if not c.winfo_exists():
            return
        c.delete("all")
        s = self.app.store
        ch = s.list("chapter")
        deadline, _ = settings(s)
        start = s.get_setting("start") or ak.today()
        data = pl.burndown(ch, s.list("session"), start, deadline, ak.today())
        w, h = max(c.winfo_width(), 200), max(c.winfo_height(), 100)
        if not data["total"]:
            c.create_text(w / 2, h / 2, text="Add chapters to see the chart.", fill=col["muted"])
            return
        x = lambda i: 46 * sc + i / max(1, data["length"]) * (w - 60 * sc)
        y = lambda v: h - 20 * sc - v / data["total"] * (h - 34 * sc)
        c.create_line(x(0), y(data["total"]), x(data["length"]), y(0), fill=col["muted"], dash=(4, 3))
        pts = [v for i, n in data["actual"] for v in (x(i), y(n))]
        if len(pts) >= 4:
            c.create_line(*pts, fill=col["accent"], width=2 * sc)
        for v in (0, data["total"] // 2, data["total"]):
            c.create_text(40 * sc, y(v), text="{:,}".format(v), anchor="e", fill=col["muted"], font=(ak.FONT, 8))


class Chapters(ttk.Frame):
    title = "Chapters"

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        self.view = ak.EntityView(self, app, "chapter", buttons=[("Count words from file", self.count), ("Add template", self.template)])
        self.view.pack(fill="both", expand=True)
        self.refresh, self.commit = self.view.refresh, self.view.commit

    def count(self):
        if self.view.current is None:
            self.app.status("Select a chapter first")
            return
        row = self.app.store.get("chapter", self.view.current)
        path = row["file"] or filedialog.askopenfilename(parent=self, filetypes=[("Drafts", "*.docx *.txt *.md *.tex"), ("All files", "*.*")])
        if path:
            self.apply_count(path)

    def apply_count(self, path):
        try:
            n = pl.words_in_file(path)
        except (OSError, KeyError, ValueError) as exc:
            messagebox.showerror("Count words", "Could not read that file.\n\n%s" % exc, parent=self)
            return None
        row = self.app.store.get("chapter", self.view.current)
        self.app.store.update("chapter", self.view.current, words=n, file=path)
        gained = n - (row["words"] or 0)
        if gained > 0:
            self.app.store.insert("session", day=ak.today(), chapter_id=self.view.current, words=gained, notes="From the file")
        self.view.form.load(self.app.store.get("chapter", self.view.current))
        self.view.refresh()
        self.app.status("%s words, %+d since last time" % ("{:,}".format(n), gained))
        return n

    def template(self):
        win = tk.Toplevel(self)
        win.title("Add chapters from a template")
        win.transient(self.winfo_toplevel())
        win.configure(bg=self.app.colors["panel"])
        v = tk.StringVar(value=next(iter(pl.TEMPLATES)))
        f = ttk.Frame(win, style="Panel.TFrame", padding=14)
        f.pack()
        ak.labeled_combo(f, "Template", v, list(pl.TEMPLATES), 34, style="PanelMuted.TLabel").pack(fill="x")

        def go():
            self.add_template(v.get())
            win.destroy()
        ttk.Button(f, text="Add chapters", style="Accent.TButton", command=go).pack(anchor="w", pady=(10, 0))

    def add_template(self, name):
        base = self.app.store.count("chapter")
        for i, (title, words) in enumerate(pl.TEMPLATES[name], 1):
            self.app.store.insert("chapter", position=base + i, title=title, target=words)
        self.refresh()


class Log(ttk.Frame):
    title = "Writing log"

    def __init__(self, parent, app):
        super().__init__(parent)
        self.view = ak.EntityView(self, app, "session")
        self.view.pack(fill="both", expand=True)
        self.refresh, self.commit = self.view.refresh, self.view.commit


class Meetings(ttk.Frame):
    title = "Supervisor meetings"

    def __init__(self, parent, app):
        super().__init__(parent)
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True)
        self.meetings = ak.EntityView(nb, app, "meeting")
        self.actions = ak.EntityView(nb, app, "action")
        nb.add(self.meetings, text="Meetings")
        nb.add(self.actions, text="Actions")

    def refresh(self):
        self.meetings.refresh()
        self.actions.refresh()

    def commit(self):
        return self.meetings.commit() and self.actions.commit()


class Plan(ttk.Frame):
    title = "Plan"

    def __init__(self, parent, app):
        super().__init__(parent)
        self.app = app
        top = ttk.Frame(self)
        top.pack(fill="x")
        self.deadline, self.start, self.per_week = tk.StringVar(), tk.StringVar(), tk.StringVar()
        ak.labeled_entry(top, "Submission date (YYYY-MM-DD)", self.deadline, 22).pack(side="left", padx=(0, 8))
        ak.labeled_entry(top, "Writing began", self.start, 14).pack(side="left", padx=(0, 8))
        ak.labeled_entry(top, "Writing days a week", self.per_week, 10).pack(side="left", padx=(0, 8))
        ttk.Button(top, text="Save and build schedule", style="Accent.TButton", command=self.save).pack(side="left", anchor="s")
        ttk.Button(top, text="Export calendar", command=self.export).pack(side="right", anchor="s")
        self.info = ttk.Label(self, text="", style="Muted.TLabel")
        self.info.pack(anchor="w", pady=6)
        self.table = ak.Table(self, app, [("c", "Chapter", 30), ("s", "Start", 11), ("f", "Finish", 11), ("left", "Words left", 10), ("day", "Words a writing day", 18)])
        self.table.pack(fill="both", expand=True)

    def save(self):
        d, st = self.deadline.get().strip(), self.start.get().strip()
        for v in (d, st):
            if v and ak.parse_date(v) is None:
                messagebox.showerror("Plan", "Dates must be YYYY-MM-DD.", parent=self)
                return
        try:
            n = int(self.per_week.get() or 5)
        except ValueError:
            messagebox.showerror("Plan", "Writing days must be a number.", parent=self)
            return
        s = self.app.store
        s.set_setting("deadline", d)
        s.set_setting("start", st or ak.today())
        s.set_setting("per_week", max(1, min(7, n)))
        self.build()

    def build(self):
        s = self.app.store
        deadline, per_week = settings(s)
        ch = s.list("chapter")
        if not deadline or not ch or deadline <= ak.today():
            self.info.configure(text="Set a future submission date and add chapters to build a schedule.")
            self.table.fill([])
            return
        rows, free = pl.schedule(ch, ak.today(), deadline, per_week)
        self.info.configure(text="Writing ends on %s. The time after that is a buffer for final revisions and printing." % free)
        self.table.fill([[r["chapter"], r["start"], r["finish"], "{:,}".format(r["words_left"]), "%d" % r["per_day"]] for r in rows])

    def export(self):
        path = filedialog.asksaveasfilename(parent=self, defaultextension=".ics", initialfile="thesis-deadlines.ics")
        if path:
            with open(path, "w", encoding="utf-8", newline="") as fh:
                fh.write(pl.ics(settings(self.app.store)[0], self.app.store.list("chapter")))
            self.app.status("Calendar saved")

    def refresh(self):
        s = self.app.store
        self.deadline.set(s.get_setting("deadline"))
        self.start.set(s.get_setting("start"))
        self.per_week.set(s.get_setting("per_week", "5"))
        self.build()


class APP(ak.BaseApp):
    APP_NAME, ACCENT = "Thesis Planner", "#1e40af"
    SCHEMA, SAMPLE = SCHEMA, staticmethod(sample)
    VIEWS = [Overview, Chapters, Log, Meetings, Plan, ak.DataView]


def main(argv=None):
    return ak.main(APP, argv)
