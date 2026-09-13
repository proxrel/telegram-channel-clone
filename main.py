import os
import json
import asyncio
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Optional, Dict, Any, List

from dotenv import load_dotenv, set_key
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

ENV_PATH = ".env"

# .env dosyası varsa yükle; yoksa sorun değil, eksik bilgiler aşağıda
# kullanıcıya sorulup otomatik olarak bu dosyaya kaydedilecek.
load_dotenv(ENV_PATH)


def ask_and_remember(env_key: str, question: str) -> str:
    """
    env_key .env dosyasında (veya ortam değişkenlerinde) zaten varsa onu
    kullanır. Yoksa kullanıcıya sorar ve bir daha sorulmaması için .env
    dosyasına yazar.
    """
    value = os.getenv(env_key, "").strip()
    if value:
        return value

    while not value:
        value = input(question).strip()

    set_key(ENV_PATH, env_key, value)
    return value


print("=== Telegram Forum Klonlayıcı ===")
print("İlk çalıştırmada birkaç bilgi soracağım; bir daha sorulmaması için")
print(f"otomatik olarak {ENV_PATH} dosyasına kaydedeceğim.\n")

API_ID_RAW = ask_and_remember(
    "API_ID",
    "API_ID (my.telegram.org üzerinden alınır): ",
)
API_HASH = ask_and_remember(
    "API_HASH",
    "API_HASH (my.telegram.org üzerinden alınır): ",
)
SOURCE_RAW = ask_and_remember(
    "SOURCE_CHANNEL",
    "Kaynak grup (@kullaniciadi ya da -100... ile başlayan ID): ",
)
DEST_RAW = ask_and_remember(
    "DEST_CHANNEL",
    "Hedef grup (@kullaniciadi ya da -100... ile başlayan ID): ",
)

try:
    API_ID = int(API_ID_RAW)
except ValueError:
    raise SystemExit("API_ID sayısal bir değer olmalı.")

SESSION_NAME = os.getenv("SESSION_NAME", "channel_forwarder").strip()
DRY_RUN = os.getenv("DRY_RUN", "true").strip().lower() == "true"
SILENT_FORWARD = os.getenv("SILENT_FORWARD", "false").strip().lower() == "true"
RESUME_FILE = os.getenv("RESUME_FILE", "state.json").strip()
POST_DELAY_SECONDS = float(os.getenv("POST_DELAY_SECONDS", "0.8"))
TOPIC_MAP_FILE = os.getenv("TOPIC_MAP_FILE", "topic_map.json").strip()
TOPIC_PAGE_SIZE = min(max(int(os.getenv("TOPIC_PAGE_SIZE", "100")), 1), 100)

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
    value = value.strip()
    if value.lstrip("-").isdigit():
        return int(value)
    return value


SOURCE = parse_peer(SOURCE_RAW)
DEST = parse_peer(DEST_RAW)


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
            print(f"Uyarı: {path} okunamadı; varsayılan değer kullanılıyor.")
    return default


def save_json(path: str, data) -> None:
    with open(path, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)


def load_state(path: str) -> Dict[str, Any]:
    return load_json(
        path,
        {
            "done_topics": {},
            "done_messages": {},
            "log": [],
        },
    )


def save_state(path: str, state: Dict[str, Any]) -> None:
    save_json(path, state)


def load_topic_map(path: str) -> Dict[str, int]:
    raw = load_json(path, {})
    if not isinstance(raw, dict):
        return {}
    result = {}
    for name, topic_id in raw.items():
        try:
            result[str(name)] = int(topic_id)
        except (TypeError, ValueError):
            continue
    return result


def save_topic_map(path: str, mapping: Dict[str, int]) -> None:
    save_json(path, mapping)


async def login_if_needed(client: TelegramClient) -> None:
    await client.connect()
    if await client.is_user_authorized():
        return

    phone = input("Telefon numaran (+90...): ").strip()
    await client.send_code_request(phone)
    code = input("Telegram kodu: ").strip()
    try:
        await client.sign_in(
            phone=phone,
            code=code,
        )
    except SessionPasswordNeededError:
        password = input("2FA parolan: ")
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
        f"{label} bulunamadı: {wanted_id}. "
        "Hesabın gruba üye olduğundan ve ID'nin doğru olduğundan emin ol."
    )


