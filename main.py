import os
import re
import json
import asyncio
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv
from telethon import TelegramClient
from telethon.errors import FloodWaitError

load_dotenv()

API_ID = int(os.getenv('API_ID', '0'))
API_HASH = os.getenv('API_HASH', '')
SESSION_NAME = os.getenv('SESSION_NAME', 'channel_forwarder')
SOURCE = os.getenv('SOURCE_CHANNEL', '')
DEST = os.getenv('DEST_CHANNEL', '')
SECTION_MODE = os.getenv('SECTION_MODE', 'hashtags')
SECTION_REGEX = os.getenv('SECTION_REGEX', r'^(?:#|##)\s*(.+)$')
DRY_RUN = os.getenv('DRY_RUN', 'true').lower() == 'true'
SILENT_FORWARD = os.getenv('SILENT_FORWARD', 'false').lower() == 'true'
RESUME_FILE = os.getenv('RESUME_FILE', 'state.json')
POST_DELAY_SECONDS = float(os.getenv('POST_DELAY_SECONDS', '0.5'))
BATCH_SIZE = int(os.getenv('BATCH_SIZE', '100'))
TOPIC_MODE = os.getenv('TOPIC_MODE', 'false').lower() == 'true'
TOPIC_MAP_FILE = os.getenv('TOPIC_MAP_FILE', 'topic_map.json')

if not API_ID or not API_HASH or not SOURCE or not DEST:
    raise SystemExit('API_ID, API_HASH, SOURCE_CHANNEL ve DEST_CHANNEL zorunlu.')


@dataclass
class ForwardItem:
    source_id: int
    date: str
    text_preview: str
    grouped_id: Optional[int]
    section: Optional[str]
    kind: str
    forwarded: bool = False
    skipped_reason: Optional[str] = None
    dest_id: Optional[int] = None


class SectionTracker:
    def __init__(self, mode: str, pattern: str):
        self.mode = mode
        self.regex = re.compile(pattern, re.MULTILINE)
        self.current: Optional[str] = None

    def update(self, text: str) -> Optional[str]:
        if not text:
            return self.current
        if self.mode == 'hashtags':
            tags = re.findall(r'#([\w\-çğıöşüÇĞİÖŞÜ]+)', text)
            if tags:
                self.current = tags[0]
        elif self.mode == 'regex':
            m = self.regex.search(text.strip())
            if m:
                self.current = m.group(1).strip()
        return self.current


def load_state(path: str) -> Dict[str, Any]:
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {'last_source_id': 0, 'log': []}


def save_state(path: str, state: Dict[str, Any]) -> None:
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


async def ensure_topic(client: TelegramClient, dest, topic_name: str, topic_map: Dict[str, int]) -> Optional[int]:
    if not TOPIC_MODE:
        return None
    if topic_name in topic_map:
        return topic_map[topic_name]
    raise RuntimeError(
        'TOPIC_MODE=true ise topic_map.json içinde bölüm adı -> topic_id eşleşmesi girilmelidir.'
    )


async def main():
    client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
    await client.start()

    source = await client.get_entity(SOURCE)
    dest = await client.get_entity(DEST)

    tracker = SectionTracker(SECTION_MODE, SECTION_REGEX)
    state = load_state(RESUME_FILE)
    topic_map = {}
    if TOPIC_MODE and os.path.exists(TOPIC_MAP_FILE):
        with open(TOPIC_MAP_FILE, 'r', encoding='utf-8') as f:
            topic_map = json.load(f)

    start_after = state.get('last_source_id', 0)
    pending_album: List[Any] = []
    pending_grouped_id = None

    async def flush_album():
        nonlocal pending_album, pending_grouped_id, state
        if not pending_album:
            return

        first = pending_album[0]
        text = (first.raw_text or '').strip()
        section = tracker.update(text)
        item = ForwardItem(
            source_id=first.id,
            date=first.date.isoformat() if isinstance(first.date, datetime) else str(first.date),
            text_preview=text[:120],
            grouped_id=pending_grouped_id,
            section=section,
            kind='album' if len(pending_album) > 1 else 'single_media'
        )

        try:
            if DRY_RUN:
                item.forwarded = False
                item.skipped_reason = 'dry_run'
            else:
                reply_to = await ensure_topic(client, dest, section, topic_map) if section else None
                result = await client.forward_messages(
                    dest,
                    pending_album,
                    silent=SILENT_FORWARD,
                    as_album=True
                )
                if reply_to:
                    item.skipped_reason = f'topic hedefleme için forward yerine resend gerekir; topic_id={reply_to}'
                item.forwarded = True
                if isinstance(result, list) and result:
                    item.dest_id = result[0].id
                elif result is not None and hasattr(result, 'id'):
                    item.dest_id = result.id
                await asyncio.sleep(POST_DELAY_SECONDS)
        except FloodWaitError as e:
            save_state(RESUME_FILE, state)
            raise RuntimeError(f'FloodWait: {e.seconds} saniye beklemen gerekiyor.')
        except Exception as e:
            item.forwarded = False
            item.skipped_reason = str(e)

        state['last_source_id'] = max(state.get('last_source_id', 0), max(m.id for m in pending_album))
        state['log'].append(asdict(item))
        save_state(RESUME_FILE, state)
        pending_album = []
        pending_grouped_id = None

    async for message in client.iter_messages(source, reverse=True, min_id=start_after):
        if not message:
            continue
        gid = getattr(message, 'grouped_id', None)
        has_media = bool(message.media)
        text = (message.raw_text or '').strip()

        if gid:
            if pending_grouped_id is None:
                pending_grouped_id = gid
                pending_album = [message]
            elif gid == pending_grouped_id:
                pending_album.append(message)
            else:
                await flush_album()
                pending_grouped_id = gid
                pending_album = [message]
            continue

        if pending_album:
            await flush_album()

        section = tracker.update(text)
        kind = 'text' if not has_media else 'single_media'
        item = ForwardItem(
            source_id=message.id,
            date=message.date.isoformat() if isinstance(message.date, datetime) else str(message.date),
            text_preview=text[:120],
            grouped_id=None,
            section=section,
            kind=kind
        )

        try:
            if DRY_RUN:
                item.forwarded = False
                item.skipped_reason = 'dry_run'
            else:
                reply_to = await ensure_topic(client, dest, section, topic_map) if section else None
                result = await client.forward_messages(
                    dest,
                    message,
                    silent=SILENT_FORWARD
                )
                if reply_to:
                    item.skipped_reason = f'topic hedefleme için forward yerine resend gerekir; topic_id={reply_to}'
                item.forwarded = True
                if result is not None and hasattr(result, 'id'):
                    item.dest_id = result.id
                await asyncio.sleep(POST_DELAY_SECONDS)
        except FloodWaitError as e:
            save_state(RESUME_FILE, state)
            raise RuntimeError(f'FloodWait: {e.seconds} saniye beklemen gerekiyor.')
        except Exception as e:
            item.forwarded = False
            item.skipped_reason = str(e)

        state['last_source_id'] = max(state.get('last_source_id', 0), message.id)
        state['log'].append(asdict(item))
        save_state(RESUME_FILE, state)

    if pending_album:
        await flush_album()

    await client.disconnect()


if __name__ == '__main__':
    asyncio.run(main())
