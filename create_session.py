import os
import asyncio
from dotenv import load_dotenv
from telethon.sync import TelegramClient
from telethon.tl.types import Dialog

load_dotenv('.env')
API_ID = os.getenv('API_ID')
API_HASH = os.getenv('API_HASH')
SESSION_NAME = 'ai-assistant'

async def main():
    print("Initializing client...")

    # NOTE: The client will create the .session file only on first run
    async with TelegramClient(SESSION_NAME, API_ID, API_HASH) as client:
        print("Client started. Fetching dialogs...")

        output_dir = 'dialogs'
        os.makedirs(output_dir, exist_ok=True)

        dialogs = await client.get_dialogs(limit=10)
        dialog: Dialog
        for dialog in dialogs:
            fp = os.path.join(output_dir, f'Chat[{dialog.id}].txt')
            with open(fp, 'w', encoding='utf-8') as f:
                f.write(dialog.stringify())


if __name__ == "__main__":
    asyncio.run(main())