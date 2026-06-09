from __future__ import annotations

import calendar
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from playwright.sync_api import Page, sync_playwright

from env import BASE_DIR, STORAGE_STATE, get_connect_sid, load_env

load_env()
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)

TIER_NAMES = {
    1: "Bronze League",
    2: "Silver League",
    3: "Gold League",
    4: "Platinum League",
    5: "Diamond League",
}


@dataclass
class LeaderboardEntry:
    rank: int
    username: str
    country: str | None
    level: int | None
    total_points: int | None
    monthly_points: int | None
    rooms_in: int | None
    user_id: str | None


@dataclass
class LeaderboardSnapshot:
    period: str
    country: str
    entries: list[LeaderboardEntry]
    user_entry: LeaderboardEntry | None = None
    days_remaining: int | None = None


@dataclass
class LeaguePlayer:
    rank: int
    username: str
    weekly_points: int


@dataclass
class LeagueSnapshot:
    tier: str | None = None
    rank: int | None = None
    weekly_points: int | None = None
    days_remaining: int | None = None
    zone: str | None = None
    promotion_cutoff: int | None = None
    top3: list[LeaguePlayer] = field(default_factory=list)
    authenticated: bool = False
    raw_text: str | None = None


@dataclass
class ProfileSnapshot:
    username: str
    level: int | None = None
    rank: int | None = None
    top_percentage: float | None = None
    badges_count: int | None = None
    latest_badge: str | None = None
    rooms_completed: int | None = None
    streak: int | None = None
    total_points: int | None = None


@dataclass
class CollectResult:
    username: str
    authenticated: bool
    profile: ProfileSnapshot | None = None
    leaderboard_monthly: LeaderboardSnapshot | None = None
    league: LeagueSnapshot | None = None
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        def lb_dict(lb: LeaderboardSnapshot | None) -> dict | None:
            if not lb:
                return None
            user = lb.user_entry
            return {
                "period": lb.period,
                "country": lb.country,
                "top_count": len(lb.entries),
                "days_remaining": lb.days_remaining,
                "top3": [
                    {
                        "rank": e.rank,
                        "username": e.username,
                        "monthly_points": e.monthly_points,
                    }
                    for e in lb.entries[:3]
                ],
                "user": None
                if not user
                else {
                    "rank": user.rank,
                    "username": user.username,
                    "country": user.country,
                    "level": user.level,
                    "total_points": user.total_points,
                    "monthly_points": user.monthly_points,
                    "rooms_in": user.rooms_in,
                    "user_id": user.user_id,
                },
            }

        league = self.league
        return {
            "username": self.username,
            "authenticated": self.authenticated,
            "leaderboard_monthly": lb_dict(self.leaderboard_monthly),
            "league": None
            if not league
            else {
                "tier": league.tier,
                "rank": league.rank,
                "weekly_points": league.weekly_points,
                "days_remaining": league.days_remaining,
                "zone": league.zone,
                "promotion_cutoff": league.promotion_cutoff,
                "top3": [
                    {
                        "rank": p.rank,
                        "username": p.username,
                        "weekly_points": p.weekly_points,
                    }
                    for p in league.top3
                ],
                "authenticated": league.authenticated,
            },
            "profile": None
            if not self.profile
            else {
                "username": self.profile.username,
                "level": self.profile.level,
                "rank": self.profile.rank,
                "top_percentage": self.profile.top_percentage,
                "badges_count": self.profile.badges_count,
                "latest_badge": self.profile.latest_badge,
                "rooms_completed": self.profile.rooms_completed,
                "streak": self.profile.streak,
                "total_points": self.profile.total_points,
            },
            "errors": self.errors,
        }


