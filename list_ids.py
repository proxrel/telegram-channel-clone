import os
import asyncio
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv(".env")

api_id = int(os.environ["API_ID"])
api_hash = os.environ["API_HASH"]

async def main():
    client = TelegramClient("id_bulucu", api_id, api_hash)

    await client.connect()

    if not await client.is_user_authorized():
        phone = input("Telefon numaran (+90...): ").strip()
        await client.send_code_request(phone)

        code = input("Telegram kodu: ").strip()

        try:
            await client.sign_in(phone, code)
        except Exception as error:
            if error.__class__.__name__ == "SessionPasswordNeededError":
                password = input("2FA parolan: ")
                await client.sign_in(password=password)
            else:
                raise

    print("\n--- Yalnızca grup sohbetleri ---\n")

    grup_sayisi = 0

    async for dialog in client.iter_dialogs():
        if not dialog.is_group:
            continue

        grup_sayisi += 1
        entity = dialog.entity
        username = getattr(entity, "username", None)

        print("-" * 65)
        print(f"Grup adı : {dialog.name}")
        print(f"Grup ID  : {dialog.id}")
        print(f"Username : @{username}" if username else "Username : yok")
        print(f"Tür      : {type(entity).__name__}")

    print("-" * 65)
    print(f"Toplam grup sayısı: {grup_sayisi}")

    await client.disconnect()

if __name__ == "__main__":
    asyncio.run(main())
