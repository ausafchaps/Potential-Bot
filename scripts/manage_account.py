"""Manage existing account credentials and roles from a trusted server terminal."""

import argparse
import getpass

from app.db.session import SessionLocal
from app.models import AuthSession, User
from app.services.auth import hash_password
from sqlalchemy import delete, select


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", required=True)
    parser.add_argument("--set-password", action="store_true")
    roles = parser.add_mutually_exclusive_group()
    roles.add_argument("--admin", action="store_true")
    roles.add_argument("--remove-admin", action="store_true")
    parser.add_argument("--revoke-sessions", action="store_true")
    args = parser.parse_args()
    if not any([args.set_password, args.admin, args.remove_admin, args.revoke_sessions]):
        parser.error("Specify a password, role, or session update")

    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == args.email.strip().lower()))
        if user is None:
            parser.error("Account was not found")
        if args.set_password:
            password = getpass.getpass("New password (12-128 characters): ")
            if not 12 <= len(password) <= 128:
                parser.error("Password must contain 12-128 characters")
            if password != getpass.getpass("Confirm password: "):
                parser.error("Passwords do not match")
            user.password_hash = hash_password(password)
        if args.admin or args.remove_admin:
            user.is_admin = args.admin
        if args.set_password or args.revoke_sessions:
            db.execute(delete(AuthSession).where(AuthSession.user_id == user.id))
        db.commit()
        print(f"Updated account: {user.email}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
