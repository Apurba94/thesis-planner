# Thesis Planner

A thesis is too big to manage by feel. This program turns yours into numbers you can act on: how far along you are, how
many words a day you need, and when you will finish at your current pace.

* **Chapters** with word targets and stages, from templates for a standard five-chapter thesis, thesis by publication,
  humanities monograph or masters dissertation.
* **Word counts from your files:** read `.docx`, `.tex`, `.md` or `.txt` drafts directly, and log the gain automatically.
* **Burndown chart** of words left against the ideal line, with a projected finish date from your recent pace.
* **Writing schedule:** shares the remaining time among chapters by the work left, and keeps a buffer for final revisions.
* **Attention list:** finishing late, an unrealistic daily target, overdue chapters and actions, and no recent meeting.
* **Supervisor meetings** with decisions and action items.
* **Calendar export** of deadlines as an `.ics` file.

`--demo` opens a temporary database with a fictional thesis.

## Download

Windows: get the `.exe` from [Releases](https://github.com/Apurba94/thesis-planner/releases/latest) and double-click it. No installation or Python is needed.
Windows may show a SmartScreen warning the first time because the program is not code-signed: choose *More info*, then *Run anyway*.

## From source

```bash
python -m thesis_planner
python -m unittest discover -s tests -t .
python build_exe.py
```

## Limits

Word counts are close to Word's but may differ slightly, and LaTeX is counted after stripping commands. Projections assume
your recent pace continues: they are planning aids, not promises. Words are one measure of a thesis, and thinking time does
not show up in them.

## License

MIT
