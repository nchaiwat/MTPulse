"""Run on the server console: python -m app.bootstrap_admin USERNAME."""

import argparse
from getpass import getpass

from app.database import SessionLocal
from app.services.local_auth import bootstrap


def main():
    parser = argparse.ArgumentParser(description="Create/reset emergency MT Pulse Local Admin")
    parser.add_argument("username")
    parser.add_argument("--reset-password", action="store_true")
    args = parser.parse_args()
    password = getpass("New password (12-256 characters): ")
    if password != getpass("Confirm password: "):
        raise SystemExit("Passwords do not match")
    with SessionLocal() as session:
        try:
            bootstrap(session, args.username, password, reset=args.reset_password)
        except ValueError as exc:
            raise SystemExit(str(exc)) from exc
    print("Local administrator saved; previous sessions revoked.")


if __name__ == "__main__":
    main()
