"""
Read-only HTTP endpoint for monthly training stats (used by the cdm_stats dashboard).

GET /training?month=YYYY-MM with "Authorization: Bearer <TRAINING_API_TOKEN>".
The response holds usernames and counts only: no image URLs, filenames, or Discord IDs.
"""

import hmac
import logging
import os
import re
from typing import Optional

from aiohttp import web

logger = logging.getLogger(__name__)

MONTH_RE = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")


def make_app(db, token: str) -> web.Application:
    """Build the aiohttp app that serves /training from the given Database."""

    async def training(request: web.Request) -> web.Response:
        auth = request.headers.get("Authorization", "")
        if not hmac.compare_digest(auth.encode(), f"Bearer {token}".encode()):
            return web.json_response({"error": "unauthorized"}, status=401)

        month = request.query.get("month", "")
        match = MONTH_RE.match(month)
        if not match:
            return web.json_response({"error": "month must be YYYY-MM"}, status=400)

        summary = db.monthly_summary(int(match.group(1)), int(match.group(2)))
        return web.json_response({
            "month": month,
            "months": summary["months"],
            "players": [
                {"username": p["username"], "sessions": p["sessions"], "days_trained": p["days_trained"]}
                for p in summary["players"]
            ],
            "daily": [
                {"date": d["date"], "username": d["username"], "sessions": d["sessions"]}
                for d in summary["daily"]
            ],
        })

    app = web.Application()
    app.router.add_get("/training", training)
    return app


async def start_training_api(bot) -> Optional[web.AppRunner]:
    """
    Start the endpoint on PORT (default 8080) if TRAINING_API_TOKEN is set.
    Stores the runner on bot.training_api_runner so bot.close() can clean it up.
    """
    token = os.getenv("TRAINING_API_TOKEN")
    if not token:
        logger.info("TRAINING_API_TOKEN not set; training API disabled")
        return None

    port = int(os.getenv("PORT", "8080"))
    runner = web.AppRunner(make_app(bot.db, token))
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", port).start()
    bot.training_api_runner = runner
    logger.info(f"Training API listening on port {port}")
    return runner


if __name__ == "__main__":
    # Dev only: serve the endpoint against a database file without Discord.
    # TRAINING_API_TOKEN=devtoken PORT=8080 uv run python -m handlers.training_api <db_path>
    import sys
    from database import Database

    web.run_app(
        make_app(Database(sys.argv[1]), os.environ["TRAINING_API_TOKEN"]),
        port=int(os.getenv("PORT", "8080")),
    )
