"""
Telegram Channel/Group Cloner (Forum/Topic support)
=====================================================

Copies every topic and its messages from a source Telegram group
(a forum/topic-enabled supergroup) to a destination forum group, in order.

See README.md for the usage guide.
"""

import os
import json
import asyncio
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, Dict, Any

from dotenv import load_dotenv
from telethon import TelegramClient, functions, types
from telethon.errors import FloodWaitError, SessionPasswordNeededError
from telethon.tl.types import (
    Channel,
    MessageMediaWebPage,
    MessageMediaPoll,
    MessageMediaGeo,
    MessageMediaGeoLive,
    MessageMediaContact,
    MessageMediaVenue,
    MessageMediaGame,
    MessageMediaUnsupported,
)

load_dotenv(".env")

API_ID = int(os.getenv("API_ID", "0"))
API_HASH = os.getenv("API_HASH", "").strip()
SESSION_NAME = os.getenv("SESSION_NAME", "channel_forwarder").strip()

SOURCE_RAW = os.getenv("SOURCE_CHANNEL", "").strip()
DEST_RAW = os.getenv("DEST_CHANNEL", "").strip()

DRY_RUN = os.getenv("DRY_RUN", "true").strip().lower() == "true"
SILENT_FORWARD = os.getenv("SILENT_FORWARD", "false").strip().lower() == "true"
RESUME_FILE = os.getenv("RESUME_FILE", "state.json").strip()
POST_DELAY_SECONDS = float(os.getenv("POST_DELAY_SECONDS", "0.8"))
TOPIC_MAP_FILE = os.getenv("TOPIC_MAP_FILE", "topic_map.json").strip()

# Media types that don't carry a real file/media (link preview, poll, location, etc.)
# These are sent as plain text rather than as a "real file".
NON_FILE_MEDIA = (
    MessageMediaWebPage,
    MessageMediaPoll,
    MessageMediaGeo,
    MessageMediaGeoLive,
    MessageMediaContact,
    MessageMediaVenue,
    MessageMediaGame,
    MessageMediaUnsupported,
)


def parse_peer(value: str):
    """Converts numeric IDs like '-100123...' to int, leaves @username as-is."""
    value = value.strip()

    if value.lstrip("-").isdigit():
        return int(value)

    return value


SOURCE = parse_peer(SOURCE_RAW)
DEST = parse_peer(DEST_RAW)

if not API_ID or not API_HASH or not SOURCE_RAW or not DEST_RAW:
    raise SystemExit(
        "API_ID, API_HASH, SOURCE_CHANNEL and DEST_CHANNEL are required. "
        "Check your .env file (see .env.example)."
    )


@dataclass
class ForwardItem:
    source_id: int
    topic_id_source: Optional[int]
    topic_name: Optional[str]
    date: str
    text_preview: str
    kind: str
    forwarded: bool = False
    skipped_reason: Optional[str] = None
    dest_id: Optional[int] = None


def load_json(path: str, default):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as file:
                return json.load(file)
        except (OSError, json.JSONDecodeError):
            print(f"Warning: could not read {path}; using default value.")

    return default


def save_json(path: str, data) -> None:
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def load_state(path: str) -> Dict[str, Any]:
    return load_json(
        path,
        {"done_topics": {}, "done_messages": {}, "log": []},
    )


def save_state(path: str, state: Dict[str, Any]) -> None:
    save_json(path, state)


def load_topic_map(path: str) -> Dict[str, int]:
    return load_json(path, {})


def save_topic_map(path: str, mapping: Dict[str, int]) -> None:
    save_json(path, mapping)


async def login_if_needed(client: TelegramClient) -> None:
    """Prompts for phone/code/2FA if there's no session file yet, or it's invalid."""
    await client.connect()

    if await client.is_user_authorized():
        return

    phone = input("Your phone number (+1...): ").strip()
    await client.send_code_request(phone)

    code = input("Telegram code: ").strip()

    try:
        await client.sign_in(phone=phone, code=code)
    except SessionPasswordNeededError:
        password = input("Your 2FA password: ")
        await client.sign_in(password=password)


