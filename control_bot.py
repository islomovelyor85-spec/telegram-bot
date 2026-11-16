import os
import asyncio
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError, PhoneCodeInvalidError
from db import (
    add_channel_db, remove_channel_db, get_channels_db,
    set_user_logged_in, is_user_logged_in
)
from watcher import send_to_database_and_user

os.makedirs("user_sessions", exist_ok=True)

active_clients = {}
login_states = {}

async def get_user_client(user_id, api_id, api_hash, fallback_userbot):
    if user_id in active_clients:
        client = active_clients[user_id]
        if not client.is_connected():
            await client.connect()
        return client
    
    session_path = f"user_sessions/user_{user_id}"
    if is_user_logged_in(user_id) and os.path.exists(f"{session_path}.session"):
        client = TelegramClient(session_path, api_id, api_hash)
        await client.connect()
        if await client.is_user_authorized():
            active_clients[user_id] = client
            return client
            
    return fallback_userbot

def setup_control_bot(bot, main_userbot, api_id, api_hash, admin_ids, db_channel, max_range, history_delay):
    def is_admin(user_id):
        return user_id in admin_ids

    @bot.on(events.NewMessage(pattern="/start"))
    async def start_cmd(event):
        user_id = event.sender_id
        status = "✅ Akkauntingiz ulangan" if is_user_logged_in(user_id) else "❌ Akkaunt ulanmagan"
        await event.respond(
            f"🤖 **Salom! Yopiq kanallardan yuklovchi botga xush kelibsiz.**\n\n"
            f"Holatingiz: **{status}**\n\n"
            f"🔒 **Xavfsizlik kafolati:**\n"
            f"Sizning ma'lumotlaringiz adminga yoki boshqa uchinchi shaxslarga tushmaydi! "
            f"Kiritgan raqamingiz faqat o'zingizning shaxsiy sessiyangizni yaratish uchun ishlatiladi.\n\n"
            "📌 **Qanday ishlaydi?**\n"
            "1. Avval `/login` buyrug‘i orqali shaxsiy akkauntingizni ulang.\n"
            "2. Istalgan yopiq kanal post havolasini (masalan: `https://t.me/c/2258587153/13580` yoki `50-65`) yuboring — bot darhol yuklab beradi!\n\n"
            "**Buyruqlar:**\n"
            "🔑 `/login` — Shaxsiy akkauntni ulash\n"
            "🚪 `/logout` — Akkauntni uzish\n"
            "❌ `/cancel` — Jarayonni bekor qilish"
        )

    @bot.on(events.NewMessage(pattern="/cancel"))
    async def cancel_cmd(event):
        user_id = event.sender_id
        if user_id in login_states:
            state = login_states.pop(user_id)
            if "client" in state:
                await state["client"].disconnect()
            await event.respond("🚫 Kirish jarayoni bekor qilindi.")

    @bot.on(events.NewMessage(pattern="/logout"))
    async def logout_cmd(event):
        user_id = event.sender_id
        if user_id in active_clients:
            try:
                await active_clients[user_id].log_out()
            except Exception:
                pass
            del active_clients[user_id]
        session_file = f"user_sessions/user_{user_id}.session"
        if os.path.exists(session_file):
            os.remove(session_file)
        set_user_logged_in(user_id, "", status=0)
        await event.respond("🚪 Akkauntingiz botdan muvaffaqiyatli uzildi va barcha ma'lumotlaringiz o‘chirildi.")

    @bot.on(events.NewMessage(pattern="/login"))
    async def login_cmd(event):
        if not event.is_private:
            return
        user_id = event.sender_id
        if is_user_logged_in(user_id):
            await event.respond("✅ Siz allaqachon tizimga kirgansiz! Yangidan ulash uchun avval `/logout` bosing.")
            return
        
        login_states[user_id] = {"step": "phone"}
        await event.respond(
            "📱 **Telegram telefon raqamingizni yuboring** (xalqaro formatda, masalan: `+998901234567`):\n\n"
            "*(Ma'lumotlaringiz mutlaqo xavfsiz. Bekor qilish uchun `/cancel` yozing)*"
        )

    @bot.on(events.NewMessage(pattern=r"^/add\s+(-?\d+)"))
    async def add_chan(event):
        if not is_admin(event.sender_id): return
        try:
            chat_id = int(event.pattern_match.group(1))
            chat = await main_userbot.get_entity(chat_id)
            add_channel_db(chat.id, chat.title)
            await event.respond(f"✅ Kanal qo'shildi: **{chat.title}** (`{chat.id}`)")
        except Exception as e:
            await event.respond(f"❌ Xatolik: {e}")

    @bot.on(events.NewMessage(pattern=r"^/remove\s+(-?\d+)"))
    async def remove_chan(event):
        if not is_admin(event.sender_id): return
        try:
            chat_id = int(event.pattern_match.group(1))
            remove_channel_db(chat_id)
            await event.respond(f"🗑 Kanal o'chirildi: `{chat_id}`")
        except Exception as e:
            await event.respond(f"❌ Xatolik: {e}")

    @bot.on(events.NewMessage(pattern="/channels"))
    async def list_chans(event):
        if not is_admin(event.sender_id): return
        rows = get_channels_db()
        if not rows:
            await event.respond("📭 Hozircha kuzatilayotgan kanallar yo'q.")
            return
        text = "📋 **Kuzatilayotgan kanallar:**\n\n"
        for cid, title in rows:
            text += f"▪️ {title or 'Noma’lum'} (`{cid}`)\n"
        await event.respond(text)

    @bot.on(events.NewMessage(func=lambda e: e.is_private and e.text and not e.text.startswith("/")))
    async def message_handler(event):
        user_id = event.sender_id
        text = event.text.strip()

        if user_id in login_states:
            state = login_states[user_id]
            step = state["step"]

            if step == "phone":
                phone = text.replace(" ", "")
                session_path = f"user_sessions/user_{user_id}"
                client = TelegramClient(session_path, api_id, api_hash)
                await client.connect()
                try:
                    sent_code = await client.send_code_request(phone)
                    state["client"] = client
                    state["phone"] = phone
                    state["phone_code_hash"] = sent_code.phone_code_hash
                    state["step"] = "code"
                    await event.respond(
                        "📩 Telegramingizga **5 xonali kod** yuborildi.\n"
                        "⚠️ **Diqqat:** Kodni xavfsizlik uchun orasiga probel yoki nuqta qo‘yib yuboring (masalan: `1 2 3 4 5`)."
                    )
                except Exception as e:
                    await client.disconnect()
                    del login_states[user_id]
                    await event.respond(f"❌ Xatolik: {e}\nQaytadan `/login` bosib urinib ko‘ring.")
                return

            elif step == "code":
                code = text.replace(" ", "").replace(".", "").replace("-", "")
                client = state["client"]
                try:
                    await client.sign_in(state["phone"], code, phone_code_hash=state["phone_code_hash"])
                    set_user_logged_in(user_id, state["phone"], status=1)
                    active_clients[user_id] = client
                    del login_states[user_id]
                    await event.respond("🎉 **Tabriklaymiz! Akkauntingiz muvaffaqiyatli ulandi.**\nEndi yopiq kanallardan post havolasini yuborishingiz mumkin!")
                except SessionPasswordNeededError:
                    state["step"] = "password"
                    await event.respond("🔐 Akkauntingizda **Ikki bosqichli parol (2FA)** o‘rnatilgan ekan. Parolingizni kiriting:")
                except PhoneCodeInvalidError:
                    await event.respond("❌ Kod noto‘g‘ri kiritildi. Qaytadan kiriting:")
                except Exception as e:
                    await client.disconnect()
                    del login_states[user_id]
                    await event.respond(f"❌ Xatolik: {e}")
                return

            elif step == "password":
                client = state["client"]
                try:
                    await client.sign_in(password=text)
                    set_user_logged_in(user_id, state["phone"], status=1)
                    active_clients[user_id] = client
                    del login_states[user_id]
                    await event.respond("🎉 **Tabriklaymiz! Akkauntingiz muvaffaqiyatli ulandi.**\nEndi yopiq kanallardan post havolasini yuborishingiz mumkin!")
                except Exception as e:
                    await event.respond(f"❌ Parol noto‘g‘ri yoki xatolik: {e}\nQaytadan urinib ko‘ring yoki `/cancel` bosing.")
                return

        if "t.me/" in text:
            client = await get_user_client(user_id, api_id, api_hash, main_userbot)

            try:
                if "-" in text.split("/")[-1] and not text.endswith("/"):
                    base_url, range_part = text.rsplit("/", 1)
                    start_str, end_str = range_part.split("-")
                    start_id = int(start_str)
                    end_id = int(end_str)

                    if (end_id - start_id) > max_range:
                        await event.respond(f"⚠️ Bir martada ko'pi bilan {max_range} ta xabar olishingiz mumkin.")
                        return

                    await event.respond(f"⏳ {start_id} dan {end_id} gacha xabarlar yuklanmoqda...")

                    if "/c/" in base_url:
                        parts = base_url.split("/c/")
                        sub_parts = parts[1].split("/")
                        chat_id = int("-100" + sub_parts[0])
                    else:
                        parts = base_url.split("t.me/")
                        sub_parts = parts[1].split("/")
                        username = sub_parts[0]
                        chat_entity = await client.get_entity(username)
                        chat_id = chat_entity.id

                    try:
                        chat_entity = await client.get_entity(chat_id)
                    except Exception:
                        await event.respond("❌ Kanal topilmadi. Agar bu yopiq kanal bo‘lsa, avval `/login` orqali o‘sha kanalga a'zo bo‘lgan akkauntingizni ulang.")
                        return

                    success_count = 0
                    for msg_id in range(start_id, end_id + 1):
                        try:
                            msg = await client.get_messages(chat_entity, ids=msg_id)
                            if msg and (msg.media or msg.document or msg.photo or msg.text):
                                await send_to_database_and_user(client, bot, db_channel, msg, target_user_event=event, original_link=f"{base_url}/{msg_id}")
                                success_count += 1
                                await asyncio.sleep(history_delay)
                        except Exception:
                            continue

                    await event.respond(f"✅ Yakunlandi! Jami {success_count} ta xabar yuklandi va bazaga saqlandi.")
                    return

                if "/c/" in text:
                    parts = text.split("/c/")
                    sub_parts = parts[1].split("/")
                    chat_id = int("-100" + sub_parts[0])
                    msg_id = int(sub_parts[1].split("-")[0])
                else:
                    parts = text.split("t.me/")
                    sub_parts = parts[1].split("/")
                    username = sub_parts[0]
                    msg_id = int(sub_parts[1].split("-")[0])
                    chat_entity = await client.get_entity(username)
                    chat_id = chat_entity.id

                try:
                    chat_entity = await client.get_entity(chat_id)
                except Exception:
                    await event.respond("❌ Kanal topilmadi. Agar bu yopiq kanal bo‘lsa, avval `/login` orqali o‘sha kanalga a'zo bo‘lgan akkauntingizni ulang.")
                    return

                msg = await client.get_messages(chat_entity, ids=msg_id)
                if msg:
                    await send_to_database_and_user(client, bot, db_channel, msg, target_user_event=event, original_link=text)
                    await event.respond("✅ Muvaffaqiyatli yuklandi va bazaga saqlandi!")
                else:
                    await event.respond("❌ Xabar topilmadi.")
            except Exception as e:
                await event.respond(f"❌ Xatolik yuz berdi: {e}")
