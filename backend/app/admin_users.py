"""Manage admin accounts from the command line (run inside backend/).

    python -m app.admin_users create you@example.com --role owner
    python -m app.admin_users list
    python -m app.admin_users reset-password you@example.com
    python -m app.admin_users disable staff@example.com
    python -m app.admin_users enable staff@example.com

Passwords are typed at a hidden prompt, never passed on the command line
(so they don't end up in shell history).
"""

import argparse
import getpass
import os
import sys

from sqlalchemy import inspect, select

from .db import SessionLocal, engine
from .models import AdminUser
from .services import auth


def _ask_password(attempts: int = 3) -> str:
    # ADMIN_PASSWORD is only for automated tests/scripts; people use the prompt.
    env = os.environ.get("ADMIN_PASSWORD")
    if env:
        return env
    print("(Nothing is shown while you type the password - that's normal.)")
    for _ in range(attempts):
        first = getpass.getpass(f"New password (at least {auth.MIN_PASSWORD_LENGTH} characters): ")
        if len(first) < auth.MIN_PASSWORD_LENGTH:
            print(f"Too short: that was {len(first)} characters. Please use at least "
                  f"{auth.MIN_PASSWORD_LENGTH} (a short phrase works well, e.g. 'blue desk lamp 2026').")
            continue
        if first != getpass.getpass("Repeat password: "):
            print("The two passwords didn't match. Please try again.")
            continue
        return first
    sys.exit("No password set. Nothing was changed.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.admin_users", description="Manage admin accounts.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("create", help="create an admin")
    c.add_argument("email")
    c.add_argument("--role", choices=auth.ROLES, default="staff",
                   help="owner = everything; staff = orders only (default: staff)")
    sub.add_parser("list", help="list admins")
    for name in ("reset-password", "disable", "enable"):
        sub.add_parser(name).add_argument("email")
    args = parser.parse_args(argv)

    if not inspect(engine).has_table("admin_users"):
        sys.exit("Database is not up to date. Run `alembic upgrade head` first.")

    with SessionLocal() as db:
        try:
            if args.cmd == "create":
                # Check the email before asking for a password, so a typo doesn't waste the prompt.
                if "@" not in args.email or "." not in args.email.split("@")[-1]:
                    sys.exit(f"Error: '{args.email}' is not an email address. Example: "
                             "admin-user.cmd create name@yourdomain.com --role owner")
                user = auth.create_user(db, args.email, _ask_password(), args.role)
                print(f"Created {user.role} {user.email}")
            elif args.cmd == "list":
                users = db.scalars(select(AdminUser).order_by(AdminUser.email)).all()
                if not users:
                    print("No admin accounts yet. Create one with: python -m app.admin_users create EMAIL --role owner")
                for u in users:
                    print(f"{u.email:40} {u.role:6} {'active' if u.active else 'DISABLED'}")
            elif args.cmd == "reset-password":
                auth.set_password(db, args.email, _ask_password())
                print(f"Password changed for {auth.normalise_email(args.email)}; their sessions were signed out.")
            elif args.cmd in ("disable", "enable"):
                auth.set_active(db, args.email, args.cmd == "enable")
                print(f"{auth.normalise_email(args.email)} {args.cmd}d.")
        except auth.AuthError as exc:
            sys.exit(f"Error: {exc}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
