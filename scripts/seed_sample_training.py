"""
Create a throwaway SQLite database with sample training submissions.

Usage:
    uv run python scripts/seed_sample_training.py /tmp/training_sample.db

Then serve the read-only endpoint against it (no Discord connection needed):
    TRAINING_API_TOKEN=devtoken PORT=8080 uv run python -m handlers.training_api /tmp/training_sample.db

And query it:
    curl -H "Authorization: Bearer devtoken" "http://localhost:8080/training?month=2026-09"

The target file must not exist yet, so this never touches data/tracker.db.
"""

import random
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from database import Database  # noqa: E402

PLAYERS = [
    ("1001", "ghost_aim"), ("1002", "flickmaster"), ("1003", "snd_sniper"),
    ("1004", "hp_anchor"), ("1005", "trackingking"), ("1006", "casual_carl"),
]
# (year, month, days in month) seeded, and how often each player trains (0-1).
MONTHS = [(2026, 7, 31), (2026, 8, 31), (2026, 9, 28)]
DILIGENCE = [0.85, 0.7, 0.55, 0.4, 0.25, 0.08]


def main(path: str):
    if Path(path).exists():
        sys.exit(f"{path} already exists; pass a new path")
    rng = random.Random(42)
    db = Database(path, timezone="America/New_York")
    for discord_id, username in PLAYERS:
        db.add_or_update_player(discord_id, username)
    n = 0
    for year, month, days in MONTHS:
        for (discord_id, _), p in zip(PLAYERS, DILIGENCE):
            for day in range(1, days + 1):
                if rng.random() < p:
                    for _ in range(rng.choice([1, 1, 1, 2, 3])):
                        # 17:00 UTC = afternoon in New York, so the date is unchanged.
                        db.clock = lambda: datetime(year, month, day, 17, 0, tzinfo=timezone.utc)
                        n += 1
                        db.log_submission(discord_id, f"https://example.com/{n}.png", f"{n}.png")
    db.close()
    print(f"Seeded {n} submissions for {len(PLAYERS)} players into {path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