async def find_dialog(
    client: TelegramClient,
    wanted_id: int,
    label: str,
):
    async for dialog in client.iter_dialogs():
        if dialog.id == wanted_id:
            return dialog

    raise RuntimeError(
        f"{label} not found: {wanted_id}. "
        "Make sure the account is a member of the group and the ID is correct."
    )


async def get_source_topics(client: TelegramClient, source):
    try:
        response = await client(
            functions.channels.GetForumTopicsRequest(
                channel=source,
                offset_date=0,
                offset_id=0,
                offset_topic=0,
                limit=100,
            )
        )
    except Exception as error:
        raise RuntimeError(
            "Could not read forum topics from the source group. "
            "Make sure the source group is a supergroup with Topics/Forum enabled."
        ) from error

    return [topic for topic in response.topics if hasattr(topic, "title")]


async def get_dest_topics(client: TelegramClient, destination) -> Dict[str, int]:
    """Returns the destination's existing topics as name -> topic_id."""
    result: Dict[str, int] = {}

    try:
        response = await client(
            functions.channels.GetForumTopicsRequest(
                channel=destination,
                offset_date=0,
                offset_id=0,
                offset_topic=0,
                limit=100,
            )
        )

        for topic in response.topics:
            if hasattr(topic, "title"):
                result[topic.title] = topic.id

    except Exception:
        pass

    return result


async def ensure_dest_topic(
    client: TelegramClient,
    destination,
    topic_name: str,
    topic_map: Dict[str, int],
    topic_map_path: str,
) -> int:
    """Returns the topic's ID if it already exists at the destination; otherwise creates it."""
    if topic_name in topic_map:
        return topic_map[topic_name]

    response = await client(
        functions.channels.CreateForumTopicRequest(
            channel=destination,
            title=topic_name[:128],
            icon_color=0x6FB9F0,
            random_id=int.from_bytes(os.urandom(8), "big", signed=True),
        )
    )

    new_topic_id = None

    for update in response.updates:
        if isinstance(update, types.UpdateMessageID):
            new_topic_id = update.id
            break

    if new_topic_id is None:
        for update in response.updates:
            message = getattr(update, "message", None)
            if message is not None and hasattr(message, "id"):
                new_topic_id = message.id
                break

    if new_topic_id is None:
        raise RuntimeError(f"Could not create topic at destination: {topic_name}")

    topic_map[topic_name] = new_topic_id
    save_topic_map(topic_map_path, topic_map)

    await asyncio.sleep(1.0)

    return new_topic_id


async def send_content(
    client: TelegramClient,
    destination,
    dest_topic_id: int,
    message,
):
    text = message.raw_text or ""
    has_real_file_media = bool(message.media) and not isinstance(
        message.media, NON_FILE_MEDIA
    )

    if has_real_file_media:
        return await client.send_file(
            entity=destination,
            file=message.media,
            caption=text,
            reply_to=dest_topic_id,
            silent=SILENT_FORWARD,
        )

    if not text.strip():
        return None

    return await client.send_message(
        entity=destination,
        message=text,
        reply_to=dest_topic_id,
        silent=SILENT_FORWARD,
    )


