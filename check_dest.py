"""
Hedef Grup Kontrol / Test Scripti
===================================

DEST_CHANNEL'da tanımlı hedef grubun bilgilerini gösterir ve gruba
gerçekten mesaj gönderebildiğinizi doğrulamak için bir test mesajı yollar.

Kullanım:
    python check_dest.py
"""

import os
import asyncio
from dotenv import load_dotenv
from telethon import TelegramClient, functions

load_dotenv(".env")

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "").strip()
SESSION_NAME = os.getenv("SESSION_NAME", "channel_forwarder").strip()
DEST = int(os.getenv("DEST_CHANNEL", "0").strip())


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
