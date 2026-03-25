import json
import logging
import os
import re

import arabic_reshaper
from bidi.algorithm import get_display
from telethon import TelegramClient, events

log = logging.getLogger("assistant")

# State management for index-based fetching
RECENT_CHATS = {}

COMMANDS = {
    "/ping": (
        "Check if the assistant is alive.",
        "/ping"
    ),
    "/help": (
        "List all commands with descriptions and examples.",
        "/help"
    ),
    "/find": (
        "Search your channels and groups by keyword.",
        "/find medicine"
    ),
    "/list": (
        "Show [N] most recent target chats/channels (default 15).",
        "/list 5"
    ),
    "/fetch": (
        "Retrieve [N] messages from a list index and save to JSON.",
        "/fetch 1 50"
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

    @on(r"^/find\s+(.+)$")
    async def _(event):
        global RECENT_CHATS
        keyword = event.pattern_match.group(1).strip().lower()
        await event.reply(f"🔍 Searching your dialogs for '{keyword}'...")

        results = []
        RECENT_CHATS.clear()
        count = 1
        
        async for dialog in client.iter_dialogs():
            if keyword in dialog.title.lower():
                RECENT_CHATS[count] = dialog.id
                d_type = "Channel" if dialog.is_channel else "Group" if dialog.is_group else "User"
                results.append(
                    f"**[{count}] {dialog.title}**\n"
                    f"  Type: {d_type}"
                )
                count += 1
                if len(results) >= 15:
                    results.append("... (results truncated to top 15)")
                    break

        if results:
            await event.reply("**Match Results:**\n\n" + "\n\n".join(results))
        else:
            await event.reply(f"❌ No chats found matching '{keyword}'.")

#region List

    @on(r"^/list(?:\s+(\d+))?$")
    async def _(event):
        global RECENT_CHATS
        limit_str = event.pattern_match.group(1)
        limit = int(limit_str) if limit_str else 15
        
        status_msg = await event.reply(f"📂 Fetching top {limit} dialogs...")
        results = []
        RECENT_CHATS.clear()
        
        count = 1
        async for dialog in client.iter_dialogs():
            if dialog.is_channel or dialog.is_group:
                RECENT_CHATS[count] = dialog.id
                d_type = "Channel" if dialog.is_channel else "Group"
                results.append(
                    f"**[{count}] {dialog.title}**\n"
                    f"  Type: {d_type}"
                )
                count += 1
                if count > limit:
                    break
                    
        if not results:
            await status_msg.edit("❌ No groups or channels found.")
            return

        # Chunking to avoid MessageTooLongError (Telegram limit is 4096 chars)
        header = f"**Recent Groups & Channels (Top {limit}):**\n\n"
        chunks = []
        current_chunk = header
        
        for res in results:
            if len(current_chunk) + len(res) + 2 > 4000:
                chunks.append(current_chunk)
                current_chunk = res + "\n\n"
            else:
                current_chunk += res + "\n\n"
        if current_chunk:
            chunks.append(current_chunk)

        # Edit the first message, reply with subsequent chunks if necessary
        await status_msg.edit(chunks[0])
        for chunk in chunks[1:]:
            await event.reply(chunk)

#endregion
#region Fetch

    @on(r"^/fetch\s+(\d+)(?:\s+(\d+))?$")
    async def _(event):
        index_str = event.pattern_match.group(1)
        limit_str = event.pattern_match.group(2)
        
        try:
            index = int(index_str)
            limit = int(limit_str) if limit_str else 100
        except ValueError:
            await event.reply("❌ Invalid format. Use: `/fetch <index> [number]`")
            return

        target_id = RECENT_CHATS.get(index)
        if not target_id:
            await event.reply(f"❌ Index {index} not found. Please run `/list` first.")
            return

        status_msg = await event.reply(f"📥 Fetching last {limit} messages from index {index}...")
        
        try:
            entity = await client.get_entity(target_id)
            chat_title = getattr(entity, 'title', 'Unknown Chat')
            messages = await client.get_messages(entity, limit=limit)
            
            if not messages:
                await status_msg.edit("❌ No messages found or unable to access history.")
                return

            export_dir = "output"
            os.makedirs(export_dir, exist_ok=True)
            filename = os.path.join(export_dir, f"chat_{target_id}_messages.json")
            
            structured_data = []
            
            # Reverse to maintain chronological order (oldest to newest)
            for msg in reversed(messages):
                # 1. Resolve Sender Identity
                sender_id = msg.sender_id
                sender_username = None
                sender_name = "Unknown"
                
                if msg.sender:
                    sender_username = getattr(msg.sender, 'username', None)
                    if sender_username:
                        sender_username = f"@{sender_username}"
                        
                    first = getattr(msg.sender, 'first_name', '') or ''
                    last = getattr(msg.sender, 'last_name', '') or ''
                    full_name = f"{first} {last}".strip()
                    
                    if full_name:
                        sender_name = full_name
                    elif sender_username:
                        sender_name = sender_username
                    else:
                        sender_name = str(sender_id)

                # 2. Construct Deep Link
                chat_id_str = str(target_id)
                deep_link = None
                if chat_id_str.startswith("-100"):
                    clean_id = chat_id_str[4:]
                    deep_link = f"https://t.me/c/{clean_id}/{msg.id}"
                elif getattr(entity, 'username', None):
                    deep_link = f"https://t.me/{entity.username}/{msg.id}"

                # # 3. Handle RTL text formatting (Persian/Arabic)
                # text_content = msg.text if msg.text else ""
                # # \u0600-\u06FF is the Unicode block for Arabic/Persian characters
                # if text_content and re.search(r'[\u0600-\u06FF]', text_content):
                #     reshaped_text = arabic_reshaper.reshape(text_content)
                #     text_content = get_display(reshaped_text)

                # 4. Build Updated JSON Schema
                msg_dict = {
                    "id": msg.id,
                    "timestamp": msg.date.isoformat() if msg.date else None,
                    "chat_title": chat_title,
                    "sender": {
                        "id": sender_id,
                        "username": sender_username,
                        "name": sender_name
                    },
                    "text": msg.text,
                    "reply_to_id": msg.reply_to_msg_id,
                    "media_type": type(msg.media).__name__ if msg.media else None,
                    "deep_link": deep_link
                }
                structured_data.append(msg_dict)

            # Save to JSON file
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(structured_data, f, ensure_ascii=False, indent=2)

            await client.send_message(
                chat_id,
                message=f"✅ **Fetch Complete**\nRetrieved {len(messages)} messages from `{chat_title}`."
            )
            await status_msg.delete()
            log.info("Fetched %d messages from %d into JSON.", len(messages), target_id)

        except Exception as e:
            log.error("Fetch failed for %d: %s", target_id, e, exc_info=True)
            await status_msg.edit(f"❌ Fetch failed: {str(e)}")

#endregion

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