def get_forum_topics_request_class():
    """
    Telethon sürümüne göre forum konu listeleme isteğini bulur.
    Güncel Telethon: functions.messages.GetForumTopicsRequest
    Eski olası şema: functions.channels.GetForumTopicsRequest
    """
    request_class = getattr(
        functions.messages,
        "GetForumTopicsRequest",
        None,
    )
    if request_class is not None:
        return request_class

    request_class = getattr(
        functions.channels,
        "GetForumTopicsRequest",
        None,
    )
    if request_class is not None:
        return request_class

    raise RuntimeError(
        "Kurulu Telethon paketinde GetForumTopicsRequest bulunamadı.\n"
        "Terminalde sırasıyla şunları çalıştır:\n"
        "python -m pip uninstall telethon -y\n"
        "python -m pip install --no-cache-dir --upgrade telethon"
    )


def get_create_forum_topic_request_class():
    """
    Güncel Telegram API şemasında konu oluşturma:
    functions.messages.CreateForumTopicRequest
    """
    request_class = getattr(
        functions.messages,
        "CreateForumTopicRequest",
        None,
    )
    if request_class is not None:
        return request_class

    request_class = getattr(
        functions.channels,
        "CreateForumTopicRequest",
        None,
    )
    if request_class is not None:
        return request_class

    raise RuntimeError(
        "Kurulu Telethon paketinde CreateForumTopicRequest bulunamadı.\n"
        "Terminalde şunu çalıştır:\n"
        "python -m pip install --no-cache-dir --upgrade telethon"
    )


async def get_all_forum_topics(
    client: TelegramClient,
    entity,
) -> List[Any]:
    """
    Forum grubundaki konu başlıklarını alır.
    Önemli: Bu Telethon şemasında parametre adı 'channel' değil 'peer'dir.
    """
    if not isinstance(entity, Channel):
        return []
    if not getattr(entity, "forum", False):
        return []

    request_class = get_forum_topics_request_class()

    all_topics: List[Any] = []
    seen_topic_ids = set()
    offset_date = 0
    offset_id = 0
    offset_topic = 0

    while True:
        try:
            response = await client(
                request_class(
                    peer=entity,
                    offset_date=offset_date,
                    offset_id=offset_id,
                    offset_topic=offset_topic,
                    limit=TOPIC_PAGE_SIZE,
                    q=None,
                )
            )
        except FloodWaitError:
            raise
        except Exception as error:
            raise RuntimeError(
                "Forum konuları okunamadı. "
                "Grubun Topics/Forum özelliğinin açık, hesabının gruba üye "
                "ve erişim yetkisinin yeterli olduğundan emin ol. "
                f"Asıl hata: {type(error).__name__}: {error}"
            ) from error

        page_topics = [
            topic
            for topic in getattr(response, "topics", [])
            if hasattr(topic, "id") and hasattr(topic, "title")
        ]
        if not page_topics:
            break

        newly_added_count = 0
        for topic in page_topics:
            if topic.id not in seen_topic_ids:
                seen_topic_ids.add(topic.id)
                all_topics.append(topic)
                newly_added_count += 1

        if len(page_topics) < TOPIC_PAGE_SIZE:
            break
        if newly_added_count == 0:
            break

        last_topic = page_topics[-1]
        offset_date = getattr(last_topic, "date", 0) or 0
        offset_id = 0
        offset_topic = last_topic.id

    return all_topics


async def get_source_topics(
    client: TelegramClient,
    source,
) -> List[Any]:
    if not getattr(source, "forum", False):
        raise RuntimeError(
            "Kaynak grup Topics/Forum açık bir süpergrup değil. "
            "Forum olmayan kaynak gruptan konu bazlı kopyalama yapılamaz."
        )
    return await get_all_forum_topics(client, source)


async def get_dest_topics(
    client: TelegramClient,
    destination,
) -> Dict[str, int]:
    """
    Hedef gruptaki mevcut konuları döndürür.
    Sonuç formatı: {"Konu adı": topic_id}
    """
    result: Dict[str, int] = {}
    if not getattr(destination, "forum", False):
        return result

    topics = await get_all_forum_topics(client, destination)
    for topic in topics:
        result[topic.title] = topic.id
    return result


