"""Application entry point."""

import os
import sys
from pathlib import Path

# Change to the script's directory so .env is found
script_dir = Path(__file__).parent.resolve()
os.chdir(script_dir)

import uvicorn

from app.config import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


def main() -> None:
    """Run the application."""
    logger.info(
        "Starting server",
        host=settings.host,
        port=settings.port,
        environment=settings.environment,
    )

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower(),
        workers=1 if settings.environment == "development" else 4,
    )


if __name__ == "__main__":
    main()