async def main():
    if not isinstance(SOURCE, int):
        raise RuntimeError(
            "SOURCE_CHANNEL must be a numeric source group ID (e.g. -100123456789)."
        )

    if not isinstance(DEST, int):
        raise RuntimeError(
            "DEST_CHANNEL must be a numeric destination group ID (e.g. -100123456789)."
        )

    print("Preparing the Telegram connection...")
    print(f"Source: {SOURCE}")
    print(f"Destination: {DEST}")
    print(f"DRY_RUN: {DRY_RUN}")
    print()

    async with TelegramClient(SESSION_NAME, API_ID, API_HASH) as client:
        await login_if_needed(client)

        source_dialog = await find_dialog(client, SOURCE, "Source group")
        destination_dialog = await find_dialog(client, DEST, "Destination group")

        source = source_dialog.entity
        destination = destination_dialog.entity

        if not isinstance(source, Channel):
            raise RuntimeError("The source group must be a Channel/supergroup.")

        if not isinstance(destination, Channel) or not getattr(
            destination, "forum", False
        ):
            raise RuntimeError(
                "The destination group must be a supergroup with Topics/Forum enabled."
            )

        print("Source and destination found successfully.")
        print(f"Source name: {source_dialog.name}")
        print(f"Destination name: {destination_dialog.name}")
        print(f"Destination forum: {destination.forum}")

        state = load_state(RESUME_FILE)
        done_topics = state.setdefault("done_topics", {})
        done_messages = state.setdefault("done_messages", {})

        topic_map = load_topic_map(TOPIC_MAP_FILE)

        existing_dest_topics = await get_dest_topics(client, destination)
        for name, topic_id in existing_dest_topics.items():
            topic_map.setdefault(name, topic_id)
        save_topic_map(TOPIC_MAP_FILE, topic_map)

        source_topics = await get_source_topics(client, source)

        print(f"Found {len(source_topics)} topics in the source.")

        for topic in source_topics:
            topic_name = topic.title
            source_topic_id = topic.id
            topic_key = str(source_topic_id)

            if done_topics.get(topic_key):
                print(f"Skipping (already done): {topic_name}")
                continue

            print(f"\nProcessing: {topic_name}")

            if DRY_RUN:
                dest_topic_id = None
                print(
                    f"  [DRY_RUN] Topic to use/create at destination: "
                    f"{topic_name}"
                )
            else:
                try:
                    dest_topic_id = await ensure_dest_topic(
                        client,
                        destination,
                        topic_name,
                        topic_map,
                        TOPIC_MAP_FILE,
                    )
                    print(f"  Destination topic ID: {dest_topic_id}")

                except FloodWaitError as error:
                    save_state(RESUME_FILE, state)
                    raise RuntimeError(
                        f"FloodWait: you need to wait {error.seconds} seconds."
                    ) from error

                except Exception as error:
                    raise RuntimeError(
                        f"Could not create topic at destination: {topic_name}. Error: {error}"
                    ) from error

            message_count = 0
            sent_count = 0
            skipped_count = 0

            async for message in client.iter_messages(
                source,
                reply_to=source_topic_id,
                reverse=True,
            ):
                if not message or message.action is not None:
                    continue

                message_count += 1
                message_key = f"{source_topic_id}:{message.id}"

                text = (message.raw_text or "").strip()
                kind = "media" if message.media else "text"

                item = ForwardItem(
                    source_id=message.id,
                    topic_id_source=source_topic_id,
                    topic_name=topic_name,
                    date=(
                        message.date.isoformat()
                        if isinstance(message.date, datetime)
                        else str(message.date)
                    ),
                    text_preview=text[:120],
                    kind=kind,
                )

                if done_messages.get(message_key):
                    skipped_count += 1
                    print(f"  Skipping (already sent): #{message.id}")
                    continue

                if DRY_RUN:
                    item.skipped_reason = "dry_run"
                    print(
                        f"  [DRY_RUN] #{message.id} | {kind} | {text[:80]!r}"
                    )
                else:
                    try:
                        sent = await send_content(
                            client,
                            destination,
                            dest_topic_id,
                            message,
                        )

                        item.forwarded = True

                        if sent is not None and hasattr(sent, "id"):
                            item.dest_id = sent.id

                        done_messages[message_key] = True
                        sent_count += 1

                        await asyncio.sleep(POST_DELAY_SECONDS)

                    except FloodWaitError as error:
                        save_state(RESUME_FILE, state)
                        raise RuntimeError(
                            f"FloodWait: you need to wait {error.seconds} seconds. "
                            "You can run the same command again once it's over."
                        ) from error

                    except Exception as error:
                        item.forwarded = False
                        item.skipped_reason = str(error)
                        print(
                            f"  [ERROR] Could not send message #{message.id}: {error}"
                        )

                state.setdefault("log", []).append(asdict(item))
                save_state(RESUME_FILE, state)

            print(
                f"  Total messages in topic: {message_count} | "
                f"Sent: {sent_count} | Skipped: {skipped_count}"
            )

            if not DRY_RUN:
                done_topics[topic_key] = True
                save_state(RESUME_FILE, state)

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
