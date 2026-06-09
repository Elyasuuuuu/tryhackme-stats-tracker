# tryhackme-stats-tracker

Periodic TryHackMe stats collector (profile, weekly league, leaderboard) with Discord notifications.


## Installation

On modern Linux (Kali, Debian, Ubuntu…), system Python is **externally managed** — `pip install` without a venv is blocked on purpose. Use a virtual environment:

```bash
gh repo clone Elyasuuuuu/tryhackme-stats-tracker
cd tryhackme-stats-tracker
python3 -m venv .venv
source .venv/bin/activate    # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium
cp .env.example .env
```


## Configuration (`.env`)

| Variable | Description |
|----------|-------------|
| `THM_USERNAME` | TryHackMe username (required) |
| `THM_COUNTRY` | Leaderboard country filter (`fr`, empty = global) |
| `THM_CONNECT_SID` | Session cookie (see below) |
| `DISCORD_WEBHOOK_URL` | Discord webhook URL |
| `CATCHUP_WEEKLY_MAX_DAYS` | Weekly catch-up alert when ≤ N days left (default: 2) |
| `CATCHUP_BOARD_MAX_DAYS` | Board catch-up alert when ≤ N days left (default: 6) |

### TryHackMe session (`THM_CONNECT_SID`)

Two ways to provide a session:

**Option A — manual (recommended for server / cron)**  
No need to run `collect.py login` or have a graphical browser on the machine running cron.

1. Log in to [tryhackme.com](https://tryhackme.com) in your usual browser.
2. Open DevTools (`F12`) → **Application** tab (Chrome) or **Storage** (Firefox).
3. **Cookies** → `https://tryhackme.com` → copy the `connect.sid` cookie value.
4. Paste it in `.env`:
   ```
   THM_CONNECT_SID=s%3A...your_value...
   ```
   The value is often already URL-encoded (`s%3A...`) — paste it as-is, without quotes.

When the session expires (after several weeks), repeat these steps or run `python collect.py login`.

**Option B — interactive login (machine with a display)**  
Opens Chromium; log in once. The script saves `storage_state.json` and copies `connect.sid` to `.env` automatically.

```bash
python collect.py login
```

## Usage

```bash
python collect.py collect        # collect + Discord
python collect.py collect --no-discord
python collect.py latest
python collect.py history
```

## Scheduled runs (cron)

To run collection automatically at a time of your choice, use `crontab`:

```bash
crontab -e
```

Add a line (replace `/path/tryhackme-stats-tracker` with the project’s absolute path):

```cron
# minute  hour  day  month  weekday  command
```

Examples:

```cron
# Every day at 8:00 AM
0 8 * * * cd /path/tryhackme-stats-tracker && /usr/bin/python3 collect.py collect >> /path/tryhackme-stats-tracker/collect.log 2>&1

# Every 6 hours (0:00, 6:00, 12:00, 18:00)
0 */6 * * * cd /path/tryhackme-stats-tracker && /usr/bin/python3 collect.py collect >> /path/tryhackme-stats-tracker/collect.log 2>&1

# Monday to Friday at 9:30 AM
30 9 * * 1-5 cd /path/tryhackme-stats-tracker && /usr/bin/python3 collect.py collect >> /path/tryhackme-stats-tracker/collect.log 2>&1
```

Notes:

- Use **absolute paths** to `python3` (`which python3`) and the project directory.
- With a venv: `/path/tryhackme-stats-tracker/.venv/bin/python collect.py collect`
- `THM_CONNECT_SID` must be set in `.env` — cron does not open a browser.
- Redirecting to `>> collect.log` keeps a trace on errors (`collect.log` is gitignored).

Verify the job is registered: `crontab -l`.

## Generated files (gitignored)

- `.env` — secrets
- `storage_state.json` — Playwright session
- `stats.db` — SQLite history
