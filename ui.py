
import logging

from telethon import TelegramClient
from telethon.tl.functions.messages import CreateChatRequest

log = logging.getLogger("assistant")
UI_TITLE = "🤖 AI Insight Assistant"

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
