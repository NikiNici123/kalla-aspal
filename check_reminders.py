"""
Fires a native Windows notification when a saved, relevant package
(Ringkasan Beranda dataset) has its Akhir Pendaftaran (registration
deadline) coming up soon.

WHY THIS IS A SEPARATE FILE FROM app.py: Streamlit only runs code while
someone has the app open in a browser tab. A reminder that only fires
while you're already looking at the app isn't much of a reminder. This
script runs on its own, on a schedule - once per line in
config/reminder_times.txt (default 08:00 / 13:00 / 16:00) - via Windows
Task Scheduler (see setup_reminders.bat, which reads that file and
registers the schedule for you; run that once, not this file directly,
unless you're testing).

It only READS the database app.py already maintains - it never scrapes
LPSE itself, so a reminder is only ever as fresh as the last time someone
ran a check inside the app. No email, no account, nothing leaves this PC:
just a plain Windows notification, the same mechanism Outlook or Teams
already uses on your machine.

ACKNOWLEDGING A REMINDER: clicking the notification (its body or its
button) marks TODAY as acknowledged (services/reminder_service.py writes
today's date into logs/reminder_ack.txt), so any later scheduled check
the same day stays silent instead of nagging again - e.g. click the 13:00
one and the 16:00 one won't fire. This resets on its own the next day.
It's deliberately a simple per-day flag, not per-package - see
reminder_service.py's docstring for that trade-off.

HONEST NOTE - read this before assuming it "just works": this has not
been tested on a real Windows machine yet. Two specific things are
genuinely uncertain until tried for real: (1) whether toast()'s return
value reliably tells us a button/body click happened vs. a plain
dismiss/timeout - see _was_acknowledged() below for the (deliberately
lenient) guess this makes, and (2) whether a click still registers once
this script's own wait window has passed and the process has exited -
it most likely does NOT, since nothing is left running to catch it, which
in practice means "acknowledge" only works if you click within
ACK_WAIT_SECONDS of the notification appearing. If it behaves
differently on your machine, tell me what you see in
logs\\reminder.log and we'll adjust the matching logic.

To test by hand instead of waiting for the schedule:
    venv\\Scripts\\python check_reminders.py
"""

from __future__ import annotations

import sys
import threading
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

# ---------------------------------------------------------------------------
# The two settings you're likely to want to change.
# ---------------------------------------------------------------------------
REMINDER_DAYS_BEFORE = 3  # warn starting this many days before the deadline

# How many seconds to wait for you to click the notification (or its
# button) before giving up and treating this run as "shown but not
# acknowledged". Keep this reasonably short - it's how long this
# background check sits waiting before it can exit. Doesn't affect how
# long the notification is VISIBLE on screen (that's Windows' own
# behavior) - only how long this script listens for a click on it.
ACK_WAIT_SECONDS = 120

# The 3 (or however many) times of day this actually runs are set in
# config/reminder_times.txt, not here - edit that file, then re-run
# setup_reminders.bat to apply it.
# ---------------------------------------------------------------------------

from database import database as db  # noqa: E402
from services import reminder_service  # noqa: E402

LOG_FILE = BASE_DIR / "logs" / "reminder.log"
ACK_FILE = BASE_DIR / "logs" / "reminder_ack.txt"


def _log(message: str) -> None:
    LOG_FILE.parent.mkdir(exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat(timespec='seconds')}  {message}\n")


def _show_toast_and_wait(title: str, body: str, on_click_path: str, timeout: float):
    """Shows the notification with an explicit acknowledge button, in a
    background thread so a slow/never-clicked notification can't hang
    this script forever - waits up to `timeout` seconds for a result,
    then gives up and returns None (the daemon thread is abandoned; once
    this process exits, the notification most likely stops being
    clickable - see the module docstring's honest note)."""
    result_holder: dict = {}

    def _run():
        from win11toast import toast
        result_holder["result"] = toast(
            title,
            body,
            duration="long",
            on_click=on_click_path,
            button="Sudah Saya Cek",
        )

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=timeout)
    return result_holder.get("result")


def _was_acknowledged(result) -> bool:
    """Best-effort read of win11toast's return value: ANY sign of a real
    click (button or notification body) counts as "acknowledged" - not
    just our specific button - since the point is "did the admin notice
    this", not which exact element they clicked. A plain timeout/dismiss
    is expected to come back falsy or empty; this hasn't been confirmed
    against a real Windows machine, so it's deliberately lenient (a
    missed acknowledgment just means one extra reminder later today,
    which is a much smaller problem than the reverse)."""
    if not result:
        return False
    arguments = str(result.get("arguments", "")) if isinstance(result, dict) else str(result)
    return bool(arguments.strip())


def main() -> None:
    if reminder_service.is_acknowledged_today(ACK_FILE):
        _log("Sudah dikonfirmasi hari ini - jadwal ini dilewati.")
        return

    try:
        with db.connect() as conn:
            rows = db.get_relevant_homepage_packages(conn)
    except Exception as exc:
        _log(f"GAGAL membuka database: {exc}")
        return

    upcoming = reminder_service.get_upcoming_deadlines(rows, REMINDER_DAYS_BEFORE)
    if not upcoming:
        _log("Tidak ada deadline dalam window - tidak ada notifikasi.")
        return

    names = [row["nama_paket"] for _, row in upcoming]
    _log(f"{len(names)} paket dalam window: " + " | ".join(names))

    try:
        from win11toast import toast  # noqa: F401  (import check only)
    except ImportError:
        _log("GAGAL: paket win11toast belum terinstall. Jalankan setup_reminders.bat lagi.")
        return

    title = f"⏰ {len(names)} Tender Segera Ditutup Pendaftarannya"
    preview_lines = [f"- {n}" for n in names[:3]]
    if len(names) > 3:
        preview_lines.append(f"(+{len(names) - 3} lainnya)")
    body = "\n".join(preview_lines)

    try:
        result = _show_toast_and_wait(
            title, body, str(BASE_DIR / "run_app.bat"), timeout=ACK_WAIT_SECONDS
        )
    except Exception as exc:
        _log(f"GAGAL menampilkan notifikasi: {exc}")
        return

    if _was_acknowledged(result):
        reminder_service.mark_acknowledged(ACK_FILE)
        _log("Dikonfirmasi - jadwal berikutnya hari ini akan dilewati.")
    else:
        _log("Notifikasi ditampilkan (belum ada konfirmasi klik).")


if __name__ == "__main__":
    main()
