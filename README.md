# Discord Aim Training Tracker Bot 🎯

A Discord bot that tracks daily aim training practice for gaming teams. Players post screenshots of their training results in a dedicated channel, and the bot automatically maintains daily and weekly submission counters.

## Features

- 📸 **Automatic Screenshot Tracking** - Monitors a designated channel for training screenshots
- 📊 **Statistics & Leaderboards** - Track daily and weekly submission counts with competitive rankings
- 🔄 **Automated Resets** - Scheduled daily and weekly counter resets
- ✅ **One Submission Per Day** - Prevents duplicate submissions on the same day
- 🎨 **Rich Discord Embeds** - Beautiful, informative messages with reactions
- 🔧 **Admin Controls** - Manual reset commands for administrators
- 💾 **Persistent Storage** - SQLite database for reliable data persistence

## Project Structure

```
discord-bot/
├── bot.py                        # Main bot entry point
├── database.py                   # Database connection and queries
├── config.json                   # Bot configuration
├── .env                          # Environment variables (create from .env.example)
├── .env.example                  # Environment variables template
├── pyproject.toml                # Python dependencies (uv)
├── commands/
│   ├── __init__.py
│   ├── stats.py                  # Stats and leaderboard commands
│   └── admin.py                  # Admin commands
├── handlers/
│   ├── __init__.py
│   ├── message_handler.py        # Screenshot submission handler
│   └── scheduler.py              # Automated reset scheduler
├── utils/
│   ├── __init__.py
│   └── helpers.py                # Helper functions
└── data/
    └── tracker.db                # SQLite database (auto-created)
```

## Prerequisites

