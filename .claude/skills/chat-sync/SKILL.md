---
disable-model-invocation: true
---

Синхронизация и обработка сообщений из Telegram-чата проекта.

## Порядок действий

1. Загрузи новые сообщения:
```bash
python -m chat sync
```

2. Классифицируй неклассифицированные сообщения по стримам:
```bash
python -m chat classify
```

3. Обнови саммари стримов:
```bash
python -m chat summarize
```

4. Покажи статус:
```bash
python -m chat status
```

5. Покажи последние новые сообщения (чтобы упомянуть важные).
SQL-запрос к chat.db (колонки: telegram_id, sender_name, text, created_at, stream):
```bash
python -c "
import sqlite3
conn = sqlite3.connect('chat.db')
rows = conn.execute('SELECT created_at, sender_name, text, stream FROM messages ORDER BY telegram_id DESC LIMIT 5').fetchall()
for r in rows:
    print(f'[{r[0]}] {r[1]} ({r[3]}): {(r[2] or \"(media)\")[:200]}')
conn.close()
"
```

6. Кратко сообщи пользователю:
   - Сколько новых сообщений загружено
   - Сколько классифицировано
   - Какие стримы обновились
   - Если есть важные новые сообщения - упомяни

## Опции

- Полная синхронизация: добавь `--full` к команде sync
- За определённый период: `--days N`
- Всё одной командой: `python -m chat update`
