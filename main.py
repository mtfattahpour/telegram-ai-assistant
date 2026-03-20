
import asyncio
import logging
import os
import sys

from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.tl.functions.messages import CreateChatRequest
from telethon.tl.types import InputPeerChat

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
UI_TITLE = "🤖 AI Insight Assistant"

COMMANDS = {
    "/ping": (
        "Check if the assistant is alive.",
        "/ping"
    ),
    "/help": (
        "List all commands with descriptions and examples.",
        "/help"
    ),
    "/list": (
        "Show configured target chats/channels.",
        "/list"
    ),
    "/clean": (
        "Wipe all messages in this UI group.",
        "/clean"
    ),
    "/stop": (
        "Gracefully shut down the assistant.",
        "/stop"
    ),
}


#region Interface Chat

async def get_or_create_ui_group(client: TelegramClient) -> int:
    """Return the UI group chat ID, create the group if it doesn't exist."""

    # Search existing dialogs first to avoid creating duplicates.
    async for dialog in client.iter_dialogs():
        if dialog.is_group and dialog.title == UI_TITLE:
            log.info("Found existing UI group (id=%d).", dialog.id)
            return dialog.id

    log.info("UI group not found — creating '%s'.", UI_TITLE)

    # NOTE: CreateChatRequest requires at least one other user.
    # @SpamBot is Telegram's own bot and resolves as a proper User entity.
    placeholder = await client.get_entity("SpamBot")
    await client(CreateChatRequest(users=[placeholder], title=UI_TITLE))

    # The return type of CreateChatRequest varies across Telethon versions, so
    # we re-scan dialogs instead of parsing the result; guaranteed to work.
    async for dialog in client.iter_dialogs():
        if dialog.is_group and dialog.title == UI_TITLE:
            # Remove the placeholder immediately; only needed to satisfy the API.
            try:
                await client.kick_participant(dialog.id, placeholder)
            except Exception as e:
                log.warning("Could not remove placeholder user: %s", e)
            log.info("UI group created (id=%d).", dialog.id)
            return dialog.id

    raise RuntimeError(f"Group '{UI_TITLE}' was not found in dialogs after creation.")

#endregion
#region Handlers

def register_handlers(client: TelegramClient, chat_id: int) -> None:
    """Attach all command handlers, scoped exclusively to the UI group."""

    def on(pattern: str = None):
        return client.on(events.NewMessage(chats=(chat_id,), pattern=pattern))

    @on(r"^/ping$")
    async def _(event):
        await event.reply("Pong! Assistant is active.")

    @on(r"^/help$")
    async def _(event):
        lines = ["**🤖 AI Insight Assistant — Commands**\n"]
        for command, (description, example) in COMMANDS.items():
            lines.append(f"**{command}**: {description}\n  📌 `{example}`\n")
        await event.reply("\n".join(lines))

    @on(r"^/list$")
    async def _(event):
        await event.reply(
            "List command received\n"
            "Target chat discovery will be implemented in the next update."
        )

    @on(r"^/clean$")
    async def _(event):
        try:
            ids = [msg.id async for msg in client.iter_messages(chat_id)]
            for i in range(0, len(ids), 100):
                await client.delete_messages(chat_id, ids[i:i + 100])
            await client.send_message(
                chat_id,
                "✅ **Assistant online.** Type `/help` for commands."
            )
        except Exception as e:
            await event.reply(f"❌ Clean failed: {e}")

    @on(r"^/stop$")
    async def _(event):
        await event.reply("🛑 Shutting down gracefully...")
        await client.disconnect()

    # @on()   # no pattern, catches everything
    # async def _(event):
    #     await event.reply(
    #         f"❓ Unknown command `{event.text}`.\nType `/help` to see available commands.",
    #     )

    log.info("Handlers registered on chat_id=%d.", chat_id)

#endregion
#region Main

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