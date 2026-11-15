"""FastAPI experiment for pyrate-limiter 4.5.1 with Redis-compatible stores."""

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from redis import Redis

from pyrate_limiter import (
    Duration,
    Limiter,
    Rate,
    RedisBucket,
    RedisStateStore,
    StateBucket,
    TokenBucket,
)

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6381/0")
# redis-py speaks the Redis protocol but only accepts redis:// as its URL scheme.
CLIENT_URL = REDIS_URL.replace("valkey://", "redis://", 1)
ALGORITHM = os.getenv("PYRATE_ALGORITHM", "sliding-window").lower()
BUCKET_KEY = os.getenv("PYRATE_BUCKET_KEY", "pyrate-limiter-validation")
RATE = Rate(5, Duration.MINUTE)
redis = Redis.from_url(CLIENT_URL)


def build_limiter() -> Limiter:
    if ALGORITHM in {"sliding-window", "sliding-window-log"}:
        bucket = RedisBucket.init([RATE], redis, BUCKET_KEY)
    elif ALGORITHM == "token-bucket":
        store = RedisStateStore(redis, BUCKET_KEY)
        bucket = StateBucket([RATE], store=store, algorithm=TokenBucket())
    else:
        raise ValueError("PYRATE_ALGORITHM must be sliding-window or token-bucket")
    return Limiter(bucket)


limiter = build_limiter()


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    redis.close()


app = FastAPI(lifespan=lifespan)


@app.get("/health")
async def health():
    redis.ping()
    return {"status": "ok", "algorithm": ALGORITHM}


@app.get("/limited")
async def limited(request: Request):
    try:
        # Uvicorn supplies the proxy-resolved client address when proxy headers
        # are enabled, so this key can be compared with slowapi/throttled-py.
        client_key = request.client.host if request.client else "unknown"
        acquired = limiter.try_acquire(client_key, blocking=False)
        if acquired is False:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
    except Exception as exc:
        if exc.__class__.__name__ == "BucketFull":
            raise HTTPException(status_code=429, detail="Rate limit exceeded") from exc
        raise
    return {"message": "Запрос разрешён", "algorithm": ALGORITHM}
