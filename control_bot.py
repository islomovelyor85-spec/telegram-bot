import re
import asyncio
from telethon import events, utils
from db import add_channel_db, remove_channel_db, get_channels_db, search_files_db
from link_handler import setup_link_handler


def setup_control_bot(bot, userbot, admin_ids, db_channel, max_range, history_delay, search_limit=10):
    def is_admin(user_id):
        return user_id in admin_ids

    @bot.on(events.NewMessage(pattern=r"^/start"))
    async def start_cmd(event):
        text = (
            "🤖 **Salom! Bot ishlamoqda.**\n\n"
            "Menga kanal post havolasini yuboring, men uni sizga tashlab beraman va baza kanalga yig'aman:\n"
            "• `https://t.me/c/123456/55` — bitta post\n"
            "• `https://t.me/c/123456/50-60` — oraliq\n"
            "• `https://t.me/username/55` — ochiq kanal\n\n"
            "🔐 Yopiq kanal bo'lsa, avval uning **taklif havolasini** yuboring "
            "(`https://t.me/+...`) — men o'zim qo'shilaman, keyin post havolasini yuborasiz.\n\n"
            f"🔎 `/search <so'z>` — bazadan qidirish\n\n"
            "*(Bu botdan hamma foydalana oladi).*"
        )
        if is_admin(event.sender_id):
            text += (
                "\n\n**Admin buyruqlari:**\n"
                "➕ `/add <kanal_id yoki @username>` - Kanal qo'shish\n"
                "➖ `/remove <kanal_id>` - Kanalni o'chirish\n"
                "📋 `/channels` - Kanallar ro'yxati"
            )
        await event.respond(text)

    @bot.on(events.NewMessage(pattern=r"^/add\s+(\S+)"))
    async def add_chan(event):
        if not is_admin(event.sender_id):
            await event.respond("❌ Kechirasiz, bu buyruq faqat admin uchun.")
            return
        try:
            arg = event.pattern_match.group(1)
            target = int(arg) if re.fullmatch(r"-?\d+", arg) else arg
            chat = await userbot.get_entity(target)
            peer_id = utils.get_peer_id(chat)  # -100... ko'rinishida, event.chat_id bilan mos
            title = getattr(chat, "title", None) or getattr(chat, "first_name", "") or str(peer_id)
            add_channel_db(peer_id, title)
            await event.respond(f"✅ Kanal qo'shildi: **{title}** (`{peer_id}`)")
        except Exception as e:
            await event.respond(f"❌ Xatolik: {e}\n\nUserbot akkaunti shu kanal a'zosi ekanini tekshiring.")

    @bot.on(events.NewMessage(pattern=r"^/remove\s+(-?\d+)"))
    async def remove_chan(event):
        if not is_admin(event.sender_id):
            await event.respond("❌ Kechirasiz, bu buyruq faqat admin uchun.")
            return
        chat_id = int(event.pattern_match.group(1))
        if remove_channel_db(chat_id):
            await event.respond(f"🗑 Kanal o'chirildi: `{chat_id}`")
        else:
            await event.respond(f"⚠️ `{chat_id}` ro'yxatda topilmadi. `/channels` dan aniq ID ni oling.")

    @bot.on(events.NewMessage(pattern=r"^/channels"))
    async def list_chans(event):
        if not is_admin(event.sender_id):
            await event.respond("❌ Kechirasiz, bu buyruq faqat admin uchun.")
            return
        rows = get_channels_db()
        if not rows:
            await event.respond("📭 Hozircha kuzatilayotgan kanallar yo'q.")
            return
        text = "📋 **Kuzatilayotgan kanallar:**\n\n"
        for cid, title in rows:
            text += f"▪️ {title or 'Noma’lum'} (`{cid}`)\n"
        await event.respond(text)

    @bot.on(events.NewMessage(pattern=r"^/search(?:\s+(.+))?"))
    async def search_cmd(event):
        query = (event.pattern_match.group(1) or "").strip()
        if not query:
            await event.respond("🔎 Foydalanish: `/search <so'z>`")
            return
        rows = search_files_db(query, search_limit)
        if not rows:
            await event.respond("😕 Hech narsa topilmadi.")
            return
        await event.respond(f"🔎 {len(rows)} ta natija topildi, yuborilmoqda...")
        for _name, msg_id, chan_id in rows:
            try:
                m = await bot.get_messages(chan_id, ids=msg_id)
                if not m:
                    continue
                if m.media:
                    await bot.send_file(event.chat_id, m.media)
                elif m.text:
                    await bot.send_message(event.chat_id, m.text.split("\n\n---\n")[0])
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"Qidiruv yuborish xatosi: {e!r}")

    # Havolalar (taklif linki va post havolalari)
    setup_link_handler(bot, userbot, db_channel, max_range, history_delay)
