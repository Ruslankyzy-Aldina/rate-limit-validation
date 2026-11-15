# Rate limiting для FastAPI

Исходный код тестов и обновлённый отчёт: [github.com/Ruslankyzy-Aldina/rate-limit-validation](https://github.com/Ruslankyzy-Aldina/rate-limit-validation).

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

## Проверка pyrate-limiter 4.5.1

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

Итог: `pyrate-limiter 4.5.1` совместим с Redis, Valkey и DragonFly через
Redis-протокол. Sliding-window log и token bucket корректно ограничивают
конкурентные запросы, а при потере backend-запрос завершается HTTP `500`, без
перехода на память процесса.

## Сравнительный вывод

| Критерий | slowapi | pyrate-limiter | throttled-py |
|---|---|---|
| Интеграция с FastAPI | Декоратор маршрута и готовый обработчик `429` | Ограничитель вызывается из обработчика приложения | Async-декоратор и готовый обработчик `429` |
| Проверенный алгоритм | `moving-window` через `limits` | Sliding-window log и token bucket | Token bucket |
| Redis-compatible backend | Redis, Valkey, DragonFly | Redis, Valkey, DragonFly через `redis-py` | Redis, Valkey, DragonFly через `redis-py` |
| Конкурентная серия 20 запросов | 5×200, 15×429 | 5×200, 15×429 | 5×200, 15×429 |
| Backend недоступен | HTTP 500 при отключённых fallback’ах | HTTP 500 | HTTP 503 |
| Burst-поведение | Зависит от стратегии `limits` | Token bucket допускает burst до ёмкости bucket | Token bucket с burst по quota DSL |

### Практический выбор

Для обычного FastAPI-приложения с простым лимитом и минимальным собственным
кодом удобны `slowapi` и `throttled-py`: лимит задаётся декоратором, а обработка
`429` уже подключена. `pyrate-limiter` лучше подходит, когда требуется явно
выбирать алгоритм, использовать token bucket или вызывать ограничитель из
собственной бизнес-логики. `throttled-py` отдельно выделяется контролируемым
`503` при недоступности backend.

Обе библиотеки в этой конфигурации требуют доступного внешнего хранилища.
Если Redis, Valkey или DragonFly недоступен, приложение не переключается на
локальную память и возвращает `500`; для production следует добавить отдельную
политику обработки ошибок, например контролируемый `503`, health checks и
мониторинг backend.

### Поведение при остановке хранилища

Для каждого backend-контейнера приложение запускалось с соответствующим Redis-
совместимым адресом, после чего контейнер временно останавливался. Запрос к
`/limited` возвращал HTTP `500` для Redis, Valkey и DragonFly. После запуска
контейнеры снова отвечали `PONG`.

В приложении заданы параметры:

```python
swallow_errors=False
in_memory_fallback_enabled=False
```

Из-за этого ошибка хранилища не подавляется и резервное хранилище в памяти не используется. Запрос не проходит через обработчик лимита, но клиент получает HTTP `500`, а не `503`. Это поведение можно описать как fail-closed с необработанной ошибкой сервера.

После каждой проверки остановленное хранилище запускали снова и проверяли командой `ping`; оно отвечало `PONG`.

## Проверка throttled-py 3.5.0

Добавлено отдельное приложение `app.throttled_app` и скрипт
`tests/run_matrix.ps1`. Интеграция использует официальный async FastAPI
декоратор `throttled.asyncio.contrib.fastapi.Limiter` и `RedisStore`.

Для Redis, Valkey и DragonFly результаты одинаковые:

- последовательные запросы: `200, 200, 200, 200, 200, 429`;
- 20 параллельных запросов: 5 ответов `200` и 15 ответов `429`;
- пять запросов с одним `X-Forwarded-For` и запрос с другим адресом: новый
  forwarded-адрес получил `200`;
- остановка backend во время работы: HTTP `503`, затем после запуска контейнера
  `PONG`.

Это отличается от текущих интеграций `slowapi` и `pyrate-limiter`, которые при
потере хранилища в данной конфигурации возвращают HTTP `500`. В `throttled-py`
ошибка backend явно преобразуется FastAPI-интеграцией в `503`.

### Откуда берётся HTTP 500

Это не ответ Redis и не специальный код лимитера. Это необработанная ошибка
подключения, которую Uvicorn/FastAPI превращает в обычный Internal Server Error:

- в `slowapi` явно установлены `swallow_errors=False` и
  `in_memory_fallback_enabled=False`; поэтому `ConnectionError` из backend
  не подавляется и не заменяется локальным хранилищем;
- в `pyrate-limiter` вызов `RedisBucket`/`RedisStateStore` также пробрасывает
  ошибку клиента Redis из `try_acquire`, а приложение не регистрирует отдельный
  обработчик `redis.exceptions.ConnectionError`;
- в `throttled-py` FastAPI-интеграция перехватывает `StoreUnavailableError` и
  создаёт `HTTPException(status_code=503, detail="Rate limit store unavailable")`.

Таким образом, наблюдение подтверждено и экспериментом, и исходным кодом:
`500` означает отсутствие прикладной политики обработки отказа, а `503` —
явно реализованную политику «сервис временно недоступен».

### Итог полной матрицы

Автоматический `tests/run_all.ps1` выполнен в Windows PowerShell 5.1 для всех
девяти комбинаций. В каждой комбинации последовательный тест дал
`200,200,200,200,200,429`, параллельный тест — `5×200` и `15×429`.

| Лимитер | Redis | Valkey | DragonFly |
|---|---:|---:|---:|
| `slowapi` | parallel OK / 500 | parallel OK / 500 | parallel OK / 500 |
| `pyrate-limiter` | parallel OK / 500 | parallel OK / 500 | parallel OK / 500 |
| `throttled-py` | parallel OK / 503 | parallel OK / 503 | parallel OK / 503 |

Во всех девяти запусках после остановки backend контейнер был автоматически
запущен обратно и отвечал `PONG`.

### X-Forwarded-For: важное различие

В тесте с обычным Uvicorn `slowapi` при смене `X-Forwarded-For` получил новый
лимит (`200`), то есть доверял forwarded-адресу. Запуск с `--no-proxy-headers`
устраняет это поведение и даёт `429` для шестого запроса. Поэтому forwarded-
заголовки нельзя принимать от произвольного клиента без доверенного reverse
proxy.

В текущем приложении `pyrate-limiter` ключ строится из `request.client.host`.
При прямом запуске на localhost смена заголовка в проверенной серии не создала
новый ключ и дала `429`; это безопаснее по умолчанию, но не является заменой
настройке доверенного proxy.

### Воспроизводимый скрипт

После запуска любого приложения на порту `8000` выполни:

```powershell
.\tests\run_matrix.ps1 -BaseUrl http://127.0.0.1:8000
```

Для полного прогона всех трёх приложений на всех трёх backend’ах используй
оркестратор. Он запускает приложение, выполняет последовательный, параллельный
и `X-Forwarded-For` тесты, останавливает backend и затем восстанавливает его:

```powershell
.\tests\run_all.ps1
```

`run_all.ps1` рассчитан на выделенные тестовые контейнеры из этого
`docker-compose.yml`: между сценариями он выполняет `FLUSHDB`, чтобы лимиты
разных тестов не влияли друг на друга. Не запускай его против Redis DB с
данными, которые нужно сохранить.

Источники API, сверенные с установленным исходным кодом и документацией:

- [slowapi](https://github.com/laurentS/slowapi);
- [pyrate-limiter](https://github.com/vutran1710/PyrateLimiter);
- [throttled-py](https://github.com/ZhuoZhuoCrayon/throttled-py);
- [throttled-py FastAPI integration](https://throttled-py.readthedocs.io/en/latest/contrib/fastapi.html).

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
