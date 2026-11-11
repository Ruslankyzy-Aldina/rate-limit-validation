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

## Дальнейшая работа

Добавить проверки pyrate-limiter и throttled-py с Redis, Valkey и DragonFly, а также тесты параллельных запросов, отключения хранилища и X-Forwarded-For.