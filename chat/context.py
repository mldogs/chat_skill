"""Build context for answering questions about the project."""

from chat.db import get_connection, get_stream_info, search_messages


def get_recent_messages(limit: int = 30) -> list[dict]:
    conn = get_connection()
    rows = conn.execute(
        """SELECT sender_name, text, created_at, stream
           FROM messages WHERE text IS NOT NULL AND text != ''
           ORDER BY created_at DESC LIMIT ?""",
        (limit,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in reversed(rows)]


def search_broad(query: str, limit: int = 30) -> list[dict]:
    fts_results = search_messages(query, limit=limit)
    conn = get_connection()
    like_rows = conn.execute(
        """SELECT id, telegram_id, sender_name, text, created_at, stream
           FROM messages
           WHERE text LIKE ? AND text IS NOT NULL
           ORDER BY created_at DESC LIMIT ?""",
        (f"%{query}%", limit),
    ).fetchall()
    conn.close()

    seen_ids = {r["id"] for r in fts_results}
    combined = list(fts_results)
    for r in like_rows:
        r = dict(r)
        if r["id"] not in seen_ids:
            combined.append(r)
            seen_ids.add(r["id"])

    combined.sort(key=lambda x: x["created_at"])
    return combined[:limit]


def build_context(query: str) -> str:
    parts = []

    streams = get_stream_info()
    summaries = [s for s in streams if s.get("summary")]
    if summaries:
        parts.append("=== STREAM SUMMARIES ===\n")
        for s in summaries:
            parts.append(f"## {s['display_name']} ({s['message_count']} messages)")
            parts.append(s["summary"])
            parts.append("")

    results = search_broad(query, limit=20)
    if results:
        parts.append("\n=== RELEVANT MESSAGES ===\n")
        for r in results:
            stream_tag = f"[{r['stream']}]" if r.get("stream") else ""
            parts.append(f"{r['created_at']} {stream_tag} {r.get('sender_name', '?')}:")
            text = r["text"][:500] if r.get("text") else "(no text)"
            parts.append(f"  {text}\n")

    recent = get_recent_messages(limit=15)
    if recent:
        parts.append("\n=== RECENT MESSAGES ===\n")
        for r in recent:
            parts.append(f"{r['created_at']} {r.get('sender_name', '?')}:")
            text = r["text"][:300] if r.get("text") else "(no text)"
            parts.append(f"  {text}\n")

    return "\n".join(parts)


def run_context(query: str) -> str:
    ctx = build_context(query)
    print(ctx)
    return ctx
