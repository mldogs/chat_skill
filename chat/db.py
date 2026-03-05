"""SQLite database: schema, queries, full-text search."""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from chat.config import DB_PATH, STREAMS


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: Path = DB_PATH):
    """Create tables and indexes."""
    conn = get_connection(db_path)
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            telegram_id INTEGER UNIQUE NOT NULL,
            dialog_id INTEGER NOT NULL,
            sender_id INTEGER,
            sender_name TEXT,
            text TEXT,
            created_at TEXT NOT NULL,
            reply_to_id INTEGER,
            forward_from TEXT,
            media_type TEXT,
            is_edited INTEGER DEFAULT 0,
            stream TEXT,
            classified_at TEXT,
            raw_data TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_messages_dialog ON messages(dialog_id);
        CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at);
        CREATE INDEX IF NOT EXISTS idx_messages_stream ON messages(stream);
        CREATE INDEX IF NOT EXISTS idx_messages_unclassified
            ON messages(stream) WHERE stream IS NULL;

        CREATE TABLE IF NOT EXISTS streams (
            name TEXT PRIMARY KEY,
            display_name TEXT NOT NULL,
            description TEXT,
            summary TEXT,
            summary_updated_at TEXT,
            message_count INTEGER DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS sync_state (
            dialog_id INTEGER PRIMARY KEY,
            dialog_name TEXT,
            last_message_id INTEGER DEFAULT 0,
            last_synced_at TEXT
        );

        CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
            text, sender_name,
            content='messages', content_rowid='id',
            tokenize='unicode61'
        );

        CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
            INSERT INTO messages_fts(rowid, text, sender_name)
            VALUES (new.id, new.text, new.sender_name);
        END;

        CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE OF text ON messages BEGIN
            INSERT INTO messages_fts(messages_fts, rowid, text, sender_name)
            VALUES ('delete', old.id, old.text, old.sender_name);
            INSERT INTO messages_fts(rowid, text, sender_name)
            VALUES (new.id, new.text, new.sender_name);
        END;

        CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
            INSERT INTO messages_fts(messages_fts, rowid, text, sender_name)
            VALUES ('delete', old.id, old.text, old.sender_name);
        END;
    """)

    for name, info in STREAMS.items():
        conn.execute(
            """INSERT OR IGNORE INTO streams (name, display_name, description)
               VALUES (?, ?, ?)""",
            (name, info["display_name"], info.get("description", "")),
        )
    conn.commit()
    conn.close()


def upsert_messages(messages: list[dict], db_path: Path = DB_PATH) -> int:
    """Insert or update messages. Returns count of new messages."""
    conn = get_connection(db_path)
    new_count = 0
    for msg in messages:
        raw = json.dumps(msg, default=str, ensure_ascii=False)
        cursor = conn.execute(
            """INSERT INTO messages
               (telegram_id, dialog_id, sender_id, sender_name, text,
                created_at, reply_to_id, forward_from, media_type, is_edited, raw_data)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(telegram_id) DO UPDATE SET
                   text = excluded.text,
                   is_edited = excluded.is_edited,
                   raw_data = excluded.raw_data""",
            (
                msg["telegram_id"],
                msg["dialog_id"],
                msg.get("sender_id"),
                msg.get("sender_name"),
                msg.get("text"),
                msg["created_at"].isoformat() if isinstance(msg["created_at"], datetime) else msg["created_at"],
                msg.get("reply_to_id"),
                json.dumps(msg.get("forward_origin"), ensure_ascii=False) if msg.get("forward_origin") else None,
                msg.get("media_type"),
                int(msg.get("is_edited", False)),
                raw,
            ),
        )
        if cursor.lastrowid:
            new_count += 1
    conn.commit()
    conn.close()
    return new_count


def get_unclassified_messages(limit: int = 100, db_path: Path = DB_PATH) -> list[dict]:
    conn = get_connection(db_path)
    rows = conn.execute(
        """SELECT id, telegram_id, sender_name, text, created_at, reply_to_id
           FROM messages
           WHERE stream IS NULL AND text IS NOT NULL AND text != ''
           ORDER BY created_at ASC LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def set_message_streams(classifications: list[tuple[int, str]], db_path: Path = DB_PATH):
    conn = get_connection(db_path)
    now = datetime.utcnow().isoformat()
    for msg_id, stream in classifications:
        conn.execute(
            "UPDATE messages SET stream = ?, classified_at = ? WHERE id = ?",
            (stream, now, msg_id),
        )
    conn.execute("""
        UPDATE streams SET message_count = (
            SELECT COUNT(*) FROM messages WHERE messages.stream = streams.name
        )
    """)
    conn.commit()
    conn.close()


