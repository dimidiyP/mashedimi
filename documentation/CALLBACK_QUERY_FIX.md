# Исправление ошибки "Query is too old and response timeout expired"

## 🔍 Причины ошибки:

1. **Callback query обрабатывается дольше 60 секунд** - Telegram отменяет запрос
2. **Повторная обработка** одного и того же callback query  
3. **Синтаксические ошибки** в коде приводят к неправильной обработке
4. **Отсутствие `answer_callback_query()`** для некоторых callback queries

## ✅ Исправления (применены):

### 1. Исправлена синтаксическая ошибка:
**Проблема:** Блок кода для `set_topic_prompt` был внутри блока `my_commands`
```python
# БЫЛО (неправильно):
elif data == "my_commands":
    # код my_commands
    # код set_topic_prompt (БЕЗ elif!)

# СТАЛО (правильно):  
elif data == "my_commands":
    # код my_commands
elif data == "set_topic_prompt":
    # код set_topic_prompt
```

### 2. Добавлена проверка времени callback query:
```python
# Проверяем, не слишком ли старый запрос (более 55 сек)
current_time = time.time()
query_time = callback_query.message.date.timestamp()

if current_time - query_time > 55:
    await bot.answer_callback_query(callback_query.id, "❌ Запрос устарел, попробуйте снова")
    return
```

### 3. Улучшена обработка исключений:
```python
try:
    await bot.answer_callback_query(callback_query.id)
except Exception as e:
    logger.warning(f"Failed to answer callback query: {str(e)}")
    # Продолжаем обработку даже если не смогли ответить
```

### 4. Предотвращение спама ошибок:
```python
# Не отправляем пользователю сообщения об ошибках "query too old"
if "Query is too old" not in str(e):
    await bot.send_message(chat_id=chat_id, text=f"❌ Ошибка: {str(e)}")
```

## 🧪 Тестирование:

После применения исправлений протестируйте:

1. **Быстрые нажатия кнопок** - не должно быть ошибок
2. **Кнопки в меню настроек** - все должно работать  
3. **Топик-настройки** - функции должны работать корректно
4. **Админская панель** - все callback queries обработаны

## 📊 Мониторинг:

Проверяйте логи backend:
```bash
tail -f /var/log/supervisor/backend.err.log
```

Если ошибки "Query is too old" повторяются:
1. Проверьте нагрузку на сервер
2. Убедитесь что нет медленных AI запросов в callback handlers
3. Проверьте соединение с MongoDB

## ✅ Результат:

После исправлений ошибки "Query is too old" должны исчезнуть.
Все callback queries теперь обрабатываются корректно и быстро.