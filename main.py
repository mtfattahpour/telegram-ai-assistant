import asyncio
import logging
import os
import sys

from dotenv import load_dotenv
from telethon import TelegramClient

from ui import get_or_create_ui_group
from handlers import register_handlers

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="[{asctime}][{levelname}]: {message}",
    style='{',
    datefmt="%H:%M:%S",
)
log = logging.getLogger("assistant")

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION = "ai-assistant"

async def main() -> None:
    client = TelegramClient(SESSION, API_ID, API_HASH)
    try:
        await client.start()
        me = await client.get_me()
        log.info("Authenticated as %s (id=%d).", me.username or me.first_name, me.id)

        chat_id = await get_or_create_ui_group(client)
        register_handlers(client, chat_id)

        await client.send_message(
            chat_id,
            "✅ **Assistant online.** Type `/help` for commands."
        )
        log.info("Listening for commands…")
        await client.run_until_disconnected()

    except asyncio.exceptions.CancelledError:
        log.info("Interrupted.")
    except Exception as e:
        log.critical("Fatal: %s", e, exc_info=True)
        sys.exit(1)
    finally:
        if client.is_connected():
            await client.disconnect()
        log.info("Disconnected.")

if __name__ == "__main__":
    asyncio.run(main())