import os
import sys
import asyncio
from dotenv import load_dotenv
from telethon import TelegramClient

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)
load_dotenv(os.path.join(BASE_DIR, ".env"))


def env_required(name):
    value = os.getenv(name)
    if not value:
        sys.exit(f"❌ .env faylida {name} topilmadi.")
    return value


API_ID = int(env_required("API_ID"))
API_HASH = env_required("API_HASH")
BOT_TOKEN = env_required("BOT_TOKEN")
DB_CHANNEL = int(env_required("DB_CHANNEL"))

admin_ids_raw = os.getenv("ADMIN_IDS", "")
ADMIN_IDS = [int(aid.strip()) for aid in admin_ids_raw.split(",") if aid.strip()]

MAX_RANGE = int(os.getenv("MAX_RANGE", 50))
HISTORY_DELAY = float(os.getenv("HISTORY_DELAY", 2))
SEARCH_LIMIT = int(os.getenv("SEARCH_LIMIT", 10))

from watcher import setup_watcher  # noqa: E402
from control_bot import setup_control_bot  # noqa: E402

# Klientlar
userbot = TelegramClient(os.path.join(BASE_DIR, "my_userbot"), API_ID, API_HASH)
bot = TelegramClient(os.path.join(BASE_DIR, "control_bot"), API_ID, API_HASH)

# Modullarni ulash
setup_watcher(userbot, bot, DB_CHANNEL)
setup_control_bot(bot, userbot, ADMIN_IDS, DB_CHANNEL, MAX_RANGE, HISTORY_DELAY, SEARCH_LIMIT)


async def main():
    print("Userbot va Bot ishga tushmoqda...")
    print("(Birinchi marta: userbot uchun telefon raqam va Telegram kodini kiriting)")
    await userbot.start()
    await bot.start(bot_token=BOT_TOKEN)

    me = await userbot.get_me()
    bot_me = await bot.get_me()
    print(f"👤 Userbot: {me.first_name} (@{me.username})")
    print(f"🤖 Bot: @{bot_me.username}")

    # Userbot kanallarni "tanishi" uchun dialoglarni yuklab olamiz
    async for _ in userbot.iter_dialogs():
        pass

    # Baza kanalini tekshirish
    try:
        await bot.get_input_entity(DB_CHANNEL)
        await bot.send_message(DB_CHANNEL, "✅ Bot ishga tushdi.")
    except Exception as e:
        print(f"⚠️ Bot baza kanaliga ({DB_CHANNEL}) yoza olmadi: {e}")
        print("   Botni baza kanaliga ADMIN qilib qo'shing (xabar yuborish huquqi bilan).")

    print("✅ Tizim to'liq tayyor va barcha modullar ishlamoqda! To'xtatish: Ctrl+C")

    await asyncio.gather(
        userbot.run_until_disconnected(),
        bot.run_until_disconnected()
    )


if __name__ == "__main__":
    try:
        # Klientlar yaratilgan loop'ning o'zida ishlatamiz (asyncio.run yangi loop ochib, xato beradi)
        userbot.loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("\n👋 To'xtatildi.")
