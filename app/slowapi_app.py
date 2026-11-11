import os

from fastapi import FastAPI, Request
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address


redis_url = os.getenv("REDIS_URL", "redis://localhost:6381/0")

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=redis_url,
    strategy="moving-window",
    swallow_errors=False,
    in_memory_fallback_enabled=False,
)

app = FastAPI()
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/limited")
@limiter.limit("5/minute")
async def limited(request: Request):
    return {"message": "Запрос разрешён"}