from __future__ import annotations

import io
from pathlib import Path

from display import _fmt_num
from PIL import Image, ImageDraw, ImageFont

# Palette THM / Discord dark
BG = "#0d1117"
PANEL = "#161b22"
PANEL_ALT = "#1c2333"
ACCENT = "#e8640a"
BLUE = "#1a5fa8"
TEXT = "#f0f6fc"
MUTED = "#8b949e"
GREEN = "#3fb950"
GOLD = "#d4a72c"

FONT_DIR = Path("/usr/share/fonts/truetype/dejavu")


def _font(name: str, size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    path = FONT_DIR / name
    if path.exists():
        return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _tier_color(tier: str | None) -> str:
    if not tier:
        return BLUE
    t = tier.lower()
    if "bronze" in t:
        return "#cd7f32"
    if "silver" in t:
        return "#b8c4ce"
    if "gold" in t:
        return GOLD
    if "platinum" in t:
        return "#79c0ff"
    if "diamond" in t:
        return "#a5d8ff"
    return BLUE


def _draw_rounded_rect(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int, int, int],
    fill: str,
    radius: int = 14,
) -> None:
    draw.rounded_rectangle(xy, radius=radius, fill=fill)


def _stat_cell(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    w: int,
    h: int,
    label: str,
    value: str,
    sub: str | None = None,
    accent: str = BLUE,
) -> None:
    _draw_rounded_rect(draw, (x, y, x + w, y + h), PANEL_ALT)
    draw.rounded_rectangle((x, y, x + w, y + 4), radius=14, fill=accent)
    draw.text((x + 16, y + 12), label.upper(), font=_font("DejaVuSans.ttf", 11), fill=MUTED)
    draw.text((x + 16, y + 32), value, font=_font("DejaVuSans-Bold.ttf", 22), fill=TEXT)
    if sub:
        draw.text((x + 16, y + h - 24), sub, font=_font("DejaVuSans.ttf", 11), fill=MUTED)


def _ranking_cell(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    w: int,
    h: int,
    label: str,
    rank: str,
    points_line: str,
    meta_line: str | None,
    accent: str,
) -> None:
    _draw_rounded_rect(draw, (x, y, x + w, y + h), PANEL_ALT)
    draw.rounded_rectangle((x, y, x + w, y + 4), radius=14, fill=accent)
    draw.text((x + 16, y + 12), label.upper(), font=_font("DejaVuSans.ttf", 11), fill=MUTED)
    draw.text((x + 16, y + 30), rank, font=_font("DejaVuSans-Bold.ttf", 28), fill=TEXT)
    draw.text((x + 16, y + 64), points_line, font=_font("DejaVuSans-Bold.ttf", 12), fill=TEXT)
    if meta_line:
        draw.text((x + 16, y + 84), meta_line, font=_font("DejaVuSans.ttf", 10), fill=MUTED)


def render_stats_card(data: dict) -> bytes:
    profile = data.get("profile") or {}
    league = data.get("league") or {}
    monthly = data.get("leaderboard_monthly") or {}
    user_m = monthly.get("user") or {}

    username = profile.get("username") or data.get("username", "?")

    width = 560
    height = 460
    img = Image.new("RGB", (width, height), BG)
    draw = ImageDraw.Draw(img)

    # Header
    _draw_rounded_rect(draw, (16, 16, width - 16, 88), PANEL)
    draw.rounded_rectangle((16, 16, width - 16, 24), radius=14, fill=ACCENT)
    draw.text((32, 30), "TRYHACKME", font=_font("DejaVuSans-Bold.ttf", 12), fill=ACCENT)
    draw.text((32, 48), username, font=_font("DejaVuSans-Bold.ttf", 26), fill=TEXT)

    draw.text((24, 104), "PROFILE", font=_font("DejaVuSans-Bold.ttf", 12), fill=ACCENT)

    rank_val = _fmt_num(profile.get("rank")) if profile.get("rank") else "?"
    rank_sub = (
        f"top {profile['top_percentage']:g}%"
        if profile.get("top_percentage") is not None
        else None
    )
    _stat_cell(
        draw, 16, 124, 168, 88, "Level", str(profile.get("level") or "?"), accent=BLUE
    )
    _stat_cell(draw, 196, 124, 168, 88, "Rank", f"#{rank_val}", rank_sub, accent=ACCENT)
    _stat_cell(
        draw,
        376,
        124,
        168,
        88,
        "Streak",
        f"{profile.get('streak') or '?'} d",
        accent=GREEN,
    )

    _stat_cell(
        draw,
        16,
        224,
        264,
        88,
        "Badges",
        str(profile.get("badges_count") or "?"),
        accent=GOLD,
    )
    _stat_cell(
        draw,
        296,
        224,
        248,
        88,
        "Rooms",
        str(profile.get("rooms_completed") or "?"),
        accent=BLUE,
    )

    draw.text((24, 328), "RANKINGS", font=_font("DejaVuSans-Bold.ttf", 12), fill=ACCENT)

    tier = league.get("tier") or "?"
    weekly_rank = f"#{league.get('rank') if league.get('rank') is not None else '?'}"
    weekly_pts = f"{_fmt_num(league.get('weekly_points'))} pts"
    meta_parts = [tier]
    if league.get("zone"):
        meta_parts.append(league["zone"])
    if league.get("days_remaining") is not None:
        meta_parts.append(f"{league['days_remaining']}d")

    _ranking_cell(
        draw,
        16,
        348,
        264,
        104,
        "Weekly",
        weekly_rank,
        weekly_pts,
        " · ".join(meta_parts),
        accent=_tier_color(tier),
    )

    board_rank = f"#{user_m.get('rank') if user_m.get('rank') else '50+'}"
    board_pts = f"{_fmt_num(user_m.get('monthly_points'))} pts"
    board_meta = (
        f"{monthly['days_remaining']}d"
        if monthly.get("days_remaining") is not None
        else None
    )
    _ranking_cell(
        draw,
        296,
        348,
        248,
        104,
        "Leaderboard",
        board_rank,
        board_pts,
        board_meta,
        accent=ACCENT,
    )

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()
