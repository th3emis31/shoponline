"""Run the shop's automation by hand (run inside backend/).

    python -m app.automation_cli status          show jobs, limits, last runs
    python -m app.automation_cli run             run every job now
    python -m app.automation_cli run low_stock   run one job now
    python -m app.automation_cli report          print the latest daily report

Windows: automation.cmd status | run [job] | report
"""

import argparse
import sys

from sqlalchemy import inspect, select

from .db import SessionLocal, engine
from .models import DailyReport
from .services import automation


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="automation", description="Run NOVAHAUS automation by hand.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status", help="show jobs and limits")
    r = sub.add_parser("run", help="run all jobs, or one job")
    r.add_argument("job", nargs="?", choices=list(automation.JOBS))
    sub.add_parser("report", help="print the latest daily report")
    args = ap.parse_args(argv)

    if not inspect(engine).has_table("automation_runs"):
        sys.exit("Database is not up to date. Run run-local.cmd (or `alembic upgrade head`) first.")

    with SessionLocal() as db:
        if args.cmd == "status":
            st = automation.status(db)
            lim = st["limits"]
            print(f"Automatic schedule: {'ON' if st['enabled'] else 'OFF'} (runs while the shop is running)")
            print(f"Limits: reorders up to GBP {lim['auto_reorder_max'] / 100:.2f} each and "
                  f"GBP {lim['auto_reorder_weekly_max'] / 100:.2f} per week; price rises up to "
                  f"{lim['auto_price_max_pct']:g}%; minimum margin {lim['min_contribution_margin']:.0%}")
            for j in st["jobs"]:
                last = f"{j['last_run']:%Y-%m-%d %H:%M} {j['last_status']}: {j['last_message']}" if j["last_run"] else "never run"
                print(f"- {j['job']:<27} {j['schedule']:<22} {last}")
        elif args.cmd == "run":
            jobs = [args.job] if args.job else list(automation.JOBS)
            failed = False
            for job in jobs:
                run = automation.run_job(db, job)
                print(f"{job}: {run.status} - {run.message}")
                failed |= run.status == "error"
            return 1 if failed else 0
        elif args.cmd == "report":
            rep = db.scalar(select(DailyReport).order_by(DailyReport.day.desc()).limit(1))
            print(rep.content if rep else "No report yet. Create one with: automation.cmd run daily_report")
    return 0


if __name__ == "__main__":
    sys.exit(main())
