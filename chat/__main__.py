"""CLI entry point: python -m chat <command>"""

import argparse
import sys

from chat.db import init_db, get_stats, search_messages


def cmd_sync(args):
    from chat.sync import run_sync
    run_sync(
        dialog_id=args.chat_id,
        full=args.full,
        days=args.days,
    )


def cmd_dialogs(args):
    from chat.sync import run_list_dialogs
    dialogs = run_list_dialogs()
    print(f"\n{'ID':<15} {'Type':<12} {'Unread':<8} Name")
    print("-" * 60)
    for d in dialogs:
        print(f"{d['id']:<15} {d['type']:<12} {d['unread']:<8} {d['name']}")
    print(f"\nTotal: {len(dialogs)} dialogs")
    print("\nSet TG_CHAT_ID in .env to the desired chat ID")


def cmd_classify(args):
    from chat.classify import run_classify
    run_classify(limit=args.limit)


def cmd_summarize(args):
    from chat.summarize import run_summarize
    run_summarize(min_messages=args.min_messages)


def cmd_search(args):
    init_db()
    results = search_messages(args.query, limit=args.limit)
    if not results:
        print("No results found")
        return
    print(f"\nFound {len(results)} results for '{args.query}':\n")
    for r in results:
        stream = f"[{r['stream']}]" if r.get("stream") else "[?]"
        print(f"  {r['created_at']} {stream} {r['sender_name']}:")
        text = r["text"][:200]
        print(f"    {text}")
        print()


def cmd_status(args):
    init_db()
    stats = get_stats()
    print("\n=== Chat Index Status ===\n")
    if stats["last_sync"]:
        s = stats["last_sync"]
        print(f"Chat: {s['dialog_name']} (ID: {s['dialog_id']})")
        print(f"Last synced: {s['last_synced_at']}")
        print(f"Last message ID: {s['last_message_id']}")
    else:
        print("No sync performed yet")
    print(f"\nMessages: {stats['total_messages']} total, {stats['classified']} classified, {stats['unclassified']} pending")
    print("\nStreams:")
    for s in stats["streams"]:
        updated = f" (updated: {s['summary_updated_at'][:10]})" if s.get("summary_updated_at") else ""
        print(f"  {s['display_name']:<35} {s['message_count']:>5} msgs{updated}")


def cmd_send(args):
    from chat.send import run_send
    text = args.text
    if text == "-":
        text = sys.stdin.read().strip()
    if not text:
        print("Error: empty message")
        sys.exit(1)
    msg_id = run_send(text)
    print(f"Sent (message ID: {msg_id})")


def cmd_context(args):
    from chat.context import run_context
    init_db()
    run_context(args.query)


def cmd_update(args):
    """Run full pipeline: sync -> classify -> summarize."""
    print("=== Step 1: Sync ===")
    cmd_sync(args)
    print("\n=== Step 2: Classify ===")
    cmd_classify(args)
    print("\n=== Step 3: Summarize ===")
    cmd_summarize(args)
    print("\n=== Done ===")
    cmd_status(args)


def main():
    parser = argparse.ArgumentParser(
        prog="python -m chat",
        description="Telegram chat indexer for Claude Code",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # sync
    p = sub.add_parser("sync", help="Sync messages from Telegram")
    p.add_argument("--chat-id", type=int, help="Override TG_CHAT_ID")
    p.add_argument("--full", action="store_true", help="Full sync (all history)")
    p.add_argument("--days", type=int, help="Sync last N days")
    p.set_defaults(func=cmd_sync)

    # dialogs
    p = sub.add_parser("dialogs", help="List available Telegram chats")
    p.set_defaults(func=cmd_dialogs)

    # classify
    p = sub.add_parser("classify", help="Classify unclassified messages")
    p.add_argument("--limit", type=int, default=500, help="Max messages to classify")
    p.set_defaults(func=cmd_classify)

    # summarize
    p = sub.add_parser("summarize", help="Generate/update stream summaries")
    p.add_argument("--min-messages", type=int, default=3, help="Min messages to generate summary")
    p.set_defaults(func=cmd_summarize)

    # search
    p = sub.add_parser("search", help="Search messages")
    p.add_argument("query", help="Search query")
    p.add_argument("--limit", type=int, default=20, help="Max results")
    p.set_defaults(func=cmd_search)

    # status
    p = sub.add_parser("status", help="Show index status")
    p.set_defaults(func=cmd_status)

    # send
    p = sub.add_parser("send", help="Send message to Telegram chat")
    p.add_argument("text", help='Message text (use "-" to read from stdin)')
    p.set_defaults(func=cmd_send)

    # context
    p = sub.add_parser("context", help="Get project context for a query")
    p.add_argument("query", help="Question or topic to search for")
    p.set_defaults(func=cmd_context)

    # update (all-in-one)
    p = sub.add_parser("update", help="Full pipeline: sync -> classify -> summarize")
    p.add_argument("--chat-id", type=int, help="Override TG_CHAT_ID")
    p.add_argument("--full", action="store_true", help="Full sync")
    p.add_argument("--days", type=int, help="Sync last N days")
    p.add_argument("--limit", type=int, default=500, help="Max messages to classify")
    p.add_argument("--min-messages", type=int, default=3, help="Min messages for summary")
    p.set_defaults(func=cmd_update)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
