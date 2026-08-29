import os
import re
import json
import asyncio
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv
from telethon import TelegramClient, functions, types
from telethon.errors import FloodWaitError

load_dotenv()

API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
SESSION_NAME = os.getenv('SESSION_NAME', 'channel_forwarder')
SOURCE = os.getenv('SOURCE_CHANNEL', '')
DEST = os.getenv('DEST_CHANNEL', '')
DRY_RUN = os.getenv('DRY_RUN', 'true').lower() == 'true'
SILENT_FORWARD = os.getenv('SILENT_FORWARD', 'false').lower() == 'true'
RESUME_FILE = os.getenv('RESUME_FILE', 'state.json')
POST_DELAY_SECONDS = float(os.getenv('POST_DELAY_SECONDS', '0.8'))
TOPIC_MAP_FILE = os.getenv('TOPIC_MAP_FILE', 'topic_map.json')

if not API_ID or not API_HASH or not SOURCE or not DEST:
    raise SystemExit('API_ID, API_HASH, SOURCE_CHANNEL ve DEST_CHANNEL zorunlu.')


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


def load_state(path: str) -> Dict[str, Any]:
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'done_topics': {}, 'log': []}


def save_state(path: str, state: Dict[str, Any]) -> None:
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def load_topic_map(path: str) -> Dict[str, int]:
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}


def save_topic_map(path: str, mapping: Dict[str, int]) -> None:
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(mapping, f, ensure_ascii=False, indent=2)


async def get_forum_topics(client: TelegramClient, dest) -> Dict[str, int]:
    """Hedef grupta zaten var olan konulari isim->id olarak dondurur."""
    result = {}
    try:
        res = await client(functions.channels.GetForumTopicsRequest(
            channel=dest, offset_date=0, offset_id=0, offset_topic=0, limit=100
        ))
        for t in res.topics:
            if hasattr(t, 'title'):
                result[t.title] = t.id
    except Exception:
        pass
    return result


async def ensure_topic(client: TelegramClient, dest, topic_name: str, topic_map: Dict[str, int], topic_map_path: str) -> int:
    """Konu varsa id'sini dondurur, yoksa hedefte forum konusu olusturur."""
    if topic_name in topic_map:
        return topic_map[topic_name]
    result = await client(functions.channels.CreateForumTopicRequest(
        channel=dest,
        title=topic_name[:128],
        icon_color=0x6FB9F0,
        random_id=int.from_bytes(os.urandom(8), 'big', signed=True),
    ))
    new_topic_id = None
    for update in result.updates:
        if isinstance(update, types.UpdateMessageID):
            new_topic_id = update.id
            break
    if new_topic_id is None:
        for update in result.updates:
            if hasattr(update, 'message') and hasattr(update.message, 'id'):
                new_topic_id = update.message.id
                break
    if new_topic_id is None:
        raise RuntimeError(f"Konu olusturulamadi: {topic_name}")
    topic_map[topic_name] = new_topic_id
    save_topic_map(topic_map_path, topic_map)
    await asyncio.sleep(1.0)
    return new_topic_id


async def send_message_to_topic(client: TelegramClient, dest, topic_id: int, message):
    """Mesaji (medya dahil) hedef grubun belirli konusuna gonderir."""
    if message.media:
        return await client.send_file(
            dest,
            message.media,
            caption=message.raw_text or '',
            reply_to=topic_id,
            silent=SILENT_FORWARD,
        )
    else:
        text = message.raw_text or ''
        if not text.strip():
            return None
        return await client.send_message(
            dest,
            text,
            reply_to=topic_id,
            silent=SILENT_FORWARD,
        )


async def main():
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start()

    source = await client.get_entity(SOURCE)
    dest = await client.get_entity(DEST)

    state = load_state(RESUME_FILE)
    done_topics: Dict[str, bool] = state.get('done_topics', {})

    topic_map = load_topic_map(TOPIC_MAP_FILE)
    existing_dest_topics = await get_forum_topics(client, dest)
    for name, tid in existing_dest_topics.items():
        topic_map.setdefault(name, tid)
    save_topic_map(TOPIC_MAP_FILE, topic_map)

    result = await client(functions.channels.GetForumTopicsRequest(
        channel=source, offset_date=0, offset_id=0, offset_topic=0, limit=100
    ))
    source_topics = [t for t in result.topics if hasattr(t, 'title')]

    print(f"Kaynakta {len(source_topics)} konu bulundu.")

    for topic in source_topics:
        topic_name = topic.title
        topic_id_source = topic.id

        if done_topics.get(str(topic_id_source)):
            print(f"Atlaniyor (tamamlanmis): {topic_name}")
            continue

        print(f"Isleniyor: {topic_name}")

        if DRY_RUN:
            print(f"  [DRY_RUN] Konu olusturulacak/kullanilacak: {topic_name}")
        else:
            dest_topic_id = await ensure_topic(client, dest, topic_name, topic_map, TOPIC_MAP_FILE)

        async for message in client.iter_messages(source, reply_to=topic_id_source, reverse=True):
            if not message:
                continue
            if message.action is not None:
                continue

            text = (message.raw_text or '').strip()
            has_media = bool(message.media)
            kind = 'text' if not has_media else 'media'

            item = ForwardItem(
                source_id=message.id,
                topic_id_source=topic_id_source,
                topic_name=topic_name,
                date=message.date.isoformat() if isinstance(message.date, datetime) else str(message.date),
                text_preview=text[:120],
                kind=kind,
            )

            try:
                if DRY_RUN:
                    item.forwarded = False
                    item.skipped_reason = 'dry_run'
                else:
                    sent = await send_message_to_topic(client, dest, dest_topic_id, message)
                    item.forwarded = True
                    if sent is not None and hasattr(sent, 'id'):
                        item.dest_id = sent.id
                    await asyncio.sleep(POST_DELAY_SECONDS)
            except FloodWaitError as e:
                state['done_topics'] = done_topics
                save_state(RESUME_FILE, state)
                raise RuntimeError(f'FloodWait: {e.seconds} saniye beklemen gerekiyor. Sonra scripti tekrar calistir, tamamlanan konular atlanacak.')
            except Exception as e:
                item.forwarded = False
                item.skipped_reason = str(e)

            state.setdefault('log', []).append(asdict(item))
            save_state(RESUME_FILE, state)

        if not DRY_RUN:
            done_topics[str(topic_id_source)] = True
            state['done_topics'] = done_topics
            save_state(RESUME_FILE, state)

    await client.disconnect()
    print('Tamamlandi.')


if __name__ == '__main__':
    asyncio.run(main())
