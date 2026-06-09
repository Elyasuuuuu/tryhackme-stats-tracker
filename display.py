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


_MEDALS = {1: "🥇", 2: "🥈", 3: "🥉"}
_ZONE_LABELS = {
    "promotion": "↑ promotion",
    "relegation": "↓ relegation",
}


def _discord_rank(rank: int | None) -> str:
    return f"**#{rank}**" if rank is not None else "**?**"


def _discord_pts(points: int | None) -> str:
    return f"`{_fmt_num(points)}` pts" if points is not None else "`?` pts"


def _discord_days(days: int | None) -> str:
    return f"`{days}d` left" if days is not None else ""


def _discord_zone(zone: str | None) -> str:
    if not zone:
        return ""
    return _ZONE_LABELS.get(zone.lower(), zone)


def _discord_top3_lines(rows: list[dict], points_key: str) -> str:
    return "\n".join(
        f"{_MEDALS.get(r['rank'], '▫️')} **{r['username']}** — {_discord_pts(r.get(points_key))}"
        for r in rows
    )


def _weekly_ranking_value(data: dict) -> str:
    league = data.get("league") or {}
    if not league.get("authenticated"):
        if data.get("authenticated"):
            return "_Unavailable_"
        return "_Login required_"

    rank = league.get("rank")
    tier = league.get("tier") or "?"
    lines = [
        f"{_discord_rank(rank)}  ·  {_discord_pts(league.get('weekly_points'))}",
        tier,
    ]
    zone = _discord_zone(league.get("zone"))
    days = _discord_days(league.get("days_remaining"))
    meta = " · ".join(part for part in (zone, days) if part)
    if meta:
        lines.append(meta)
    return "\n".join(lines)


def _board_ranking_value(data: dict) -> str:
    monthly = data.get("leaderboard_monthly") or {}
    user_m = monthly.get("user") or {}
    days = _discord_days(monthly.get("days_remaining"))

    if user_m:
        line = f"{_discord_rank(user_m.get('rank'))}  ·  {_discord_pts(user_m.get('monthly_points'))}"
        if days:
            line += f"  ·  {days}"
        return line

    line = "_Outside top 50_"
    if days:
        line += f"  ·  {days}"
    return line


def _catchup_discord_lines(data: dict) -> list[str]:
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
                f"⚔️ Weekly — **`{_fmt_num(gap)}` pts** to **#1** · {_discord_days(weekly_days)}"
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
                f"🏅 Board — **`{_fmt_num(gap)}` pts** to **#1** · {_discord_days(board_days)}"
            )

    return lines


def build_player_discord_embed(data: dict) -> dict:
    profile = data.get("profile") or {}
    username = profile.get("username") or data.get("username", "?")
    level = profile.get("level")
    badge_count = profile.get("badges_count")
    streak = profile.get("streak")
    rooms = profile.get("rooms_completed")
    rank = profile.get("rank")
    top_pct = profile.get("top_percentage")

    rank_value = f"`#{_fmt_num(rank)}`" if rank is not None else "`?`"
    if top_pct is not None:
        rank_value += f"\ntop **{top_pct:g}%**"

    fields: list[dict] = [
        {"name": "Level", "value": f"`{level if level is not None else '?'}`", "inline": True},
        {"name": "Global rank", "value": rank_value, "inline": True},
        {"name": "Streak", "value": f"`{streak if streak is not None else '?'}` days", "inline": True},
        {"name": "Badges", "value": f"`{badge_count if badge_count is not None else '?'}`", "inline": True},
        {"name": "Rooms", "value": f"`{rooms if rooms is not None else '?'}`", "inline": True},
        {"name": "\u200b", "value": "\u200b", "inline": True},
        {"name": "⚔️ Weekly League", "value": _weekly_ranking_value(data), "inline": False},
        {"name": "🏅 Monthly Board", "value": _board_ranking_value(data), "inline": False},
    ]

    catchup = _catchup_discord_lines(data)
    if catchup:
        fields.append(
            {"name": "🎯 Catch-up", "value": "\n".join(catchup), "inline": False}
        )

    return {
        "title": f"📊  {username}",
        "color": 0xE8640A,
        "fields": fields,
    }


def build_top3_discord_embed(data: dict) -> dict | None:
    fields: list[dict] = []
    league = data.get("league") or {}
    weekly_top = league.get("top3") or []
    if weekly_top:
        fields.append(
            {
                "name": "⚔️ Weekly League",
                "value": _discord_top3_lines(weekly_top, "weekly_points"),
                "inline": False,
            }
        )

    monthly = data.get("leaderboard_monthly") or {}
    board_top = monthly.get("top3") or []
    if board_top:
        fields.append(
            {
                "name": "🏅 Monthly Board",
                "value": _discord_top3_lines(board_top, "monthly_points"),
                "inline": False,
            }
        )

    if not fields:
        return None

    return {
        "title": "🏆  Top 3",
        "color": 0x1A5FA8,
        "fields": fields,
    }


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
