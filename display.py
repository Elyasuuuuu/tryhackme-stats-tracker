from __future__ import annotations

from env import get_catchup_board_max_days, get_catchup_weekly_max_days


def _fmt_num(n: int | None) -> str:
    if n is None:
        return "?"
    return f"{n:,}".replace(",", " ")


def _rank_line(rank: int | None, top_pct: int | float | None) -> str:
    if rank is None:
        return "?"
    line = f"#{_fmt_num(rank)}"
    if top_pct is not None:
        line += f" (top {top_pct:g}%)"
    return line


def build_profile_block(data: dict) -> list[str]:
    profile = data.get("profile") or {}
    username = profile.get("username") or data.get("username", "?")
    level = profile.get("level")
    badge_count = profile.get("badges_count")

    return [
        f"Username   {username}",
        f"Level      {level if level is not None else '?'}",
        f"Rank       {_rank_line(profile.get('rank'), profile.get('top_percentage'))}",
        f"Badges     {badge_count if badge_count is not None else '?'}",
        f"Rooms      {profile.get('rooms_completed') if profile.get('rooms_completed') is not None else '?'}",
        f"Streak     {profile.get('streak') if profile.get('streak') is not None else '?'} d",
    ]


def build_rankings_block(data: dict) -> list[str]:
    lines: list[str] = []
    league = data.get("league") or {}
    monthly = data.get("leaderboard_monthly") or {}
    user_m = monthly.get("user") or {}

    if league.get("authenticated"):
        tier = league.get("tier") or "?"
        rank = league.get("rank")
        pts = league.get("weekly_points")
        league_line = f"Weekly     #{rank if rank is not None else '?'} · {_fmt_num(pts)} pts · {tier}"
        if league.get("zone"):
            league_line += f" · {league['zone']}"
        if league.get("days_remaining") is not None:
            league_line += f" · {league['days_remaining']}d"
        lines.append(league_line)
    elif data.get("authenticated"):
        lines.append("Weekly     unavailable")
    else:
        lines.append("Weekly     login required")

    if user_m:
        lb_line = (
            f"Board      #{user_m.get('rank')} · "
            f"{_fmt_num(user_m.get('monthly_points'))} pts"
        )
        if monthly.get("days_remaining") is not None:
            lb_line += f" · {monthly['days_remaining']}d"
        lines.append(lb_line)
    else:
        lb_line = "Board      outside top 50"
        if monthly.get("days_remaining") is not None:
            lb_line += f" · {monthly['days_remaining']}d"
        lines.append(lb_line)

    return lines


def _top3_line(place: int, username: str, points: int | None) -> str:
    pts = _fmt_num(points) if points is not None else "?"
    return f"{place} - {username} - {pts}"


def build_top3_block(data: dict) -> list[str]:
    lines: list[str] = []
    league = data.get("league") or {}
    weekly_top = league.get("top3") or []
    if weekly_top:
        lines.append("Top 3 Weekly")
        for row in weekly_top:
            lines.append(
                _top3_line(row["rank"], row["username"], row.get("weekly_points"))
            )
        lines.append("")

    monthly = data.get("leaderboard_monthly") or {}
    board_top = monthly.get("top3") or []
    if board_top:
        lines.append("Top 3 Leaderboard")
        for row in board_top:
            lines.append(
                _top3_line(row["rank"], row["username"], row.get("monthly_points"))
            )

    return lines


def _points_to_first(top3: list[dict], points_key: str, user_points: int | None) -> int | None:
    if not top3 or user_points is None:
        return None
    leader_pts = top3[0].get(points_key)
    if leader_pts is None:
        return None
    gap = int(leader_pts) - int(user_points)
    return gap if gap > 0 else None


def build_catchup_block(data: dict) -> list[str]:
    """Alerts when not #1 and the period is ending soon."""
    lines: list[str] = []
    league = data.get("league") or {}
    monthly = data.get("leaderboard_monthly") or {}
    user_m = monthly.get("user") or {}

    weekly_days = league.get("days_remaining")
    if (
        league.get("authenticated")
        and league.get("rank") != 1
        and weekly_days is not None
        and weekly_days <= get_catchup_weekly_max_days()
    ):
        gap = _points_to_first(
            league.get("top3") or [], "weekly_points", league.get("weekly_points")
        )
        if gap is not None:
            lines.append(
                f"Weekly: {_fmt_num(gap)} pts to reach #1 ({weekly_days}d left)"
            )

    board_days = monthly.get("days_remaining")
    if (
        user_m.get("rank") != 1
        and board_days is not None
        and board_days <= get_catchup_board_max_days()
    ):
        gap = _points_to_first(
            monthly.get("top3") or [], "monthly_points", user_m.get("monthly_points")
        )
        if gap is not None:
            lines.append(
                f"Leaderboard: {_fmt_num(gap)} pts to reach #1 ({board_days}d left)"
            )

    return lines


def format_catchup_discord(data: dict) -> str | None:
    lines = build_catchup_block(data)
    return "\n".join(lines) if lines else None


def format_top3_discord(data: dict) -> str | None:
    block = build_top3_block(data)
    if not block:
        return None
    sections: list[str] = []
    league = data.get("league") or {}
    if league.get("top3"):
        sections.append(
            "**Weekly**\n"
            + "\n".join(
                _top3_line(r["rank"], r["username"], r.get("weekly_points"))
                for r in league["top3"]
            )
        )
    monthly = data.get("leaderboard_monthly") or {}
    if monthly.get("top3"):
        sections.append(
            "**Leaderboard**\n"
            + "\n".join(
                _top3_line(r["rank"], r["username"], r.get("monthly_points"))
                for r in monthly["top3"]
            )
        )
    return "\n\n".join(sections) if sections else None


def format_terminal(data: dict) -> str:
    profile = build_profile_block(data)
    rankings = build_rankings_block(data)
    top3 = build_top3_block(data)
    parts = [
        "",
        "=== THM Stats ===",
        "",
        "── Profile ─────────",
        *profile,
        "",
        "── Rankings ────────",
        *rankings,
    ]
    if top3:
        parts.extend(["", "── Top 3 ───────────", *top3])
    catchup = build_catchup_block(data)
    if catchup:
        parts.extend(["", "── Catch-up ────────", *catchup])
    return "\n".join(parts)
