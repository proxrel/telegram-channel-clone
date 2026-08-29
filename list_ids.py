"""
Group/Channel ID Finder
=========================

Lists every GROUP chat (not channel) your account is a member of.
Use it to find your SOURCE_CHANNEL / DEST_CHANNEL values.

Usage:
    python list_ids.py
"""

import os
import asyncio
from dotenv import load_dotenv
from telethon import TelegramClient

load_dotenv(".env")

API_ID = int(os.environ["API_ID"])
API_HASH = os.environ["API_HASH"]
SESSION_NAME = os.getenv("SESSION_NAME", "channel_forwarder").strip()


async def main():
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)

    await client.connect()

    if not await client.is_user_authorized():
        phone = input("Your phone number (+1...): ").strip()
        await client.send_code_request(phone)

        code = input("Telegram code: ").strip()

        try:
            await client.sign_in(phone, code)
        except Exception as error:
            if error.__class__.__name__ == "SessionPasswordNeededError":
                password = input("Your 2FA password: ")
                await client.sign_in(password=password)
            else:
                raise

    print("\n--- Group chats only ---\n")

    group_count = 0

    async for dialog in client.iter_dialogs():
        if not dialog.is_group:
            continue

        group_count += 1
        entity = dialog.entity
        username = getattr(entity, "username", None)

        print("-" * 65)
        print(f"Group name: {dialog.name}")
        print(f"Group ID  : {dialog.id}")
        print(f"Username  : @{username}" if username else "Username  : none")
        print(f"Type      : {type(entity).__name__}")

    print("-" * 65)
    print(f"Total groups: {group_count}")

    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
