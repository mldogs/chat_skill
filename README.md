# chat-skill

Telegram-чат как база знаний для [Claude Code](https://docs.anthropic.com/en/docs/claude-code).

Синхронизирует сообщения через Telethon, хранит в SQLite с полнотекстовым поиском, классифицирует по тематическим стримам через LLM, генерирует саммари. Готовые Claude Code Skills в комплекте.

## Что делает

1. **Sync** - загружает сообщения из Telegram-чата через user API (Telethon)
2. **Classify** - классифицирует каждое сообщение в тематический стрим через LLM
3. **Summarize** - генерирует/обновляет markdown-саммари по каждому стриму
4. **Search** - полнотекстовый поиск (FTS5) + LIKE-фоллбэк по всем сообщениям
5. **Send** - отправка сообщений обратно в чат
6. **Context** - собирает контекст (саммари + поиск + последние) для ответов на вопросы

## Быстрый старт

```bash
git clone <repo-url>
cd chat-skill
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Заполни Telegram-креды и ключ OpenRouter

# Найди ID чата
python -m chat dialogs

# Укажи TG_CHAT_ID в .env, затем:
python -m chat update   # sync + classify + summarize
```

### Telegram API

1. Зайди на [my.telegram.org](https://my.telegram.org), создай приложение - получишь `TG_API_ID` и `TG_API_HASH`
2. Сгенерируй StringSession для Telethon:
   ```bash
   python -c "
   from telethon.sync import TelegramClient
   from telethon.sessions import StringSession
   with TelegramClient(StringSession(), API_ID, 'API_HASH') as client:
       print(client.session.save())
   "
   ```
3. Скопируй строку сессии в `TG_SESSION` в `.env`

### OpenRouter

1. Зарегистрируйся на [openrouter.ai](https://openrouter.ai)
2. Создай API-ключ, добавь в `OPENROUTER_API_KEY` в `.env`
3. Модель по умолчанию: `google/gemini-3.1-flash-lite-preview` (дёшево и быстро). Можно изменить через `LLM_MODEL`

## CLI

```
python -m chat sync            # загрузить новые сообщения
python -m chat sync --full     # полная пересинхронизация
python -m chat sync --days 7   # за последние 7 дней
python -m chat dialogs         # список доступных чатов
python -m chat classify        # классифицировать по стримам
python -m chat summarize       # обновить саммари
python -m chat search "..."    # полнотекстовый поиск
python -m chat send "..."      # отправить сообщение
python -m chat context "..."   # собрать контекст для ответа
python -m chat status          # статус индекса
python -m chat update          # полный пайплайн: sync + classify + summarize
```

## Стримы

Сообщения классифицируются по стримам из `streams.json`. Настрой под свой проект:

```json
{
  "backend": {
    "display_name": "Backend",
    "description": "Серверная часть, API, базы данных"
  },
  "frontend": {
    "display_name": "Frontend",
    "description": "UI, компоненты, стили"
  },
  "devops": {
    "display_name": "DevOps",
    "description": "CI/CD, деплой, инфраструктура"
  }
}
```

Саммари сохраняются как markdown в `docs/streams/` и в SQLite-базе.

## Claude Code Skills

В репозитории три готовых скилла в `.claude/skills/`:

| Скилл | Триггер | Что делает |
|-------|---------|-----------|
| `chat-sync` | `/chat-sync` | Пайплайн sync + classify + summarize |
| `chat-ask` | Авто (вопросы по чату) | Поиск по истории чата для ответов на вопросы |
| `chat-send` | `/chat-send` | Составление и отправка сообщения в чат |

Скиллы подхватываются Claude Code автоматически при работе в директории проекта.

## Структура

```
.claude/skills/      -- Claude Code Skills
  chat-sync/         -- синхронизация и обработка
  chat-ask/          -- ответы на вопросы по чату
  chat-send/         -- отправка сообщений
chat/                -- Python-модуль
  config.py          -- загрузка .env и streams.json
  db.py              -- SQLite, FTS5, CRUD
  sync.py            -- синхронизация через Telethon
  classify.py        -- LLM-классификация (батчами)
  summarize.py       -- генерация саммари по стримам
  send.py            -- отправка через Telethon
  context.py         -- сборка контекста для Q&A
  __main__.py        -- CLI
CLAUDE.md            -- инструкции для Claude Code
streams.json         -- определения стримов (настрой под проект)
chat.db              -- SQLite-база (создаётся автоматически, gitignored)
docs/streams/        -- сгенерированные саммари
```

## Лицензия

MIT
