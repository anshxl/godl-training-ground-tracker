# Aim Training Tracker Bot

A Discord bot that tracks aim practice for the team. Players post a screenshot of their Call of Duty: Mobile practice range results in one channel. The bot checks the screenshot, counts it, and keeps daily, weekly and all-time leaderboards.

## How a submission works

1. A player posts an image in the tracking channel. The bot uses the first image in the message.
2. If the player already posted a file with the same name, the bot rejects it as a duplicate.
3. The bot checks the image's C2PA metadata and rejects images marked as AI-generated.
4. Gemini (`gemini-2.5-flash-lite`) checks that the image is the practice range "MISSION COMPLETE" results screen. The prompt is `VALIDATION_PROMPT` in [utils/image_validator.py](utils/image_validator.py).
5. A valid screenshot adds 1 to the player's daily and weekly counts, and the bot replies with the new counts.

If Gemini fails or `GEMINI_API_KEY` is not set, the bot accepts the image, so an outage never blocks players. The bot logs a warning at startup when the key is missing.

## Commands

| Command | Aliases | What it does |
|---|---|---|
| `!leaderboard` | `!stats`, `!lb` | Weekly leaderboard (top 10) |
| `!mystats` | `!me`, `!myrank` | Your daily, weekly and all-time counts and ranks |
| `!alltime` | `!lifetime`, `!total`, `!at` | All-time leaderboard (top 10) |
| `!admin` | | Lists the admin commands |
| `!admin reset daily` / `weekly` | | Sets every player's count to 0 (asks for a ✅ reaction first) |
| `!admin set @user daily\|weekly <n>` | | Sets one player's count |
| `!admin add @user daily\|weekly <n>` | | Adds to one player's count (negative subtracts) |
| `!admin info` | | Shows the bot's settings |

Admin commands need the role in `ADMIN_ROLE_ID` or the server's Administrator permission.

## Scheduled jobs

Times use `TIMEZONE`. The hours and day are in [config.json](config.json).

- **Daily reset:** daily counts go to 0 at `daily_reset_hour`.
- **Weekly reset:** weekly counts go to 0 on `weekly_reset_day` (0 = Monday, 6 = Sunday) at `weekly_reset_hour`.
- **Monthly recap:** on the 1st at 00:00, the bot posts last month's sessions per player in the tracking channel.

Resets only change the counters. Submissions are kept, so the all-time counts and the monthly recap are not affected.

## Training API

When `TRAINING_API_TOKEN` is set, the bot also serves `GET /training?month=YYYY-MM` on `PORT`, with the header `Authorization: Bearer <token>`. It returns sessions and days trained per player for that month (usernames and counts only). The Training page of the cdm_stats dashboard reads it.

To try it without Discord, see [scripts/seed_sample_training.py](scripts/seed_sample_training.py).

## Setup

### 1. Create the Discord bot

1. In the [Discord Developer Portal](https://discord.com/developers/applications), create an application and add a bot.
2. Turn on the **Message Content** and **Server Members** intents. Copy the bot token.
3. Under OAuth2 → URL Generator, select the `bot` scope and these permissions: View Channels, Send Messages, Embed Links, Read Message History, Add Reactions. Open the URL to invite the bot.
4. Turn on Developer Mode in Discord (Settings → Advanced). Right-click the tracking channel and the admin role to copy their IDs.

### 2. Run it

Needs Python 3.11 and [uv](https://docs.astral.sh/uv/).

```
uv sync
cp .env.example .env   # then fill it in
uv run python bot.py
```

| Variable | Required | Meaning |
|---|---|---|
| `DISCORD_TOKEN` | yes | Bot token |
| `TRACKING_CHANNEL_ID` | yes | Channel where players post screenshots |
| `ADMIN_ROLE_ID` | yes | Role allowed to use admin commands |
| `TIMEZONE` | no | IANA name for resets and submission dates (default `America/New_York`) |
| `GEMINI_API_KEY` | no | Turns on screenshot validation. Get one from [Google AI Studio](https://aistudio.google.com/apikey). |
| `TRAINING_API_TOKEN` | no | Turns on the training API |
| `PORT` | no | Training API port (default 8080) |

The bot creates the SQLite database at `data/tracker.db` (set by `database_path` in [config.json](config.json)). Logs go to the console and to `bot.log`.

## Deploy

Production runs on Railway with the [Procfile](Procfile) (`python bot.py`). Set the variables above on the host.

The database is a file, so the host must keep `data/` across redeploys (on Railway, mount a volume there). Without that, every redeploy starts with an empty database.

## Tests

```
uv sync --extra dev
uv run pytest
```

The tests use a temporary database and stub out Gemini, so they need no Discord token or API key.
