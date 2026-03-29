import asyncio
import json
import logging
import os

from dotenv import load_dotenv
from google import genai
from telethon import TelegramClient, events

log = logging.getLogger("assistant")

load_dotenv()

# State management for index-based fetching
RECENT_CHATS = {}

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
genai_client = genai.Client(api_key=GEMINI_API_KEY)

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
    "/ask": (
        "Ask a question based on the last 1000 messages of a target chat.",
        "/ask 1 What are the latest treatment protocols?"
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
#region Ask

    @on(r"^/ask\s+(\d+)\s+([\s\S]+)$")
    async def _(event):
        if not genai_client:
            await event.reply("❌ Gemini API key is missing. Please configure GEMINI_API_KEY in your .env file.")
            return

        index_str = event.pattern_match.group(1)
        question = event.pattern_match.group(2).strip()
        
        try:
            index = int(index_str)
        except ValueError:
            await event.reply("❌ Invalid format. Use: `/ask <index> <question>`")
            return

        target_id = RECENT_CHATS.get(index)
        if not target_id:
            await event.reply(f"❌ Index {index} not found. Please run `/list` or `/find` first.")
            return

        status_msg = await event.reply(f"📥 Fetching message history from index {index} (safeguarded by token limits)...")
        
        try:
            entity = await client.get_entity(target_id)
            chat_title = getattr(entity, 'title', 'Unknown Chat')
            
            # Determine Base Link for Citations upfront to pass to Gemini
            chat_id_str = str(target_id)
            base_link = ""
            if chat_id_str.startswith("-100"):
                clean_id = chat_id_str[4:]
                base_link = f"https://t.me/c/{clean_id}/"
            elif getattr(entity, 'username', None):
                base_link = f"https://t.me/{entity.username}/"
            else:
                base_link = "https://t.me/c/0/" # Fallback if unroutable

            # Fetch a large buffer (up to 3000), but we will slice it based on character count 
            # to avoid the 429 Token limit before building the JSON schema or prompt.
            messages = await client.get_messages(entity, limit=3000)
            
            if not messages:
                await status_msg.edit("❌ No messages found or unable to access history.")
                return

            # Safeguard: Limit context to ~300,000 characters (approx 75k-100k tokens, well under the 250k free tier limit)
            MAX_CHARS = 300_000
            total_chars = 0
            valid_messages = []
            
            # Iterate newest to oldest to keep the most recent context, stopping when limit is reached
            for msg in messages:
                text_len = len(msg.text) if msg.text else 0
                if total_chars + text_len > MAX_CHARS:
                    log.info("Token safeguard triggered: stopping at %d messages.", len(valid_messages))
                    break
                valid_messages.append(msg)
                total_chars += text_len

            # Reverse to chronological order (oldest -> newest) for the AI prompt and JSON output
            valid_messages.reverse()

            export_dir = "output"
            os.makedirs(export_dir, exist_ok=True)
            filename = os.path.join(export_dir, f"chat_{target_id}_messages.json")
            
            structured_data = []
            ai_context_lines = []
            
            for msg in valid_messages:
                # Resolve Sender Identity
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

                deep_link = f"{base_link}{msg.id}" if base_link != "https://t.me/c/0/" else None
                text_content = msg.text if msg.text else ""

                # Build Updated JSON Schema
                msg_dict = {
                    "id": msg.id,
                    "timestamp": msg.date.isoformat() if msg.date else None,
                    "chat_title": chat_title,
                    "sender": {
                        "id": sender_id,
                        "username": sender_username,
                        "name": sender_name
                    },
                    "text": text_content,
                    "reply_to_id": msg.reply_to_msg_id,
                    "media_type": type(msg.media).__name__ if msg.media else None,
                    "deep_link": deep_link
                }
                structured_data.append(msg_dict)

                # Append to AI context strictly mapped by message ID to save context window
                if text_content:
                    ai_context_lines.append(f"[ID: {msg.id}] {text_content}")

            # Save to JSON file locally
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(structured_data, f, ensure_ascii=False, indent=2)

            await status_msg.edit(f"🧠 History retrieved ({len(valid_messages)} messages analyzed). Querying generative AI; please wait...")
            log.info("Querying Gemini for chat %d with %d contextual messages.", target_id, len(ai_context_lines))

            context_text = "\n".join(ai_context_lines)
            prompt = f"""
            You are a highly capable AI Assistant extracting knowledge from Telegram chats. 
            The user has asked a question. You must answer it based STRICTLY on the provided Chat History.

            User Question: "{question}"
            Base Link for Citations: {base_link}

            Directives:
            1. Safety: If the question is unsafe or inappropriate, politely decline to answer.
            2. Answerability: Determine if the answer actually exists within the Chat History. If the data is insufficient, clearly state that the information is not available in the recent messages. Do not hallucinate outside knowledge.
            3. Synthesis: If answerable, synthesize a condensed, accurate, and thorough answer based only on the provided history.
            4. Citation: You MUST cite the most pertinent messages, if any, to prove your claims. To cite, strictly use the markdown format: `[Citation Text](Base Link + ID)`. For example, to cite ID 1234, write `[Message 1234]({base_link}1234)`.
            5. Language: You MUST write your final response ENTIRELY IN ENGLISH, regardless of the language of the user's question or the chat history.

            Chat History (Format: [ID: <id>] <message content>):
            {context_text}
            """

            with open(os.path.join(export_dir, 'prompt.txt'), 'w', encoding='utf-8') as f:
                f.write(prompt)

            with open(os.path.join(export_dir, 'context.txt'), 'w', encoding='utf-8') as f:
                f.write(context_text)

            # Execute synchronous Gemini call in a separate thread
            response = await asyncio.to_thread(
                genai_client.models.generate_content,
                model="gemini-3-flash-preview",
                contents=prompt
            )

            final_text = response.text

            # Chunking the response in case Gemini generates a message longer than 4096 chars
            if len(final_text) > 4000:
                chunks = [final_text[i:i+4000] for i in range(0, len(final_text), 4000)]
                await status_msg.edit(chunks[0])
                for chunk in chunks[1:]:
                    await event.reply(chunk)
            else:
                await status_msg.edit(final_text)

        except Exception as e:
            log.error("Ask failed for %d: %s", target_id, e, exc_info=True)
            await status_msg.edit(f"❌ Ask command failed: {str(e)}")

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