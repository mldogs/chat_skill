# Chat Skill

Индексатор Telegram-чата для Claude Code. Синхронизирует сообщения, классифицирует по тематическим стримам, генерирует саммари, позволяет искать и отправлять сообщения.

## Модуль chat/

- **БД:** `chat.db` (SQLite) - индекс всех сообщений с полнотекстовым поиском (FTS5)
- **Стримы:** сообщения классифицируются по тематическим стримам из `streams.json`
- **Саммари:** автогенерируемые в `docs/streams/`

### CLI

```
python -m chat sync          # загрузить новые сообщения
python -m chat classify      # классифицировать по стримам
python -m chat summarize     # обновить саммари
python -m chat search "..."  # полнотекстовый поиск
python -m chat send "..."    # отправить сообщение в чат
python -m chat context "..."  # собрать контекст для ответа на вопрос
python -m chat status        # статус индекса
python -m chat update        # sync + classify + summarize
```

## Настройка

1. Скопировать `.env.example` в `.env` и заполнить:
   - `TG_API_ID`, `TG_API_HASH`, `TG_SESSION` - Telegram API (Telethon)
   - `TG_CHAT_ID` - ID чата (узнать через `python -m chat dialogs`)
   - `OPENROUTER_API_KEY` - ключ OpenRouter для LLM
   - `LLM_MODEL` - модель (по умолчанию claude-haiku-4-5)

2. Настроить стримы в `streams.json` под свой проект

## Конвенции

- Пароли и ключи только в `.env` (gitignored)
- Для Telegram: без markdown-разметки, без длинных тире
