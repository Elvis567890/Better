import asyncio, os
from .brain import Boat

def main():
    cmd = os.environ.get("BOAT_CMD") or "make money anywhere today"
    chat = os.environ.get("BOAT_CHAT") or None
    asyncio.run(Boat().handle(cmd, source="github", reply_to=chat))

if __name__ == "__main__":
    main()