def get_stream_messages(stream_name: str, since: str | None = None,
                        limit: int = 500, db_path: Path = DB_PATH) -> list[dict]:
    conn = get_connection(db_path)
    if since:
        rows = conn.execute(
            """SELECT id, telegram_id, sender_name, text, created_at
               FROM messages WHERE stream = ? AND created_at > ?
               ORDER BY created_at ASC LIMIT ?""",
            (stream_name, since, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT id, telegram_id, sender_name, text, created_at
               FROM messages WHERE stream = ?
               ORDER BY created_at ASC LIMIT ?""",
            (stream_name, limit),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_stream_info(db_path: Path = DB_PATH) -> list[dict]:
    conn = get_connection(db_path)
    rows = conn.execute(
        "SELECT name, display_name, description, summary, summary_updated_at, message_count FROM streams"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_stream_summary(stream_name: str, summary: str, db_path: Path = DB_PATH):
    conn = get_connection(db_path)
    conn.execute(
        "UPDATE streams SET summary = ?, summary_updated_at = ? WHERE name = ?",
        (summary, datetime.utcnow().isoformat(), stream_name),
    )
    conn.commit()
    conn.close()


def search_messages(query: str, limit: int = 20, db_path: Path = DB_PATH) -> list[dict]:
    conn = get_connection(db_path)
    rows = conn.execute(
        """SELECT m.id, m.telegram_id, m.sender_name, m.text, m.created_at, m.stream, rank
           FROM messages_fts fts
           JOIN messages m ON m.id = fts.rowid
           WHERE messages_fts MATCH ?
           ORDER BY rank LIMIT ?""",
        (query, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_sync_state(dialog_id: int, db_path: Path = DB_PATH) -> dict | None:
    conn = get_connection(db_path)
    row = conn.execute(
        "SELECT * FROM sync_state WHERE dialog_id = ?", (dialog_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_sync_state(dialog_id: int, dialog_name: str,
                      last_message_id: int, db_path: Path = DB_PATH):
    conn = get_connection(db_path)
    conn.execute(
        """INSERT INTO sync_state (dialog_id, dialog_name, last_message_id, last_synced_at)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(dialog_id) DO UPDATE SET
               last_message_id = excluded.last_message_id,
               last_synced_at = excluded.last_synced_at""",
        (dialog_id, dialog_name, last_message_id, datetime.utcnow().isoformat()),
    )
    conn.commit()
    conn.close()


def get_stats(db_path: Path = DB_PATH) -> dict:
    conn = get_connection(db_path)
    total = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    classified = conn.execute("SELECT COUNT(*) FROM messages WHERE stream IS NOT NULL").fetchone()[0]
    unclassified = conn.execute(
        "SELECT COUNT(*) FROM messages WHERE stream IS NULL AND text IS NOT NULL AND text != ''"
    ).fetchone()[0]
    streams = conn.execute(
        "SELECT name, display_name, message_count, summary_updated_at FROM streams ORDER BY message_count DESC"
    ).fetchall()
    sync = conn.execute("SELECT * FROM sync_state").fetchone()
    conn.close()
    return {
        "total_messages": total,
        "classified": classified,
        "unclassified": unclassified,
        "streams": [dict(s) for s in streams],
        "last_sync": dict(sync) if sync else None,
    }