- Python 3.11 or higher
- [uv](https://github.com/astral-sh/uv) package manager
- A Discord bot token ([Create one here](https://discord.com/developers/applications))
- Discord server with appropriate permissions

## Installation

### 1. Clone or Download the Project

```bash
cd discord-bot
```

### 2. Install Dependencies

Using `uv`:
```bash
uv sync
```

Or using pip:
```bash
pip install discord.py python-dotenv APScheduler pytz
```

### 3. Create Discord Bot

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name
3. Go to the "Bot" section and click "Add Bot"
4. Enable these Privileged Gateway Intents:
   - Message Content Intent
   - Server Members Intent
5. Copy the bot token

### 4. Invite Bot to Your Server

1. Go to OAuth2 → URL Generator
2. Select scopes: `bot`, `applications.commands`
3. Select permissions:
   - Read Messages/View Channels
   - Send Messages
   - Embed Links
   - Read Message History
   - Add Reactions
4. Copy the generated URL and open it in your browser to invite the bot

### 5. Configure Environment Variables

Create a `.env` file from the example:
```bash
cp .env.example .env
```

Edit `.env` with your values:
```env
DISCORD_TOKEN=your_bot_token_here
TRACKING_CHANNEL_ID=123456789012345678
ADMIN_ROLE_ID=987654321098765432
TIMEZONE=America/New_York
# Optional: read-only /training endpoint for the cdm_stats dashboard.
# The web server starts only when the token is set.
TRAINING_API_TOKEN=
PORT=8080
```

**How to get IDs:**
- Enable Developer Mode in Discord (Settings → Advanced → Developer Mode)
- Right-click on a channel or role and select "Copy ID"

### 6. Configure Bot Settings (Optional)

Edit `config.json` to customize:
```json
{
  "prefix": "!",
  "daily_reset_hour": 0,
  "weekly_reset_day": 6,
  "weekly_reset_hour": 0,
  "database_path": "data/tracker.db",
  "max_submissions_per_day": 1
}
```

- `daily_reset_hour`: Hour (0-23) for daily reset
- `weekly_reset_day`: Day of week (0=Monday, 6=Sunday)
- `database_path`: Path to SQLite database file

## Usage

### Running the Bot

```bash
uv run python bot.py
```

Or with standard Python:
```bash
python bot.py
```

The bot will:
1. Connect to Discord
2. Initialize the database
3. Start monitoring the tracking channel
4. Set up automated reset schedules

### Bot Commands

#### For Players

**`!leaderboard`** (aliases: `!stats`, `!lb`)
- Shows the weekly leaderboard with top performers
- Displays daily and weekly counts for all players

**`!mystats`** (aliases: `!me`, `!myrank`)
- Shows your personal statistics
- Displays your current rank on the leaderboard
- Shows daily and weekly submission counts

#### For Admins

**`!admin`**
- Shows available admin commands

**`!admin reset daily`**
- Manually reset all daily counters to 0
- Requires confirmation

**`!admin reset weekly`**
- Manually reset all weekly counters to 0
- Requires confirmation

**`!admin info`**
- Display bot configuration and status

### How It Works

1. **Submit Training**: Players post a screenshot in the designated tracking channel
2. **Automatic Detection**: Bot detects image attachments and validates them
3. **One Per Day**: Bot checks if player already submitted today
4. **Update Counters**: If valid, bot logs submission and updates daily/weekly counts
5. **Confirmation**: Bot sends a confirmation message with updated stats
6. **Automated Resets**: Counters reset automatically at configured times

## Database Schema

### Tables

**players**
- `discord_id` (PRIMARY KEY): Discord user ID
- `username`: Discord username
- `created_at`: Account creation timestamp

**submissions**
- `id` (PRIMARY KEY): Auto-incrementing ID
- `discord_id`: Foreign key to players
- `submission_date`: Date of submission
- `timestamp`: Exact submission time
- `image_url`: URL of submitted image

**counters**
- `discord_id` (PRIMARY KEY): Foreign key to players
- `daily_count`: Current daily submission count
- `weekly_count`: Current weekly submission count
- `last_daily_reset`: Timestamp of last daily reset
- `last_weekly_reset`: Timestamp of last weekly reset

## Deployment

### Local Development
```bash
uv run python bot.py
```

### Production Deployment

#### Option 1: VPS (Digital Ocean, Linode, etc.)

1. SSH into your server
2. Clone/upload the project
3. Install Python and dependencies
4. Create a systemd service:

```ini
[Unit]
Description=Discord Aim Training Tracker Bot
After=network.target

[Service]
Type=simple
User=your-user
WorkingDirectory=/path/to/discord-bot
ExecStart=/usr/bin/python3 bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

5. Enable and start the service:
```bash
sudo systemctl enable discord-bot
sudo systemctl start discord-bot
```

#### Option 2: Docker

Create a `Dockerfile`:
```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install discord.py python-dotenv APScheduler pytz

COPY . .

CMD ["python", "bot.py"]
```

Build and run:
```bash
docker build -t aim-tracker-bot .
docker run -d --name aim-bot --env-file .env aim-tracker-bot
```

#### Option 3: Cloud Platforms
- Heroku
- Railway
- Render
- AWS EC2

## Troubleshooting

### Bot doesn't respond to commands
- Ensure the bot has proper permissions in the server
- Check that Message Content Intent is enabled in Discord Developer Portal
- Verify the command prefix in `config.json` matches what you're typing

### Bot doesn't track submissions
- Verify `TRACKING_CHANNEL_ID` is correct in `.env`
- Ensure bot can read messages in that channel
- Check bot logs for errors

### Database errors
- Ensure the `data/` directory exists and is writable
- Check file permissions on `tracker.db`
- Look for database errors in bot logs

### Scheduler not working
- Verify timezone in `.env` is valid (use IANA timezone names)
- Check the bot logs for scheduler startup messages
- Ensure the bot stays running continuously

## Logs

Logs are written to:
- Console output (stdout)
- `bot.log` file in the project directory

## Contributing

Feel free to submit issues and enhancement requests!

## License

This project is provided as-is for educational and personal use.

## Support

For issues and questions, please check:
1. This README
2. The project logs (`bot.log`)
3. Discord Developer Documentation

---
