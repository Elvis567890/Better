"""Entrypoint for GitHub Actions."""
import asyncio
import logging
import os

from .brain import Boat

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)


def main():
    cmd = os.environ.get("BOAT_CMD") or "make money anywhere today"
    chat = os.environ.get("BOAT_CHAT") or None
    asyncio.run(Boat().handle(cmd, source="github", reply_to=chat))


if __name__ == "__main__":
    main()
