"""Small command-line management utility for the leaderboard."""

from __future__ import annotations

import argparse
import os
from pathlib import Path

if "DATABASE_PATH" not in os.environ and Path("/var/lib/yex-lol").is_dir():
    os.environ["DATABASE_PATH"] = "/var/lib/yex-lol/yex.db"
    os.environ.setdefault("SEED_DEMO_DATA", "0")

from app import db_session


def list_projects() -> None:
    with db_session() as db:
        rows = db.execute(
            """
            SELECT slug, name, status, is_demo, total_bid_cents, clicks, created_at
            FROM projects ORDER BY is_demo ASC, total_bid_cents DESC
            """
        ).fetchall()
    if not rows:
        print("No projects.")
        return
    for row in rows:
        kind = "demo" if row["is_demo"] else "live"
        print(
            f"{row['slug']:<28} {row['status']:<7} {kind:<5} "
            f"${row['total_bid_cents'] / 100:>7.2f} {row['clicks']:>5} clicks  "
            f"{row['name']}"
        )


def set_status(slug: str, status: str) -> None:
    with db_session() as db:
        cursor = db.execute("UPDATE projects SET status = ? WHERE slug = ?", (status, slug))
    if cursor.rowcount != 1:
        raise SystemExit(f"Unknown project: {slug}")
    print(f"{slug}: {status}")


def stats() -> None:
    with db_session() as db:
        row = db.execute(
            """
            SELECT
                SUM(CASE WHEN is_demo = 0 AND status = 'live' THEN 1 ELSE 0 END) AS live_projects,
                COALESCE(SUM(CASE WHEN is_demo = 0 THEN total_bid_cents ELSE 0 END), 0) AS revenue_cents,
                COALESCE(SUM(CASE WHEN is_demo = 0 THEN clicks ELSE 0 END), 0) AS clicks
            FROM projects
            """
        ).fetchone()
    print(f"Live projects: {row['live_projects'] or 0}")
    print(f"Recorded payments: ${row['revenue_cents'] / 100:.2f}")
    print(f"Outbound clicks: {row['clicks']}")


parser = argparse.ArgumentParser(description="Manage the leaderboard database.")
sub = parser.add_subparsers(dest="command", required=True)
sub.add_parser("list")
sub.add_parser("stats")
for name in ("hide", "show"):
    command = sub.add_parser(name)
    command.add_argument("slug")

args = parser.parse_args()
if args.command == "list":
    list_projects()
elif args.command == "stats":
    stats()
elif args.command == "hide":
    set_status(args.slug, "hidden")
elif args.command == "show":
    set_status(args.slug, "live")
