"""Planning arithmetic: progress, pace, projections, schedules, and word counts from Word and text files."""
import datetime
import re
import zipfile
from xml.etree import ElementTree

STATUS = ["Not started", "Outlining", "First draft", "Revising", "With supervisor", "Final"]
STAGE_WEIGHT = {"Not started": 0.0, "Outlining": 0.1, "First draft": 0.5, "Revising": 0.75, "With supervisor": 0.9, "Final": 1.0}
TEMPLATES = {
    "Standard five-chapter thesis": [("Introduction", 8000), ("Literature review", 18000), ("Methodology", 12000), ("Results", 18000),
                                     ("Discussion and conclusion", 14000)],
    "Thesis by publication": [("Introduction", 8000), ("Paper 1", 9000), ("Paper 2", 9000), ("Paper 3", 9000), ("Integrative discussion", 10000)],
    "Humanities monograph": [("Introduction", 10000), ("Chapter 1", 15000), ("Chapter 2", 15000), ("Chapter 3", 15000), ("Chapter 4", 15000), ("Conclusion", 8000)],
    "Masters dissertation": [("Introduction", 2000), ("Literature review", 5000), ("Methods", 3000), ("Findings", 5000), ("Discussion", 3500), ("Conclusion", 1500)],
}


def d(text):
    return datetime.date.fromisoformat(text)


def days_between(a, b):
    return (d(b) - d(a)).days


def add_days(day, n):
    return (d(day) + datetime.timedelta(days=n)).isoformat()


def progress(chapters):
    """Totals over chapters. 'stage' weighs each chapter by how finished it is, as well as how long."""
    target = sum(c["target"] or 0 for c in chapters)
    words = sum(c["words"] or 0 for c in chapters)
    capped = sum(min(c["words"] or 0, c["target"] or 0) for c in chapters)
    stage = sum((c["target"] or 0) * STAGE_WEIGHT.get(c["status"], 0) for c in chapters)
    return {"target": target, "words": words, "left": max(0, target - capped), "fraction": capped / target if target else 0.0,
            "stage": stage / target if target else 0.0}


def working_days(start, end, per_week=5):
    """Writing days from start to end inclusive: Monday onwards, per_week days each week."""
    per_week = max(1, min(7, per_week))
    count = 0
    cur = d(start)
    stop = d(end)
    while cur <= stop:
        if cur.weekday() < per_week:
            count += 1
        cur += datetime.timedelta(days=1)
    return count


def recent_pace(sessions, today, window=28):
    """Words per calendar day over the window, from the writing log."""
    since = add_days(today, -(window - 1))
    return sum(s["words"] or 0 for s in sessions if since <= s["day"] <= today) / float(window)


def required_pace(words_left, today, deadline, per_week=5):
    """Words per writing day needed to reach the deadline, or None if it has passed."""
    if days_between(today, deadline) < 0:
        return None
    return words_left / max(1, working_days(today, deadline, per_week))


def projected_finish(words_left, pace, today):
    """Date at the current pace, or None when there is no pace yet."""
    if words_left <= 0:
        return today
    if pace <= 0:
        return None
    days = int(words_left / pace + 0.999)
    return add_days(today, days) if days < 36500 else None


def status_line(chapters, sessions, today, deadline, per_week=5):
    p = progress(chapters)
    pace = recent_pace(sessions, today)
    finish = projected_finish(p["left"], pace, today)
    late = None
    if finish and deadline:
        late = days_between(deadline, finish)
    return {"progress": p, "pace": pace, "finish": finish, "days_late": late,
            "needed": required_pace(p["left"], today, deadline, per_week) if deadline else None}


def burndown(chapters, sessions, start, deadline, today):
    """Series for the chart: actual words left, by day, reconstructed from the log, and the ideal straight line."""
    total = sum(c["target"] or 0 for c in chapters)
    logged = sum(s["words"] or 0 for s in sessions)
    now = sum(c["words"] or 0 for c in chapters)
    baseline = max(0, now - logged)                     # words that existed before logging began
    by_day = {}
    for s in sessions:
        by_day[s["day"]] = by_day.get(s["day"], 0) + (s["words"] or 0)
    actual, cum = [], baseline
    span = max(0, days_between(start, today))
    for i in range(span + 1):
        day = add_days(start, i)
        cum += by_day.get(day, 0)
        actual.append((i, max(0, total - cum)))
    length = max(1, days_between(start, deadline)) if deadline else max(1, span)
    ideal = [(0, total), (length, 0)]
    return {"actual": actual, "ideal": ideal, "length": length, "total": total}


