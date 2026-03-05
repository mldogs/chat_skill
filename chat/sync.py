"""Telegram chat synchronization via Telethon."""

import asyncio
from datetime import datetime, timedelta

from telethon import TelegramClient
from telethon.sessions import StringSession
from telethon.tl.types import (
    User, Chat, Channel,
    Message as TelethonMessage,
    MessageMediaPhoto, MessageMediaDocument, MessageMediaWebPage,
)

from chat.config import TG_API_ID, TG_API_HASH, TG_SESSION, TG_CHAT_ID
from chat.db import init_db, upsert_messages, get_sync_state, update_sync_state


def _create_client() -> TelegramClient:
    session = TG_SESSION
    if session and len(session) > 1:
        padding = 4 - (len(session) - 1) % 4
        if padding < 4:
            session = session[0] + session[1:] + "=" * padding
    return TelegramClient(StringSession(session), TG_API_ID, TG_API_HASH)


def _get_entity_name(entity) -> str:
    if isinstance(entity, User):
        parts = []
        if entity.first_name:
            parts.append(entity.first_name)
        if entity.last_name:
            parts.append(entity.last_name)
        return " ".join(parts) or entity.username or f"User {entity.id}"
    elif isinstance(entity, (Chat, Channel)):
        return entity.title or f"Chat {entity.id}"
    return f"Unknown {entity.id}"


def _get_media_type(message: TelethonMessage) -> str | None:
    if not message.media:
        return None
    if isinstance(message.media, MessageMediaPhoto):
        return "photo"
    elif isinstance(message.media, MessageMediaDocument):
        doc = message.media.document
        if doc:
            for attr in doc.attributes:
                attr_type = type(attr).__name__
                if "Video" in attr_type:
                    return "video"
                elif "Audio" in attr_type:
                    return "audio"
                elif "Sticker" in attr_type:
                    return "sticker"
                elif "Voice" in attr_type:
                    return "voice"
        return "document"
    elif isinstance(message.media, MessageMediaWebPage):
        return "webpage"
    return "other"


def _serialize_message(message: TelethonMessage, dialog_id: int) -> dict | None:
    if message.action is not None:
        return None
    if not message.text and not message.media:
        return None

    forward_origin = None
    if message.forward:
        fwd = message.forward
        forward_origin = {
            "from_id": fwd.from_id.user_id if hasattr(fwd.from_id, "user_id") else None,
            "from_name": fwd.from_name,
            "date": fwd.date.isoformat() if fwd.date else None,
        }

    sender_name = None
    if message.sender:
        sender_name = _get_entity_name(message.sender)

    return {
        "dialog_id": dialog_id,
        "telegram_id": message.id,
        "sender_id": message.sender_id,
        "sender_name": sender_name,
        "text": message.text or None,
        "media_type": _get_media_type(message),
        "reply_to_id": message.reply_to.reply_to_msg_id if message.reply_to else None,
        "forward_origin": forward_origin,
        "is_edited": message.edit_date is not None,
        "created_at": message.date,
    }


async def _fetch_messages(client, dialog_id, min_id=0, since=None, limit=5000):
    messages = []
    async for message in client.iter_messages(dialog_id, limit=limit, min_id=min_id):
        if since and message.date.replace(tzinfo=None) < since.replace(tzinfo=None):
            break
        serialized = _serialize_message(message, dialog_id)
        if serialized:
            messages.append(serialized)
    return messages


async def list_dialogs():
    """List all available Telegram dialogs."""
    client = _create_client()
    try:
        await client.connect()
        dialogs = []
        async for dialog in client.iter_dialogs(limit=100):
            entity = dialog.entity
            dtype = "private"
            if isinstance(entity, Chat):
                dtype = "group"
            elif isinstance(entity, Channel):
                dtype = "supergroup" if entity.megagroup else "channel"
            dialogs.append({
                "id": dialog.id,
                "name": _get_entity_name(entity),
                "type": dtype,
                "unread": dialog.unread_count,
            })
        return dialogs
    finally:
        await client.disconnect()


async def sync_chat(dialog_id=None, full=False, days=None):
    """Sync messages from Telegram chat."""
    dialog_id = dialog_id or TG_CHAT_ID
    if not dialog_id:
        raise ValueError("TG_CHAT_ID not set. Run `python -m chat dialogs` to find chat ID.")

    init_db()
    state = get_sync_state(dialog_id)
    min_id = 0 if full else (state["last_message_id"] if state else 0)
    since = None
    if days:
        since = datetime.utcnow() - timedelta(days=days)
        min_id = 0

    client = _create_client()
    try:
        await client.connect()
        entity = await client.get_entity(dialog_id)
        chat_name = _get_entity_name(entity)

        print(f"Syncing: {chat_name} (ID: {dialog_id})")
        if min_id:
            print(f"  Incremental from message ID {min_id}")
        elif since:
            print(f"  From {since.strftime('%Y-%m-%d')}")
        else:
            print("  Full sync")

        messages = await _fetch_messages(client, dialog_id, min_id=min_id, since=since)
    finally:
        await client.disconnect()

    if not messages:
        print("  No new messages")
        return {"new": 0, "chat": chat_name}

    new_count = upsert_messages(messages)
    max_id = max(m["telegram_id"] for m in messages)
    update_sync_state(dialog_id, chat_name, max_id)

    print(f"  Fetched {len(messages)} messages, {new_count} new")
    return {"new": new_count, "total_fetched": len(messages), "chat": chat_name}


def run_sync(**kwargs):
    return asyncio.run(sync_chat(**kwargs))


def run_list_dialogs():
    return asyncio.run(list_dialogs())
