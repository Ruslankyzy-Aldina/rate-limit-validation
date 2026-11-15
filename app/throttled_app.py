"""FastAPI experiment for throttled-py 3.5.0 with Redis-compatible stores."""

import os

from fastapi import FastAPI, Request
from throttled.asyncio.contrib.fastapi import (
    Limiter,
    RateLimitMiddleware,
    RateLimitExceededError,
    get_remote_address,
    rate_limit_exceeded_handler,
)
from throttled.asyncio.store import RedisStore
from throttled.constants import RateLimiterType


REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6381/0")
CLIENT_URL = REDIS_URL.replace("valkey://", "redis://", 1)
KEY_PREFIX = os.getenv("THROTTLED_KEY_PREFIX", "throttled-validation")


def client_key(request: Request) -> str:
    address = get_remote_address(request)
    return f"{KEY_PREFIX}:{address}"

store = RedisStore(server=CLIENT_URL)
limiter = Limiter(
    quota="5/m",
    using=RateLimiterType.TOKEN_BUCKET.value,
    store=store,
    key_func=client_key,
)

app = FastAPI()
app.add_middleware(RateLimitMiddleware)
app.add_exception_handler(RateLimitExceededError, rate_limit_exceeded_handler)


@app.get("/health")
async def health():
    await store._backend.get_client().ping()
    return {"status": "ok", "algorithm": "token-bucket"}


@app.get("/limited")
@limiter.limit()
async def limited(request: Request):
    return {"message": "Запрос разрешён", "algorithm": "token-bucket"}