def schedule(chapters, today, deadline, per_week=5, buffer_share=0.15):
    """Share the writing days among unfinished chapters in proportion to their remaining work. The last share of the
    time is left free as a buffer for final revisions."""
    todo = [c for c in sorted(chapters, key=lambda c: c.get("position") or 0) if c["status"] != "Final"]
    weights = [max(50, (c["target"] or 0) * (1 - STAGE_WEIGHT.get(c["status"], 0))) for c in todo]
    total = sum(weights)
    span = max(1, days_between(today, deadline))
    usable = max(1, int(span * (1 - buffer_share)))
    out, used = [], 0.0
    for c, w in zip(todo, weights):
        begin = add_days(today, int(used))
        used += usable * w / total
        finish = add_days(today, max(int(used), int(used - usable * w / total) + 1))
        left = max(0, (c["target"] or 0) - (c["words"] or 0))
        out.append({"chapter": c["title"], "start": begin, "finish": finish, "words_left": left,
                    "per_day": left / max(1, working_days(begin, finish, per_week))})
    return out, add_days(today, usable)


def risks(chapters, sessions, meetings, actions, today, deadline, per_week=5):
    """Sentences about what could go wrong, most serious first."""
    out = []
    st = status_line(chapters, sessions, today, deadline, per_week)
    if deadline and days_between(today, deadline) < 0:
        out.append(("danger", "The submission date has passed."))
    elif st["days_late"] is not None and st["days_late"] > 0:
        out.append(("danger", "At your recent pace you would finish %d days late." % st["days_late"]))
    elif st["finish"] is None and st["progress"]["left"] > 0:
        out.append(("warning", "No words logged in the last four weeks, so no finish date can be projected."))
    if st["needed"] is not None and st["needed"] > 1500:
        out.append(("warning", "You would need %d words every writing day. Consider moving the date or cutting scope." % st["needed"]))
    for c in chapters:
        if c.get("due") and c["status"] != "Final" and c["due"] < today:
            out.append(("warning", "%s was due on %s." % (c["title"], c["due"])))
        if (c["words"] or 0) > 1.15 * (c["target"] or 0) > 0:
            out.append(("info", "%s is %d%% over its target." % (c["title"], 100 * (c["words"] / c["target"] - 1))))
    for a in actions:
        if not a["done"] and a.get("due") and a["due"] < today:
            out.append(("warning", "Overdue action: %s" % a["text"]))
    if meetings:
        last = max(m["day"] for m in meetings)
        if days_between(last, today) > 42:
            out.append(("info", "Your last supervisor meeting was %d days ago." % days_between(last, today)))
    elif chapters:
        out.append(("info", "No supervisor meetings are recorded yet."))
    order = {"danger": 0, "warning": 1, "info": 2}
    return sorted(out, key=lambda r: order[r[0]])


def streak(sessions, today):
    days = {s["day"] for s in sessions if (s["words"] or 0) > 0}
    cur = d(today) if today in days else d(today) - datetime.timedelta(days=1)
    n = 0
    while cur.isoformat() in days:
        n += 1
        cur -= datetime.timedelta(days=1)
    return n


def count_words(text):
    return len(re.findall(r"[^\W\d_][\w'’-]*|\d[\d.,]*", text))


def read_text(path):
    """Plain text from .docx, .tex, .md or .txt."""
    low = path.lower()
    if low.endswith(".docx"):
        with zipfile.ZipFile(path) as z:
            root = ElementTree.fromstring(z.read("word/document.xml"))
        ns = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
        paras = []
        for p in root.iter(ns + "p"):
            paras.append("".join(t.text or "" for t in p.iter(ns + "t")))
        return "\n".join(paras)
    with open(path, encoding="utf-8", errors="replace") as fh:
        text = fh.read()
    if low.endswith(".tex"):
        text = re.sub(r"(?<!\\)%.*", "", text)
        text = re.sub(r"\\begin\{(figure|table|equation)\*?\}.*?\\end\{\1\*?\}", " ", text, flags=re.S)
        text = re.sub(r"\\[a-zA-Z]+\*?(\[[^\]]*\])?(\{[^{}]*\})?", " ", text)
    return text


def words_in_file(path):
    return count_words(read_text(path))


def ics(deadline, chapters):
    rows = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Thesis Planner//EN"]
    items = [(c["due"], c["title"]) for c in chapters if c.get("due")]
    if deadline:
        items.append((deadline, "Thesis submission"))
    for day, title in items:
        rows += ["BEGIN:VEVENT", "UID:%s-%s@thesis-planner" % (day, abs(hash(title)) % 10 ** 6), "DTSTAMP:%sT000000Z" % day.replace("-", ""),
                 "DTSTART;VALUE=DATE:%s" % day.replace("-", ""), "SUMMARY:%s" % title.replace(",", "\\,"), "END:VEVENT"]
    return "\r\n".join(rows + ["END:VCALENDAR"]) + "\r\n"
