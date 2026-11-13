# Rate limiting для FastAPI

Тестовое приложение проверяет slowapi с Redis. Лимит — 5 запросов в минуту с одного IP.

## Адреса

- FastAPI: http://127.0.0.1:8000
- Redis: localhost:6381 (запускается через Docker Compose)

## Запуск

Команды выполнять в PowerShell из папки проекта.

1. Открыть Docker Desktop и дождаться запуска движка.

2. Создать виртуальное окружение и установить зависимости:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

3. Запустить Redis:

```powershell
docker compose up -d
docker compose exec redis redis-cli ping
```

Ожидаемый ответ: `PONG`.

4. Запустить FastAPI:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.slowapi_app:app --host 127.0.0.1 --port 8000
```

Оставить этот терминал открытым.

## Проверка лимита

Во втором терминале PowerShell выполнить:

```powershell
1..6 | % { try { (iwr http://127.0.0.1:8000/limited -UseBasicParsing).StatusCode } catch { [int]$_.Exception.Response.StatusCode } }
```

Если лимит до проверки не использовался, ожидаются ответы: `200, 200, 200, 200, 200, 429`.

Маршрут http://127.0.0.1:8000/health проверяет, что приложение запущено.

## Первый результат

При первой проверке получены ответы: `200, 429, 429, 429, 429, 429`. До запуска команды маршрут `/limited` уже вызывался, поэтому часть лимита была использована.

Результат повторной проверки после ожидания более одной минуты: **[вписать фактические ответы]**.

## Остановка

Остановить FastAPI сочетанием `Ctrl+C`, затем выполнить:

```powershell
docker compose down
```


## Поведение при отключении Redis

Во время работы FastAPI контейнер Redis был остановлен:

```powershell
docker compose stop redis
```

После этого запрос к `/limited` вернул:

```text
500 Internal Server Error
```

В traceback было зафиксировано исключение:

```text
redis.exceptions.ConnectionError:
Error 10061 connecting to localhost:6381
```

Slowapi проверял лимит `moving-window` через Lua-команду Redis `EVALSHA`. Redis был недоступен, поэтому соединение завершилось ошибкой.

В приложении были установлены параметры:

```python
swallow_errors=False
in_memory_fallback_enabled=False
```

Поэтому ошибка не была подавлена и резервное хранилище в памяти не использовалось. Исключение дошло до FastAPI, который вернул HTTP 500.

Запрос не был пропущен, поэтому поведение является **fail-closed**, но ошибка возвращается неконтролируемым ответом HTTP 500 вместо HTTP 503.

После повторного запуска Redis команда `redis-cli ping` вернула `PONG`.