async def ensure_dest_topic(
    client: TelegramClient,
    destination,
    topic_name: str,
    topic_map: Dict[str, int],
    topic_map_path: str,
) -> int:
    """
    Hedefte aynı isimli topic varsa onun ID'sini verir.
    Yoksa hedef forum grubunda yeni topic oluşturur.
    """
    if topic_name in topic_map:
        return topic_map[topic_name]

    create_request = get_create_forum_topic_request_class()
    try:
        response = await client(
            create_request(
                peer=destination,
                title=topic_name[:128],
                icon_color=0x6FB9F0,
                random_id=int.from_bytes(
                    os.urandom(8),
                    "big",
                    signed=True,
                ),
            )
        )
    except FloodWaitError:
        raise
    except Exception as error:
        raise RuntimeError(
            f"Yeni hedef konusu oluşturulamadı: {topic_name}. "
            f"Asıl hata: {type(error).__name__}: {error}"
        ) from error

    new_topic_id = None
    for update in getattr(response, "updates", []):
        message = getattr(update, "message", None)
        if message is not None and getattr(message, "id", None):
            new_topic_id = message.id
            break

    if new_topic_id is None:
        for update in getattr(response, "updates", []):
            if isinstance(update, types.UpdateMessageID):
                new_topic_id = update.id
                break

    if new_topic_id is None:
        raise RuntimeError(
            f"Hedefte konu oluşturuldu ancak topic ID okunamadı: {topic_name}"
        )

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
    """
    Kaynak mesajın içeriğini hedef topic'e yollar.
    reply_to=dest_topic_id forum topic başlangıç mesajına yanıt olarak
    gönderim yapar; Telegram bunu ilgili topic içinde gösterir.
    """
    text = message.raw_text or ""
    has_real_file_media = (
        bool(message.media)
        and not isinstance(message.media, NON_FILE_MEDIA)
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


def topic_has_unresolved_failures(
    source_topic_id: int,
    state: Dict[str, Any],
) -> bool:
    """
    Bu konuda daha önce gönderilmeye çalışılıp başarısız olan ve hâlâ
    (done_messages'a göre) gerçekten gönderilmemiş bir mesaj var mı diye
    bakar. Varsa, konu 'tamamlandı' olarak işaretlenmiş olsa bile eksik
    mesajların yeniden denenmesi için konu atlanmaz.
    """
    done_messages = state.get("done_messages", {})
    for entry in state.get("log", []):
        if entry.get("topic_id_source") != source_topic_id:
            continue
        if entry.get("skipped_reason") == "dry_run":
            continue
        if entry.get("forwarded"):
            continue
        message_key = f"{source_topic_id}:{entry.get('source_id')}"
        if not done_messages.get(message_key):
            return True
    return False


async def main():
    if not isinstance(SOURCE, int):
        raise RuntimeError("SOURCE_CHANNEL sayısal kaynak grup ID'si olmalı.")
    if not isinstance(DEST, int):
        raise RuntimeError("DEST_CHANNEL sayısal hedef grup ID'si olmalı.")

    print("\nTelegram bağlantısı hazırlanıyor...")
    print(f"Kaynak: {SOURCE}")
    print(f"Hedef : {DEST}")
    print(f"DRY_RUN: {DRY_RUN}")
    print()

    async with TelegramClient(
        SESSION_NAME,
        API_ID,
        API_HASH,
    ) as client:
        await login_if_needed(client)

        source_dialog = await find_dialog(client, SOURCE, "Kaynak grup")
        destination_dialog = await find_dialog(client, DEST, "Hedef grup")

        source = source_dialog.entity
        destination = destination_dialog.entity

        if not isinstance(source, Channel):
            raise RuntimeError("Kaynak grup Channel/süpergrup türünde olmalı.")
        if not getattr(source, "forum", False):
            raise RuntimeError(
                "Kaynak grup Topics/Forum özelliği açık bir süpergrup olmalı."
            )
        if not isinstance(destination, Channel):
            raise RuntimeError("Hedef grup Channel/süpergrup türünde olmalı.")
        if not getattr(destination, "forum", False):
            raise RuntimeError(
                "Hedef grup Topics/Forum özelliği açık bir süpergrup olmalı."
            )

        print("Kaynak ve hedef başarıyla bulundu.")
        print(f"Kaynak adı : {source_dialog.name}")
        print(f"Hedef adı : {destination_dialog.name}")
        print(f"Kaynak forum : {source.forum}")
        print(f"Hedef forum : {destination.forum}")

        state = load_state(RESUME_FILE)
        done_topics = state.setdefault("done_topics", {})
        done_messages = state.setdefault("done_messages", {})
        state.setdefault("log", [])

        topic_map = load_topic_map(TOPIC_MAP_FILE)

        print("\nHedefteki mevcut topicler okunuyor...")
        existing_dest_topics = await get_dest_topics(client, destination)
        for name, topic_id in existing_dest_topics.items():
            topic_map.setdefault(name, topic_id)
        save_topic_map(TOPIC_MAP_FILE, topic_map)

        print("Kaynak topicler okunuyor...")
        source_topics = await get_source_topics(client, source)
        print(f"Kaynakta {len(source_topics)} konu bulundu.")

        for topic in source_topics:
            topic_name = topic.title
            source_topic_id = topic.id
            topic_key = str(source_topic_id)

            if done_topics.get(topic_key):
                if not topic_has_unresolved_failures(source_topic_id, state):
                    print(f"Atlanıyor (tamamlanmış): {topic_name}")
                    continue
                print(
                    f"'{topic_name}' konusu tamamlanmış görünüyordu ama "
                    "eksik/başarısız gönderilmiş mesaj(lar) var — "
                    "kontrol edilip eksikler tekrar denenecek."
                )

            print(f"\nİşleniyor: {topic_name}")

            if DRY_RUN:
                dest_topic_id = None
                print(
                    " [DRY_RUN] Hedefte kullanılacak/oluşturulacak konu: "
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
                    print(f" Hedef konu ID: {dest_topic_id}")
                except FloodWaitError as error:
                    save_state(RESUME_FILE, state)
                    raise RuntimeError(
                        f"FloodWait: {error.seconds} saniye beklemen gerekiyor."
                    ) from error
                except Exception as error:
                    raise RuntimeError(
                        f"Hedefte konu oluşturulamadı: {topic_name}. "
                        f"Hata: {type(error).__name__}: {error}"
                    ) from error

            message_count = 0
            sent_count = 0
            skipped_count = 0
            topic_had_failure = False

            async for message in client.iter_messages(
                source,
                reply_to=source_topic_id,
                reverse=True,
            ):
                if not message:
                    continue
                if message.action is not None:
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
                    print(f" Atlanıyor (gönderilmiş): #{message.id}")
                    continue

                if DRY_RUN:
                    item.skipped_reason = "dry_run"
                    print(f" [DRY_RUN] #{message.id} | {kind} | {text[:80]!r}")
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
                            f"FloodWait: {error.seconds} saniye beklemen gerekiyor. "
                            "Süre dolunca aynı komutu tekrar çalıştırabilirsin."
                        ) from error
                    except Exception as error:
                        item.forwarded = False
                        item.skipped_reason = str(error)
                        topic_had_failure = True
                        print(
                            f" [HATA] Mesaj #{message.id} gönderilemedi: "
                            f"{type(error).__name__}: {error}"
                        )

                state["log"].append(asdict(item))
                save_state(RESUME_FILE, state)

            print(
                f" Konudaki toplam mesaj: {message_count} | "
                f"Gönderilen: {sent_count} | "
                f"Atlanan: {skipped_count}"
            )

            if not DRY_RUN:
                if not topic_had_failure and not topic_has_unresolved_failures(
                    source_topic_id, state
                ):
                    done_topics[topic_key] = True
                else:
                    done_topics.pop(topic_key, None)
                    print(
                        f" '{topic_name}' konusunda hâlâ gönderilememiş "
                        "mesaj(lar) var; bir sonraki çalıştırmada tekrar "
                        "denenecek."
                    )
                save_state(RESUME_FILE, state)

    print("\nTamamlandı.")


if __name__ == "__main__":
    asyncio.run(main())
