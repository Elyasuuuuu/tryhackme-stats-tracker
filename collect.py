#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys

from db import history, latest_snapshot, save_snapshot
from discord_notify import send_discord_webhook
from display import format_terminal
from env import load_env, load_settings
from thm_client import THMClient, save_storage_state_interactive

load_env()


def print_summary(data: dict) -> None:
    print(format_terminal(data))


def cmd_collect(args: argparse.Namespace) -> int:
    settings = load_settings()
    client = THMClient(
        username=settings.username,
        country=settings.country,
        headless=not args.show_browser,
    )
    result = client.collect()
    payload = result.to_dict()
    snapshot_id = save_snapshot(settings.username, payload)
    print_summary(payload)
    print(f"\nSnapshot #{snapshot_id} saved.")

    if not getattr(args, "no_discord", False):
        if not settings.discord_webhook_url:
            print("\nDiscord: skipped (DISCORD_WEBHOOK_URL not set in .env)")
        else:
            discord_err = send_discord_webhook(payload)
            if discord_err:
                print(f"\nDiscord: failed — {discord_err}")
            else:
                print("\nDiscord: notification sent.")

    return 0 if not payload.get("errors") or payload.get("leaderboard_monthly") else 1


def cmd_latest(args: argparse.Namespace) -> int:
    settings = load_settings()
    snap = latest_snapshot(settings.username)
    if not snap:
        print("No snapshots yet. Run: python collect.py")
        return 1
    print(f"Latest snapshot: {snap['collected_at']}")
    print_summary(snap["data"])
    return 0


def cmd_login(_args: argparse.Namespace) -> int:
    save_storage_state_interactive()
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    settings = load_settings()
    rows = history(settings.username, limit=args.limit)
    if not rows:
        print("History is empty.")
        return 1
    print(f"{'Date':<28} {'Board':>8} {'Weekly':>8} {'Pts/wk':>8} {'Lvl':>4}")
    print("-" * 62)
    for row in rows:
        data = row["data"]
        lb = (data.get("leaderboard_monthly") or {}).get("user") or {}
        league = data.get("league") or {}
        profile = data.get("profile") or {}
        print(
            f"{row['collected_at'][:19]:<28} "
            f"{('#' + str(lb.get('rank'))) if lb.get('rank') else 'n/a':>8} "
            f"{('#' + str(league.get('rank'))) if league.get('rank') else 'n/a':>8} "
            f"{str(league.get('weekly_points') or '-'):>8} "
            f"{str(profile.get('level') or '-'):>4}"
        )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="TryHackMe stats collector")
    sub = parser.add_subparsers(dest="command")

    p_collect = sub.add_parser("collect", help="Collect and save stats")
    p_collect.add_argument("--show-browser", action="store_true")
    p_collect.add_argument(
        "--no-discord", action="store_true", help="Do not send the Discord webhook"
    )
    p_collect.set_defaults(func=cmd_collect, no_discord=False, show_browser=False)

    p_login = sub.add_parser("login", help="Interactive login → session in .env")
    p_login.set_defaults(func=cmd_login)

    p_latest = sub.add_parser("latest", help="Show the latest snapshot")
    p_latest.set_defaults(func=cmd_latest)

    p_hist = sub.add_parser("history", help="Snapshot history")
    p_hist.add_argument("--limit", type=int, default=15)
    p_hist.set_defaults(func=cmd_history)

    args = parser.parse_args()
    if not args.command:
        args.command = "collect"
        args.func = cmd_collect
        args.show_browser = False
        args.no_discord = False
        args.limit = 15
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
