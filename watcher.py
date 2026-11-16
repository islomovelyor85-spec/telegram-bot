import os
import asyncio
import tempfile
from telethon import events
from telethon.tl.custom.message import Message
from telethon.errors import FloodWaitError
from db import watched_chats_cache, save_file_db

DOWNLOAD_DIR = os.path.join(tempfile.gettempdir(), "tg_bot_downloads")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Baza kanaliga media ostidagi sarlavha
DB_HEADER = "📦 **Baza — yuklanganlar**\n💯✅"

_db_entity = None


async def get_db_entity(bot, db_channel):
    global _db_entity
    if _db_entity is None:
        _db_entity = await bot.get_input_entity(db_channel)
    return _db_entity


def as_message(obj):
    """NewMessage.Event yoki Message keladi — har doim Message qaytaramiz."""
    if isinstance(obj, Message):
        return obj
    return obj.message


async def get_album(userbot, msg):
    """Xabar albom bo'lsa, albomdagi barcha xabarlarni tartib bilan qaytaradi."""
    if not msg.grouped_id:
        return [msg]
    ids = list(range(max(1, msg.id - 10), msg.id + 11))
    around = await userbot.get_messages(msg.chat_id, ids=ids)
    album = [m for m in around if m and m.grouped_id == msg.grouped_id]
    album.sort(key=lambda m: m.id)
    return album or [msg]


async def post_link(msg):
    chat = await msg.get_chat()
    username = getattr(chat, "username", None)
    if username:
        return f"https://t.me/{username}/{msg.id}"
    return f"https://t.me/c/{str(msg.chat_id).replace('-100', '', 1)}/{msg.id}"


async def build_info(msg, target_user_event, original_link):
    """
    Media ostiga reply qilinadigan ma'lumot:
    so'ragan foydalanuvchi (havola orqali) yoki manba kanal (avto-kuzatuv).
    """
    if target_user_event is not None:
        who = await target_user_event.get_sender()
        who_id = target_user_event.sender_id
    else:
        who = await msg.get_chat()
        who_id = msg.chat_id

    name = (getattr(who, "first_name", None) or getattr(who, "title", None) or "Noma’lum") if who else "Noma’lum"
    last = getattr(who, "last_name", None) if who else None
    if last:
        name = f"{name} {last}"
    username = getattr(who, "username", None) if who else None
    uname = f" (@{username})" if username else ""
    link = original_link or await post_link(msg)

    return (
        f"👤 {name}{uname}\n"
        f"🆔 `{who_id}`\n"
        f"🔗 {link}"
    )


async def _download_all(userbot, messages):
    paths = []
    for m in messages:
        if m.media:
            p = await userbot.download_media(m, file=DOWNLOAD_DIR + os.sep)
            if p:
                paths.append(p)
    return paths


def _cleanup(paths):
    for p in paths:
        try:
            os.remove(p)
        except OSError:
            pass


async def send_to_database_and_user(userbot, bot, db_channel, event, target_user_event=None, original_link=None):
    """
    Xabarni userbot orqali yuklab oladi, bot orqali baza kanalga (media + reply ma'lumot)
    va (kerak bo'lsa) foydalanuvchiga yuboradi. Muvaffaqiyatli bo'lsa True qaytaradi.
    """
    msg = as_message(event)

    for attempt in range(2):
        try:
            return await _deliver(userbot, bot, db_channel, msg, target_user_event, original_link)
        except FloodWaitError as e:
            print(f"FloodWait: {e.seconds} soniya kutilmoqda...")
            await asyncio.sleep(e.seconds + 1)
        except Exception as e:
            print(f"Yetkazish xatosi: {e!r}")
            return False
    return False


async def _deliver(userbot, bot, db_channel, msg, target_user_event, original_link):
    db_entity = await get_db_entity(bot, db_channel)
    info_text = await build_info(msg, target_user_event, original_link)
    user_chat = target_user_event.chat_id if target_user_event else None

    async def send_info(reply_to_id):
        await bot.send_message(db_entity, info_text, reply_to=reply_to_id, link_preview=False)

    # --- Albom ---
    if msg.grouped_id:
        album = await get_album(userbot, msg)
        paths = await _download_all(userbot, album)
        if not paths:
            return False
        try:
            album_text = next((m.text for m in album if m.text), "")
            sent = await bot.send_file(db_entity, paths, caption=DB_HEADER)
            sent_list = sent if isinstance(sent, list) else [sent]
            await send_info(sent_list[0].id)
            if user_chat:
                # Bot o'zi yuklagan mediani qayta ishlatadi — qayta yuklash shart emas
                await bot.send_file(user_chat, [s.media for s in sent_list], caption=album_text or None)
            save_file_db((album_text or "Albom")[:50], sent_list[0].id, db_channel)
        finally:
            _cleanup(paths)
        return True

    # --- Oddiy media ---
    if msg.media and not getattr(msg, "web_preview", None):
        paths = await _download_all(userbot, [msg])
        if not paths:
            return False
        try:
            sent = await bot.send_file(db_entity, paths[0], caption=DB_HEADER)
            await send_info(sent.id)
            if user_chat:
                await bot.send_file(user_chat, sent.media, caption=msg.text or None)
        finally:
            _cleanup(paths)
        save_file_db((msg.text or getattr(msg.file, "name", None) or "Media / Fayl")[:50], sent.id, db_channel)
        return True

    # --- Faqat matn ---
    if msg.text:
        sent = await bot.send_message(db_entity, f"{DB_HEADER}\n\n{msg.text}", link_preview=False)
        await send_info(sent.id)
        if user_chat:
            await bot.send_message(user_chat, msg.text)
        save_file_db(msg.text[:50], sent.id, db_channel)
        return True

    return False


def setup_watcher(userbot, bot, db_channel):
    # Oddiy (albom bo'lmagan) media
    @userbot.on(events.NewMessage)
    async def userbot_listener(event):
        if event.chat_id not in watched_chats_cache:
            return
        if event.grouped_id:
            return  # albomlarni pastdagi Album handler bir marta ushlaydi
        if event.media:
            await send_to_database_and_user(userbot, bot, db_channel, event)

    # Albom (bir postda bir nechta rasm/video) — to'liq kelgandan keyin bir marta
    @userbot.on(events.Album)
    async def album_listener(event):
        if event.chat_id not in watched_chats_cache:
            return
        await send_to_database_and_user(userbot, bot, db_channel, event.messages[0])
