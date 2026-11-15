# Rate limiting для FastAPI

Тестовое приложение проверяет slowapi с Redis, Valkey и DragonFly. Настроен лимит — 5 запросов в минуту с одного IP. Тесты пока выполнялись вручную в PowerShell.

## Адреса хранилищ

| Хранилище | Адрес |
|---|---|
| Redis | `redis://localhost:6381/0` |
| Valkey | `valkey://localhost:6382/0` |
| DragonFly | `redis://localhost:6383/0` |

FastAPI: <http://127.0.0.1:8000>

## Запуск

Команды выполняются в PowerShell из папки проекта.

1. Запусти Docker Desktop и дождись, пока Docker Engine будет готов.

2. Установи зависимости:

   ```powershell
   py -3 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   ```

3. Запусти контейнеры и проверь доступность хранилищ:

   ```powershell
   docker compose up -d
   docker compose exec redis redis-cli ping
   docker compose exec valkey valkey-cli ping
   docker compose exec dragonfly redis-cli ping
   ```

   Для каждого запущенного хранилища ожидается ответ `PONG`.

4. В PowerShell задай адрес нужного хранилища и запусти приложение. Команды для выбранного хранилища выполняются **в одном и том же окне**.

   Redis:

   ```powershell
   $env:REDIS_URL = "redis://localhost:6381/0"
   .\.venv\Scripts\python.exe -m uvicorn app.slowapi_app:app --host 127.0.0.1 --port 8000
   ```

   Valkey:

   ```powershell
   $env:REDIS_URL = "valkey://localhost:6382/0"
   .\.venv\Scripts\python.exe -m uvicorn app.slowapi_app:app --host 127.0.0.1 --port 8000
   ```

   DragonFly:

   ```powershell
   $env:REDIS_URL = "redis://localhost:6383/0"
   .\.venv\Scripts\python.exe -m uvicorn app.slowapi_app:app --host 127.0.0.1 --port 8000
   ```

   Перед переключением на другое хранилище останови Uvicorn сочетанием `Ctrl+C`. Затем задай новый `REDIS_URL` и запусти приложение снова.

## Проверка приложения и лимита

Проверка состояния приложения:

```powershell
Invoke-WebRequest "http://127.0.0.1:8000/health" -UseBasicParsing
```

Ожидается статус `200`.

Чтобы проверить лимит, отправь шесть запросов к `/limited`:

```powershell
1..6 | ForEach-Object {
    try {
        (Invoke-WebRequest "http://127.0.0.1:8000/limited" -UseBasicParsing).StatusCode
    } catch {
        [int]$_.Exception.Response.StatusCode
    }
}
```

При неиспользованном лимите ожидаются пять ответов `200`, затем `429`. Перед повторной проверкой подожди больше минуты после последних запросов к `/limited`.

## Результаты обычной проверки

Для каждого хранилища `/health` вернул `200`, а при шести запросах к `/limited` получены пять ответов `200` и один `429`.

- **Redis:** подключение проверено через `redis://localhost:6381/0`.
- **Valkey:** подключение проверено через `valkey://localhost:6382/0`.
- **DragonFly:** подключение проверено через `redis://localhost:6383/0`.

При первой проверке Redis получилось `200, 429, 429, 429, 429, 429`, потому что до неё маршрут `/limited` уже вызывался. После ожидания больше минуты повторная проверка дала пять `200` и один `429`.

## Параллельные запросы

Для каждого хранилища было отправлено 20 параллельных запросов к `/limited`.

| Хранилище | `200` | `429` | Результат |
|---|---:|---:|---|
| Redis | 5 | 15 | Превышения лимита не обнаружено |
| Valkey | 5 | 15 | Превышения лимита не обнаружено |
| DragonFly | 5 | 15 | Превышения лимита не обнаружено |

## Поведение при отключении хранилища

