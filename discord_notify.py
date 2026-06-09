from __future__ import annotations

import json
import urllib.error
import urllib.request

from display import build_player_discord_embed, build_top3_discord_embed
from env import get_discord_webhook_url


def build_payload(data: dict) -> dict:
    embeds: list[dict] = [build_player_discord_embed(data)]

    top3_embed = build_top3_discord_embed(data)
    if top3_embed:
        embeds.append(top3_embed)

    return {
        "username": "THM Leaderboard",
        "embeds": embeds,
    }


def send_discord_webhook(data: dict) -> str | None:
    """Send stats embeds to Discord. Returns an error string or None on success."""
    url = get_discord_webhook_url()
    if not url:
        return None

    body = json.dumps(build_payload(data)).encode()
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "thm-stats/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status >= 400:
                return f"Discord HTTP {resp.status}"
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode(errors="replace")[:200]
        return f"Discord HTTP {exc.code}: {err_body}"
    except urllib.error.URLError as exc:
        return f"Discord: {exc.reason}"
    return None
