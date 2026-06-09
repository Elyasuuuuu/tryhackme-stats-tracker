from __future__ import annotations

import json
import uuid
import urllib.error
import urllib.request

from card_image import render_stats_card
from display import format_catchup_discord, format_top3_discord
from env import get_discord_webhook_url


def _multipart_body(png: bytes, payload: dict, boundary: str) -> bytes:
    lines: list[bytes] = []
    payload_json = json.dumps(payload).encode()

    lines.append(f"--{boundary}\r\n".encode())
    lines.append(b'Content-Disposition: form-data; name="payload_json"\r\n\r\n')
    lines.append(payload_json)
    lines.append(b"\r\n")

    lines.append(f"--{boundary}\r\n".encode())
    lines.append(
        b'Content-Disposition: form-data; name="files[0]"; filename="thm-stats.png"\r\n'
    )
    lines.append(b"Content-Type: image/png\r\n\r\n")
    lines.append(png)
    lines.append(b"\r\n")

    lines.append(f"--{boundary}--\r\n".encode())
    return b"".join(lines)


def build_payload(data: dict) -> dict:
    profile = data.get("profile") or {}
    username = profile.get("username") or data.get("username", "?")

    embeds: list[dict] = [
        {
            "title": f"📊 {username}",
            "color": 0xE8640A,
            "image": {"url": "attachment://thm-stats.png"},
        }
    ]

    top3_text = format_top3_discord(data)
    if top3_text:
        embeds.append(
            {
                "title": "🏆 Top 3",
                "color": 0x1A5FA8,
                "description": top3_text,
            }
        )

    catchup_text = format_catchup_discord(data)
    if catchup_text:
        embeds.append(
            {
                "title": "🎯 Catch-up",
                "color": 0xE8640A,
                "description": catchup_text,
            }
        )

    return {
        "username": "THM Leaderboard",
        "embeds": embeds,
    }


def send_discord_webhook(data: dict) -> str | None:
    """Send the PNG stats card to Discord. Returns an error string or None on success."""
    url = get_discord_webhook_url()
    if not url:
        return None

    try:
        png = render_stats_card(data)
    except Exception as exc:
        return f"Image: {exc}"

    boundary = f"----THMStats{uuid.uuid4().hex}"
    body = _multipart_body(png, build_payload(data), boundary)
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
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
