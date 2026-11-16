"""Foydalanuvchi yuborgan havolalar: taklif linki orqali qo'shilish va postlarni olish."""
import asyncio
from telethon import events
from telethon.errors import FloodWaitError
from links import LINK_RE, INVITE_RE, NOT_MEMBER_TEXT, join_by_invite, resolve_chat
from watcher import send_to_database_and_user


def setup_link_handler(bot, userbot, db_channel, max_range, history_delay):
    @bot.on(events.NewMessage(func=lambda e: e.is_private and e.text and "t.me/" in e.text and not e.text.startswith("/")))
    async def get_by_link(event):
        # --- 1) Taklif havolalari: userbot avtomatik qo'shiladi ---
        invites = INVITE_RE.findall(event.text)
        if invites:
            sender = await event.get_sender()
            name = getattr(sender, "first_name", None) or "Noma’lum"
            uname = f" (@{sender.username})" if getattr(sender, "username", None) else ""
            for inv in dict.fromkeys(invites):  # takrorlarsiz
                link = f"https://t.me/+{inv}"
                try:
                    status, title, _chat = await join_by_invite(userbot, inv)
                except FloodWaitError as e:
                    await event.respond(f"⏳ Telegram cheklovi: {e.seconds} soniyadan keyin qayta urinib ko'ring.")
                    return
                reply = {
                    "joined": f"✅ Kanalga qo'shildim: **{title}**",
                    "already": f"ℹ️ Allaqachon a'zoman: **{title}**",
                    "request": f"📨 **{title}** — qo'shilish so'rovi yuborildi, admin tasdiqlashi kerak.",
                    "expired": "❌ Taklif havolasi eskirgan yoki noto'g'ri.",
                    "error": f"❌ Qo'shilib bo'lmadi: {title}",
                }[status]
                if status in ("joined", "already"):
                    reply += "\n\nEndi shu kanaldan post havolasini yuboring."
                await event.respond(reply)

                # Baza kanaliga log
                status_text = {
                    "joined": "✅ qo'shildi", "already": "ℹ️ avval a'zo", "request": "📨 so'rov yuborildi",
                    "expired": "❌ eskirgan", "error": "❌ xato",
                }[status]
                try:
                    await bot.send_message(
                        db_channel,
                        f"🔐 **Taklif linki**\n"
                        f"👤 {name}{uname}\n"
                        f"🆔 `{event.sender_id}`\n"
                        f"🔗 {link}\n"
                        f"📢 {title or '—'} — {status_text}",
                        link_preview=False,
                    )
                except Exception as e:
                    print(f"Log yuborish xatosi: {e!r}")
                await asyncio.sleep(1)

        match = LINK_RE.search(INVITE_RE.sub(" ", event.text))
        if not match:
            if invites:
                return
            await event.respond("❌ Havola formati noto'g'ri. Misol: `https://t.me/c/123456/55`")
            return

        is_private, chat_part, username, start_s, end_s = match.groups()
        start_id = int(start_s)
        end_id = int(end_s) if end_s else start_id
        if end_id < start_id:
            start_id, end_id = end_id, start_id

        try:
            chat_id = await resolve_chat(userbot, is_private, chat_part, username)
        except Exception as e:
            print(f"Kanal topilmadi ({chat_part or username}): {e!r}")
            await event.respond(NOT_MEMBER_TEXT)
            return

        base_url = (f"https://t.me/c/{chat_part}" if is_private else f"https://t.me/{username}")

        # --- Bitta post ---
        if start_id == end_id:
            try:
                msg = await userbot.get_messages(chat_id, ids=start_id)
            except Exception as e:
                # Masalan: kanaldan chiqarilgan yoki kanal yopiq (ChannelPrivateError)
                print(f"Post olish xatosi: {e!r}")
                await event.respond(NOT_MEMBER_TEXT)
                return
            if not msg:
                await event.respond("❌ Xabar topilmadi.")
                return
            status = await event.respond("⏳ Yuklanmoqda...")
            ok = await send_to_database_and_user(
                userbot, bot, db_channel, msg, target_user_event=event, original_link=f"{base_url}/{start_id}"
            )
            await status.edit("✅ Muvaffaqiyatli olindi va bazaga saqlandi!" if ok else "❌ Xabarni yuborib bo'lmadi.")
            return

        # --- Oraliq ---
        if (end_id - start_id + 1) > max_range:
            await event.respond(f"⚠️ Kechirasiz, bir martada ko'pi bilan {max_range} ta xabar olishingiz mumkin.")
            return

        status = await event.respond(f"⏳ {start_id} dan {end_id} gacha bo'lgan xabarlar yuklanmoqda...")
        try:
            messages = await userbot.get_messages(chat_id, ids=list(range(start_id, end_id + 1)))
        except Exception as e:
            print(f"Oraliq olish xatosi: {e!r}")
            await status.edit(NOT_MEMBER_TEXT)
            return

        success_count = 0
        seen_groups = set()
        for msg in messages:
            if not msg or not (msg.media or msg.text):
                continue
            if msg.grouped_id:
                if msg.grouped_id in seen_groups:
                    continue
                seen_groups.add(msg.grouped_id)
            ok = await send_to_database_and_user(
                userbot, bot, db_channel, msg, target_user_event=event, original_link=f"{base_url}/{msg.id}"
            )
            if ok:
                success_count += 1
            await asyncio.sleep(history_delay)

        await event.respond(f"✅ Jarayon yakunlandi! Jami {success_count} ta post bazaga yig'ildi va sizga yuborildi.")
