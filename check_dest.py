import os
import asyncio

from dotenv import load_dotenv, set_key
from telethon import TelegramClient, functions

ENV_PATH = ".env"
load_dotenv(ENV_PATH)


def ask_and_remember(env_key: str, question: str) -> str:
    value = os.getenv(env_key, "").strip()
    if value:
        return value

    while not value:
        value = input(question).strip()

    set_key(ENV_PATH, env_key, value)
    return value


API_ID = int(
    ask_and_remember("API_ID", "API_ID (my.telegram.org üzerinden alınır): ")
)
API_HASH = ask_and_remember(
    "API_HASH", "API_HASH (my.telegram.org üzerinden alınır): "
)
DEST_RAW = ask_and_remember(
    "DEST_CHANNEL",
    "Hedef grup ID'si (-100... ile başlayan sayı, list_ids.py ile bulabilirsin): ",
)
DEST = int(DEST_RAW)
SESSION_NAME = os.getenv("SESSION_NAME", "channel_forwarder").strip()


async def main():
    async with TelegramClient(SESSION_NAME, API_ID, API_HASH) as client:
        dialog = None
        async for d in client.iter_dialogs():
            if d.id == DEST:
                dialog = d
                break

        if dialog is None:
            print("Hedef dialoglarda bulunamadı.")
            return

        entity = dialog.entity
        print("Ad:", dialog.name)
        print("ID:", dialog.id)
        print("Tür:", type(entity).__name__)
        print("Ham entity:", entity)

        chat_id = abs(entity.id)
        try:
            full = await client(functions.messages.GetFullChatRequest(chat_id=chat_id))
            chat = full.chats[0]
            print("\n--- Tam grup bilgisi ---")
            print("deactivated:", getattr(chat, "deactivated", None))
            print("migrated_to:", getattr(chat, "migrated_to", None))
            print("left:", getattr(chat, "left", None))
            print("kicked:", getattr(chat, "kicked", None))
        except Exception as error:
            print("GetFullChatRequest hatası:", error)

        try:
            test_msg = await client.send_message(entity, "🔧 test mesajı")
            print("\nTest mesajı GÖNDERİLDİ. Mesaj ID:", test_msg.id)
        except Exception as error:
            print("\nTest mesajı BAŞARISIZ:", error)


if __name__ == "__main__":
    asyncio.run(main())
