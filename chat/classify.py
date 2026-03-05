"""Classify messages into streams using LLM via OpenRouter."""

import json

from openai import OpenAI

from chat.config import OPENROUTER_API_KEY, OPENROUTER_BASE_URL, LLM_MODEL, CLASSIFY_BATCH_SIZE, STREAMS
from chat.db import get_unclassified_messages, set_message_streams


def _get_client():
    return OpenAI(api_key=OPENROUTER_API_KEY, base_url=OPENROUTER_BASE_URL)


def _build_prompt(messages: list[dict]) -> str:
    streams_desc = "\n".join(
        f'- "{name}": {info["display_name"]} — {info.get("description", "")}'
        for name, info in STREAMS.items()
    )
    msgs_text = "\n".join(
        f'[{i}] ({msg["created_at"]}) {msg["sender_name"]}: {msg["text"][:500]}'
        for i, msg in enumerate(messages)
    )
    return f"""Классифицируй каждое сообщение в один из стримов.

Доступные стримы:
{streams_desc}

Сообщения:
{msgs_text}

Верни JSON-массив имён стримов, по одному на сообщение, в том же порядке.
Пример: ["general", "technical", "financial"]
Верни ТОЛЬКО JSON-массив, без другого текста."""


def classify_batch(messages: list[dict]) -> list[str]:
    client = _get_client()
    response = client.chat.completions.create(
        model=LLM_MODEL,
        max_tokens=1024,
        messages=[{"role": "user", "content": _build_prompt(messages)}],
    )
    text = response.choices[0].message.content.strip()
    if text.startswith("["):
        result = json.loads(text)
    else:
        start = text.find("[")
        end = text.rfind("]") + 1
        result = json.loads(text[start:end])

    valid_streams = set(STREAMS.keys())
    first_stream = next(iter(STREAMS))
    return [s if s in valid_streams else first_stream for s in result]


def run_classify(limit: int = 500) -> dict:
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY not set in .env")

    messages = get_unclassified_messages(limit=limit)
    if not messages:
        print("No unclassified messages")
        return {"classified": 0}

    print(f"Classifying {len(messages)} messages...")
    total_classified = 0

    for i in range(0, len(messages), CLASSIFY_BATCH_SIZE):
        batch = messages[i : i + CLASSIFY_BATCH_SIZE]
        try:
            streams = classify_batch(batch)
            classifications = [(msg["id"], stream) for msg, stream in zip(batch, streams)]
            set_message_streams(classifications)
            total_classified += len(batch)
            print(f"  Batch {i // CLASSIFY_BATCH_SIZE + 1}: {len(batch)} messages classified")
        except Exception as e:
            print(f"  Batch {i // CLASSIFY_BATCH_SIZE + 1} failed: {e}")

    print(f"Total classified: {total_classified}")
    return {"classified": total_classified}
