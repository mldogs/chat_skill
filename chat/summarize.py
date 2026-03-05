"""Generate and update stream summaries using LLM via OpenRouter."""

from openai import OpenAI

from chat.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, LLM_MODEL, STREAMS_DIR
from chat.db import get_stream_info, get_stream_messages, update_stream_summary


def _get_client():
    return OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)


def _build_summary_prompt(display_name, current_summary, messages):
    msgs_text = "\n".join(
        f'[{msg["created_at"]}] {msg["sender_name"]}: {msg["text"][:800]}'
        for msg in messages if msg.get("text")
    )
    if current_summary:
        return f"""Обнови саммари стрима "{display_name}" на основе новых сообщений.

Текущее саммари:
{current_summary}

Новые сообщения:
{msgs_text}

Напиши обновлённое саммари. Структура:
1. **Текущий статус** - что решено, на чём остановились
2. **Ключевые решения** - принятые решения с датами
3. **Открытые вопросы** - нерешённые вопросы и блокеры
4. **Следующие шаги** - запланированные действия

Будь конкретным, указывай даты и имена участников. Не дублируй информацию."""
    else:
        return f"""Создай саммари стрима "{display_name}" на основе сообщений чата.

Сообщения:
{msgs_text}

Напиши саммари. Структура:
1. **Текущий статус** - что решено, на чём остановились
2. **Ключевые решения** - принятые решения с датами
3. **Открытые вопросы** - нерешённые вопросы и блокеры
4. **Следующие шаги** - запланированные действия

Будь конкретным, указывай даты и имена участников."""


def generate_summary(stream_name, display_name, current_summary, messages):
    client = _get_client()
    response = client.chat.completions.create(
        model=LLM_MODEL,
        max_tokens=2048,
        messages=[{"role": "user", "content": _build_summary_prompt(
            display_name, current_summary, messages
        )}],
    )
    return response.choices[0].message.content.strip()


def _write_stream_markdown(stream_name, display_name, summary, message_count):
    STREAMS_DIR.mkdir(parents=True, exist_ok=True)
    path = STREAMS_DIR / f"{stream_name}.md"
    content = f"""# {display_name}

> Auto-generated from Telegram chat

**Messages in stream:** {message_count}

---

{summary}
"""
    path.write_text(content, encoding="utf-8")


def run_summarize(min_messages: int = 3) -> dict:
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY not set in .env")

    streams = get_stream_info()
    updated = []

    for stream in streams:
        name = stream["name"]
        if stream["message_count"] < min_messages:
            print(f"  {stream['display_name']}: skipped ({stream['message_count']} msgs, need {min_messages})")
            continue

        since = stream.get("summary_updated_at")
        messages = get_stream_messages(name, since=since)

        if not messages:
            print(f"  {stream['display_name']}: no new messages since last summary")
            continue

        print(f"  {stream['display_name']}: summarizing {len(messages)} messages...")
        try:
            summary = generate_summary(
                name, stream["display_name"], stream.get("summary"), messages,
            )
            update_stream_summary(name, summary)
            _write_stream_markdown(name, stream["display_name"], summary, stream["message_count"])
            updated.append(name)
            print(f"    Done")
        except Exception as e:
            print(f"    Failed: {e}")

    print(f"\nUpdated {len(updated)} stream summaries")
    return {"updated": updated}