Во время работы приложения соответствующий контейнер останавливали, затем отправляли запрос к `/limited`. Для всех трёх хранилищ запрос вернул HTTP `500`.

- **Redis:** в traceback — `redis.exceptions.ConnectionError` при подключении к `localhost:6381`.
- **Valkey:** в traceback — `valkey.exceptions.ConnectionError` при подключении к `localhost:6382`.
- **DragonFly:** в traceback — `redis.exceptions.ConnectionError` при подключении к `localhost:6383`.

Для DragonFly использовался Redis-клиент, поэтому ошибка имеет тип `redis.exceptions.ConnectionError`.

## Следующий этап: pyrate-limiter 4.5.1

В проект добавлено отдельное приложение `app.pyrate_limiter_app`. Оно не изменяет
конфигурацию `slowapi` и проверяет два алгоритма с Redis-совместимым хранилищем:

- `sliding-window` — точный sliding-window log через `RedisBucket`;
- `token-bucket` — GCRA/token bucket через `StateBucket` и `RedisStateStore`.

Установи зависимость и запускай приложение в отдельном окне PowerShell:

```powershell
\.venv\Scripts\python.exe -m pip install -r requirements.txt
$env:REDIS_URL = "redis://localhost:6381/0"
$env:PYRATE_ALGORITHM = "sliding-window"
$env:PYRATE_BUCKET_KEY = "pyrate-redis-sliding"
\.venv\Scripts\python.exe -m uvicorn app.pyrate_limiter_app:app --host 127.0.0.1 --port 8001
```

Для token bucket замени `PYRATE_ALGORITHM` на `token-bucket` и используй новый
`PYRATE_BUCKET_KEY`. Для Valkey укажи `valkey://localhost:6382/0`, для DragonFly
— `redis://localhost:6383/0`. На каждом чистом ключе ожидаются пять ответов
`200`, затем `429` для sliding-window. Token bucket также допускает burst,
поэтому его поведение дополнительно проверяй серией запросов после простоя.

Приложение автоматически преобразует `valkey://` в `redis://` для `redis-py`:
Valkey совместим с Redis-протоколом, но `redis-py` принимает только схему
`redis://`.

### Результаты проверки pyrate-limiter

Для token bucket на чистых ключах выполнены серии из шести последовательных
запросов: для Redis, Valkey и DragonFly получено `200, 200, 200, 200, 200, 429`.

Для конкурентной проверки отправлено 20 запросов одновременно. На всех трёх
хранилищах получено 5 ответов `200` и 15 ответов `429`.

В приложении заданы параметры:

```python
swallow_errors=False
in_memory_fallback_enabled=False
```

Из-за этого ошибка хранилища не подавляется и резервное хранилище в памяти не используется. Запрос не проходит через обработчик лимита, но клиент получает HTTP `500`, а не `503`. Это поведение можно описать как fail-closed с необработанной ошибкой сервера.

После каждой проверки остановленное хранилище запускали снова и проверяли командой `ping`; оно отвечало `PONG`.

## Проверка `X-Forwarded-For`

Тест выполнен напрямую через localhost, без отдельного reverse proxy.

При обычном запуске Uvicorn первые пять запросов с заголовком `X-Forwarded-For: 198.51.100.10` получили `200`. Шестой запрос с заголовком `X-Forwarded-For: 203.0.113.20` также получил `200`. Это показывает, что в проверенной конфигурации разные значения заголовка могли дать разные ключи лимитера.

При повторном запуске Uvicorn с параметром `--no-proxy-headers` шестой запрос с другим значением заголовка получил `429`. В этой конфигурации заголовок не позволил получить новый лимит.

Проверка с `--no-proxy-headers` не заменяет отдельный тест за реальным reverse proxy. В рабочем развертывании следует доверять forwarded-заголовкам только от известного прокси.

## Остановка

Останови FastAPI сочетанием `Ctrl+C`, затем останови контейнеры:

```powershell
docker compose down
```
