# Telegram baza boti (userbot + boshqaruv boti)

## Ishga tushirishdan oldin (bir marta)
1. **Botni baza kanaliga admin qiling** (`DB_CHANNEL`, xabar yuborish huquqi bilan).
2. **Userbot akkaunti** (telefon raqamingiz) kuzatiladigan / havolasi yuboriladigan kanallarga **a'zo** bo'lsin.
3. `.env.example` dan nusxa olib `.env` yarating va qiymatlarni to'ldiring.

## Ishga tushirish
- macOS / Linux: `./start.sh`
- Windows: `start.bat` ni ikki marta bosing

Birinchi ishga tushishda terminal telefon raqamingizni (`+998...`) va Telegram yuborgan kodni so'raydi
(2-bosqichli parol bo'lsa, uni ham). Keyin `my_userbot.session` fayli yaratiladi va boshqa so'ramaydi.

## Buyruqlar
| Buyruq | Kim | Vazifasi |
|---|---|---|
| havola `https://t.me/c/123/55` | hamma | bitta postni olish |
| havola `https://t.me/c/123/50-60` | hamma | oraliqdagi postlar (`MAX_RANGE` gacha) |
| `/search so'z` | hamma | bazadan qidirish (`SEARCH_LIMIT` ta) |
| `/add -100123...` yoki `/add @kanal` | admin | kanalni avto-kuzatuvga qo'shish |
| `/remove -100123...` | admin | kuzatuvdan olib tashlash |
| `/channels` | admin | kuzatilayotgan kanallar |

## Fayllar
- `main.py` — hammasini ishga tushiradi
- `control_bot.py` — bot buyruqlari va havola orqali yuklash
- `watcher.py` — kanallarni kuzatish, yuklab olib baza kanalga yuborish
- `db.py` — SQLite (`bot_database.db`)
