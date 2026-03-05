"""Send messages to Telegram chat."""

import asyncio

from telethon import TelegramClient
from telethon.sessions import StringSession

from chat.config import TG_API_ID, TG_API_HASH, TG_SESSION, TG_CHAT_ID


def _create_client():
    session = TG_SESSION
    if session and len(session) > 1:
        padding = 4 - (len(session) - 1) % 4
        if padding < 4:
            session = session[0] + session[1:] + "=" * padding
    return TelegramClient(StringSession(session), TG_API_ID, TG_API_HASH)


async def send_message(text: str, dialog_id: int | None = None) -> int:
    dialog_id = dialog_id or TG_CHAT_ID
    if not dialog_id:
        raise ValueError("TG_CHAT_ID not set in .env")
    client = _create_client()
    try:
        await client.connect()
        result = await client.send_message(dialog_id, text)
        return result.id
    finally:
        await client.disconnect()


def run_send(text: str, dialog_id: int | None = None) -> int:
    return asyncio.run(send_message(text, dialog_id))
