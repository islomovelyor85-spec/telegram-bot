"""Havolalarni tahlil qilish va userbotni kanalga qo'shish yordamchilari."""
import re
from telethon import events, utils
from telethon.tl.functions.messages import ImportChatInviteRequest, CheckChatInviteRequest
from telethon.tl.types import ChatInviteAlready
from telethon.tl.functions.channels import JoinChannelRequest
from telethon.errors import (
    UserAlreadyParticipantError, InviteHashExpiredError, InviteHashInvalidError, FloodWaitError,
)

# https://t.me/c/123456/55 , https://t.me/c/123456/50-60 , https://t.me/username/55 , t.me/username/50-60
LINK_RE = re.compile(
    r"(?:https?://)?t\.me/(?:(c)/(\d+)|([A-Za-z0-9_]{4,}))/(?:\d+/)?(\d+)(?:\s*-\s*(\d+))?"
)


# https://t.me/+AbCdEf... yoki https://t.me/joinchat/AbCdEf...
INVITE_RE = re.compile(r"(?:https?://)?t\.me/(?:\+|joinchat/)([A-Za-z0-9_-]{8,})")


async def join_by_invite(userbot, invite_hash):
    """
    Userbotni taklif havolasi orqali kanal/guruhga qo'shadi.
    Qaytaradi: (status, title, chat)  status: joined | already | request | expired | error
    """
    try:
        info = await userbot(CheckChatInviteRequest(invite_hash))
    except (InviteHashExpiredError, InviteHashInvalidError):
        return "expired", None, None

    if isinstance(info, ChatInviteAlready):
        return "already", getattr(info.chat, "title", ""), info.chat

    title = getattr(info, "title", "") or ""
    try:
        res = await userbot(ImportChatInviteRequest(invite_hash))
        chat = res.chats[0] if res.chats else None
        return "joined", getattr(chat, "title", title), chat
    except UserAlreadyParticipantError:
        return "already", title, None
    except FloodWaitError:
        raise
    except Exception as e:
        if type(e).__name__ == "InviteRequestSentError":
            return "request", title, None
        return "error", f"{title} ({e})", None


NOT_MEMBER_TEXT = "❌ Kanal topilmadi. Yopiq kanal bo'lsa, avval taklif linkini yuboring."


async def resolve_chat(userbot, is_private, chat_part, username):
    if is_private:
        chat_id = int("-100" + chat_part)
        try:
            await userbot.get_input_entity(chat_id)
        except ValueError:
            # Kanalga keyinroq qo'shilgan bo'lishi mumkin — dialoglarni yangilab qayta urinamiz
            async for _ in userbot.iter_dialogs():
                pass
            await userbot.get_input_entity(chat_id)  # baribir topilmasa ValueError
        return chat_id
    entity = await userbot.get_entity(username)
    # Ochiq kanal bo'lsa — admin profil (userbot) avtomatik a'zo bo'ladi
    if getattr(entity, "left", False):
        try:
            await userbot(JoinChannelRequest(entity))
        except Exception as e:
            print(f"Ochiq kanalga qo'shilish xatosi: {e!r}")
    return utils.get_peer_id(entity)
