"""Runs automation jobs in the background while the backend is running.

A single daemon thread wakes every minute and runs whatever is due. Jobs
never crash the shop: failures are recorded in automation_runs and shown in
Admin > Automation. Set AUTOMATION_ENABLED=false in backend/.env to turn off
the schedule (you can still run jobs by hand with automation.cmd).
"""

import logging
import threading

from .db import SessionLocal
from .services import automation

log = logging.getLogger("novahaus.automation")
_stop = threading.Event()
_thread: threading.Thread | None = None
TICK_SECONDS = 60


def _loop() -> None:
    while not _stop.is_set():
        try:
            with SessionLocal() as db:
                for run in automation.run_due_jobs(db):
                    log.info("automation %s: %s %s", run.job, run.status, run.message)
        except Exception:  # database briefly unavailable etc.: try again next tick
            log.exception("automation tick failed")
        _stop.wait(TICK_SECONDS)


def start() -> None:
    global _thread
    if _thread and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="novahaus-automation", daemon=True)
    _thread.start()


def stop() -> None:
    _stop.set()
