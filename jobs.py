from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from tg_time_logger.config import load_settings
from tg_time_logger.db import Database
from tg_time_logger.jobs_runner import run_job
from tg_time_logger.logging_setup import setup_logging


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python jobs.py <sunday_summary|reminders|midweek|check_quests>")

    setup_logging()
    settings = load_settings()
    db = Database(settings.database_path)
    run_job(sys.argv[1], db, settings)


if __name__ == "__main__":
    main()
