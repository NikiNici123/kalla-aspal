# AGENTS.md — Working Conventions for This Project

This file is for any AI coding agent (Claude or otherwise) picking up **Kalla Aspal / LPSE Monitor** cold. It's the distilled result of many actual working sessions with Nikol — read it before touching anything non-trivial.

**Read order for a fresh session:** `PRD.md` (what this is for) → `TRD.md` (how it's actually built) → this file (how to work on it) → `PROJECT_STATUS.md` (detailed recent history). All four now live inside `src/`, alongside the rest of the app's code — see rule 16 below before assuming a path. If you're a Claude session with access to the "Kalla Aspal" claude.ai project, also check `devices-and-workflow.md` there — it covers the two physical devices, sync model, and deployment notes, and isn't duplicated in the repo.

---

## 1. Don't "fix" the architecture toward the ideal

`TRD.md` describes the real, flat, single-file-heavy structure this app actually has — not an aspirational deeper one. If you notice `app.py` is one big file, or `database.py` isn't split into a repository pattern, that is not a bug to fix. Restructuring working code to match a document's "ideal" shape, without being asked, is exactly the kind of change that burns a session's trust. See `TRD.md` Section 4's "when to split further" rule before ever proposing a structural refactor.

## 2. The two datasets stay separate, always

"Daftar Lengkap" (`/lelang`) and "Ringkasan Beranda" (homepage summary, has Akhir Pendaftaran deadlines) are intentionally separate all the way down: different scraper modules, different DB tables, different services, different UI tabs, different Excel exports. Never merge them "to reduce duplication" — the duplication is deliberate, because they're genuinely different data with different guarantees (only one has a deadline date). If asked to add a feature to one, check whether the other needs the mirrored version too, but keep the implementations as separate, parallel modules.

## 3. Two devices, git-only sync

Nikol works from (at least) two machines — a home device (`D:\Github Repository\kalla-aspal`, primary, most history built here) and a second one (`E:\Project Kaizen`). Only one can be linked to a Claude session at a time via the device bridge. There is no automatic file sync — git is the only thing moving code between them, and `data/*.db` / Excel workbooks are gitignored per-device by design. Never assume state on a device you're not currently linked to; if something seems out of date, it's probably just the other machine.

## 4. Never handle raw git credentials

Standing restriction, not a one-off: never attempt to read, write, or pass raw credential material (PATs, passwords) via Bash, the device bridge, or a git-credential-file. This is specifically about handling raw secrets directly — it does **not** block using already-authenticated tools like GitHub Desktop's own credential helper, or running ordinary `git` commands through it.

## 5. Never commit or push on Nikol's behalf

Deliver changed files (see workflow below), but leave `git add` / `git commit` / `git push` to Nikol, via GitHub Desktop or `push_to_github.bat`, unless she explicitly asks you to do it. This has held across many sessions — files have sat uncommitted on purpose while she reviews them first.

## 6. The delivery workflow for a changed file

1. Edit the file in the sandbox/scratchpad.
2. `python3 -m py_compile <file>` — there's no live Streamlit runtime available to actually run the app, so this is the real verification step. Say so plainly; don't imply the app was actually run if it wasn't.
3. `SendUserFile` the updated file.
4. `device_commit_files` it back to its original path on the connected device (same folder it came from — check `get_device_info`'s `connectedFolders` first, don't guess a path).
5. Tell Nikol plainly what changed and that it's saved-but-not-committed.

## 7. pytest can't run in the cloud sandbox

No PyPI network access there. For pure-logic modules (the `services/` files are all designed to be testable without Streamlit), verify changes with a short manual `python3 -c` assertion script instead of pretending `pytest` ran. Say clearly which verification method was actually used.

## 8. Language split: Indonesian UI, English code

All user-facing Streamlit copy (labels, captions, button text, error messages) is Indonesian. All code, comments, and docstrings are English. Keep this split consistent in anything new.

## 9. Match the established "small icon / popover" UI pattern

Recent UI work converged on a specific house style for tucking secondary detail out of the main flow: a small icon-labeled `st.popover()` (the "Status per Wilayah" bell, the deadline calendar icon), rather than an always-visible block or a `st.expander`. If a new feature needs to show detail without cluttering the main view, follow this pattern rather than inventing a new one. Check `ui/style.css`'s existing `.st-key-*` scoped classes before writing new inline `<style>` blocks — most spacing/sizing needs are already solved there.

## 10. `web-prototype/` stays untouched

It's an unused scaffold, noted in `devices-and-workflow.md`. Don't build it out, add to it, or reference it unless Nikol explicitly asks.

## 11. `.exe` packaging is optional, not primary

`launcher.py` / `lpse_monitor.spec` / `build_exe.bat` exist from an earlier "would a standalone .exe be reasonable?" discussion — the answer was "sure, but not necessary." `run_app.bat` (double-click, auto-bootstraps Python/dependencies if missing) is the actual primary way this app gets run day to day. Don't assume the `.exe` path is how anyone is actually launching this unless told otherwise.

## 12. Confirm before big changes; Nikol directs casually

Requests often arrive as a screenshot plus a stream-of-consciousness message mixing English and Indonesian, sometimes across several turns before landing on the actual ask. That's the normal working style here, not something to "clean up" — but it does mean: when a request's *scope* is ambiguous (does "make it cleaner" mean this one screen, or a full redesign?), do the part that's clearly asked for, and either ask or flag your interpretation plainly rather than guessing big. `TRD.md` Section 44's rule 11 ("explain architectural changes before implementing them") applies especially here.

## 13. `PROJECT_STATUS.md` is the one changelog

Append significant changes there. Don't create a `CHANGELOG.md` — see `TRD.md` Section 43.

## 14. Keep scope disciplined

As of this writing, the explicitly committed scope is: **SPSE package auto-scraper + deadline reminders.** Nikol has deliberately kept the following as *future*, *deferred*, or *discussed-but-declined-for-now* — don't build toward them proactively even if they'd be natural extensions:

* Online/cloud deployment, authentication, multi-user access
* A real cloud database
* External notification channels (email, Telegram, WhatsApp)
* Auto-populating Kalla's internal Odoo CRM (discussed as a theoretical "could this work" question — Odoo does have a safe scoped-API-key path for it, but nothing has been built, and it would need real organizational buy-in first, not just a technical green light)

If a request seems to want to reopen one of these, that's worth flagging explicitly rather than quietly building a first version.

## 15. When in doubt about what's real, check the code

This file and `TRD.md` describe the state of things as of when they were written. Documents drift; code doesn't lie. If something here seems to contradict what you actually find in the repo, trust the repo, fix your understanding, and — if the drift is significant — flag it back to Nikol the way `TRD.md` itself was reconciled against reality once already.

## 16. Two-tier folder layout: root vs. `src/`

As of the 2026-09-22 reorganization, the repo root only holds four things Nikol touches directly: `run_app.bat`, `push_to_github.bat`, her `.xlsx` workbook, and `.gitignore` (plus `.git/`). Every actual file this document set describes — `app.py`, `database/`, `scraper/`, `services/`, `ui/`, `config/`, `data/`, `backups/`, `logs/`, `tests/`, this file, `PRD.md`, `TRD.md`, `PROJECT_STATUS.md`, `README.md`, and the packaging/reminder scripts — lives one folder deeper, inside `src/`. See `TRD.md` Section 29 for the full tree and the reasoning.

The short version: everything inside `src/` resolves its own paths relative to itself (`Path(__file__).resolve().parent...` in Python, `%~dp0` in `.bat` files), so the move needed zero code changes for almost everything. The only two things that had to change were the ones reaching *across* the `src/` boundary — `run_app.bat` (now `cd`s into `src/` before running anything) and `services/excel_service.py`'s file-discovery default (must scan the true repo root, not `src/`, or it stops finding Nikol's workbook next to `run_app.bat` — see its `REPO_ROOT` vs `PROJECT_ROOT` distinction). If you're asked to touch a path, check which side of that boundary it's actually on before assuming.