class THMClient:
    def __init__(self, username: str, country: str = "", headless: bool = True):
        self.username = username
        self.country = country
        self.headless = headless
        self._captured: dict[str, dict] = {}

    def _has_auth_material(self) -> bool:
        return STORAGE_STATE.exists() or bool(get_connect_sid())

    def collect(self) -> CollectResult:
        result = CollectResult(
            username=self.username,
            authenticated=self._has_auth_material(),
        )
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless)
            context_kwargs: dict[str, Any] = {"user_agent": USER_AGENT}
            if STORAGE_STATE.exists():
                context_kwargs["storage_state"] = str(STORAGE_STATE)
            context = browser.new_context(**context_kwargs)
            connect_sid = get_connect_sid()
            if connect_sid:
                context.add_cookies(
                    [
                        {
                            "name": "connect.sid",
                            "value": connect_sid,
                            "domain": "tryhackme.com",
                            "path": "/",
                            "httpOnly": True,
                            "secure": True,
                            "sameSite": "Lax",
                        }
                    ]
                )
            page = context.new_page()
            page.on("response", self._on_response)

            try:
                result.leaderboard_monthly = self._collect_leaderboard(
                    page, period="monthly", username=self.username, country=self.country
                )
            except Exception as exc:
                result.errors.append(f"leaderboard_monthly: {exc}")

            if self._has_auth_material():
                try:
                    result.profile = self._collect_profile(page)
                except Exception as exc:
                    result.errors.append(f"profile: {exc}")

                try:
                    result.league = self._collect_league(page)
                except Exception as exc:
                    result.errors.append(f"league: {exc}")

                if not self._looks_authenticated(page):
                    result.authenticated = False
                    result.errors.append(
                        "session expired — run collect.py login or update .env (THM_CONNECT_SID)"
                    )
            else:
                result.errors.append(
                    "no session — weekly league skipped. Run: python collect.py login"
                )

            browser.close()
        return result

    def _on_response(self, response) -> None:
        url = response.url
        if "tryhackme.com/api/" not in url:
            return
        try:
            body = response.json()
        except Exception:
            return
        self._captured[url] = body

    def _collect_leaderboard(
        self, page: Page, period: str, username: str, country: str
    ) -> LeaderboardSnapshot:
        self._captured.clear()

        def wait_leaderboard_response() -> dict:
            with page.expect_response(
                lambda r: "leaderboards/general" in r.url and r.status == 200,
                timeout=45000,
            ) as resp_info:
                page.goto(
                    "https://tryhackme.com/leaderboards",
                    wait_until="domcontentloaded",
                    timeout=60000,
                )
            return resp_info.value.json()

        if period == "all":
            page.goto(
                "https://tryhackme.com/leaderboards",
                wait_until="domcontentloaded",
                timeout=60000,
            )
            page.wait_for_timeout(2000)
            with page.expect_response(
                lambda r: "leaderboards/general" in r.url
                and "period=all" in r.url
                and r.status == 200,
                timeout=20000,
            ) as resp_info:
                page.get_by_role("button", name="All time", exact=True).click(timeout=8000)
            payload = resp_info.value.json()
        else:
            payload = wait_leaderboard_response()

        users = payload.get("data", {}).get("users", [])
        entries = []
        user_entry = None
        for idx, user in enumerate(users, start=1):
            entry = LeaderboardEntry(
                rank=idx,
                username=user.get("username", ""),
                country=user.get("country"),
                level=user.get("level"),
                total_points=user.get("points"),
                monthly_points=user.get("monthlyPoints"),
                rooms_in=user.get("roomsIn"),
                user_id=user.get("_id"),
            )
            entries.append(entry)
            if entry.username.lower() == username.lower():
                user_entry = entry

        return LeaderboardSnapshot(
            period=period,
            country=country,
            entries=entries,
            user_entry=user_entry,
            days_remaining=self._monthly_days_remaining(),
        )

    def _monthly_days_remaining(self) -> int:
        now = datetime.now(timezone.utc)
        last_day = calendar.monthrange(now.year, now.month)[1]
        if now.day == last_day and (now.hour > 23 or (now.hour == 23 and now.minute >= 59)):
            return 0
        return last_day - now.day

    def _looks_authenticated(self, page: Page) -> bool:
        try:
            page.goto("https://tryhackme.com/dashboard", wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2000)
            body = page.inner_text("body").lower()
            return "log in" not in body[:500] and "join for free" not in body[:800]
        except Exception:
            return False

    def _league_days_remaining(self, end_date: str | None) -> int | None:
        if not end_date:
            return None
        end = datetime.fromisoformat(end_date.replace("Z", "+00:00"))
        delta = end - datetime.now(timezone.utc)
        return max(0, delta.days)

    def _league_zone_from_text(self, text: str) -> str | None:
        lower = text.lower()
        if "promotion zone" in lower:
            return "promotion"
        if "demotion zone" in lower:
            return "demotion"
        if "well done" in lower and "promotion" in lower:
            return "promotion"
        return None

    def _collect_league(self, page: Page) -> LeagueSnapshot:
        with page.expect_response(
            lambda r: "weekly-leagues/statistics" in r.url and r.status == 200,
            timeout=45000,
        ) as resp_info:
            page.goto(
                "https://tryhackme.com/leagues",
                wait_until="domcontentloaded",
                timeout=60000,
            )
        page.wait_for_timeout(1500)
        text = page.inner_text("body")
        if "log in" in text.lower()[:600]:
            return LeagueSnapshot(authenticated=False)

        payload = resp_info.value.json()
        data = payload.get("data", {})
        tier_num = data.get("tier")
        tier = TIER_NAMES.get(tier_num, f"Tier {tier_num}" if tier_num else None)
        days_remaining = self._league_days_remaining(data.get("endDate"))

        leaderboard = data.get("leaderboard") or []
        user_row = next(
            (
                entry
                for entry in leaderboard
                if entry.get("username", "").lower() == self.username.lower()
            ),
            None,
        )
        if user_row is None:
            user_row = next((entry for entry in leaderboard if entry.get("isCurrent")), None)

        rank = user_row.get("position") if user_row else None
        weekly_points = user_row.get("points") if user_row else None
        top3 = [
            LeaguePlayer(
                rank=int(entry["position"]),
                username=entry["username"],
                weekly_points=int(entry["points"]),
            )
            for entry in leaderboard[:3]
        ]

        zone = self._league_zone_from_text(text)
        promotion_cutoff = None
        promo_match = re.search(r"top\s+(\d+)\s+advance", text, re.IGNORECASE)
        if promo_match:
            promotion_cutoff = int(promo_match.group(1))

        return LeagueSnapshot(
            tier=tier,
            rank=rank,
            weekly_points=weekly_points,
            days_remaining=days_remaining,
            zone=zone,
            promotion_cutoff=promotion_cutoff,
            top3=top3,
            authenticated=True,
        )

    def _collect_profile(self, page: Page) -> ProfileSnapshot:
        stats_body: dict | None = None
        self_data: dict | None = None

        with page.expect_response(
            lambda r: "users/statistics" in r.url and r.status == 200,
            timeout=45000,
        ) as stats_resp:
            page.goto(
                "https://tryhackme.com/dashboard",
                wait_until="domcontentloaded",
                timeout=60000,
            )
        stats_body = stats_resp.value.json().get("data", {})

        for url, body in self._captured.items():
            if "users/self" in url:
                self_data = body.get("data", {}).get("user", {})
                break

        if not self_data:
            with page.expect_response(
                lambda r: "users/self" in r.url and r.status == 200,
                timeout=20000,
            ) as self_resp:
                page.reload(wait_until="domcontentloaded")
            self_data = self_resp.value.json().get("data", {}).get("user", {})

        badges = self_data.get("badges") or []
        latest_badge = badges[-1].get("name") if badges else None
        username = self_data.get("username") or self.username

        return ProfileSnapshot(
            username=username,
            level=stats_body.get("level"),
            rank=stats_body.get("rank"),
            top_percentage=stats_body.get("topPercentage"),
            badges_count=stats_body.get("badgesNumber"),
            latest_badge=latest_badge,
            rooms_completed=stats_body.get("completedRoomsNumber"),
            streak=stats_body.get("streak"),
            total_points=stats_body.get("totalPoints"),
        )


def save_storage_state_interactive() -> None:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(user_agent=USER_AGENT)
        page = context.new_page()
        page.goto("https://tryhackme.com/login", wait_until="domcontentloaded")
        print("Log in to TryHackMe in the Chromium window.")
        print("When the dashboard is visible, return here and press Enter.")
        input()
        context.storage_state(path=str(STORAGE_STATE))
        browser.close()
        print(f"Session saved to {STORAGE_STATE}")
        from env import sync_connect_sid_from_storage_state

        if sync_connect_sid_from_storage_state():
            print(f"connect.sid token copied to {BASE_DIR / '.env'}")
        else:
            print("connect.sid not found — add THM_CONNECT_SID to .env manually")
