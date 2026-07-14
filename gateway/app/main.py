"""
FastAPI application entry-point.

Start-up sequence:
  1. init_db()  – create tables if they don't exist
  2. Mount routers
  3. Register the proxy endpoint + API-key middleware

Middleware auth flow (proxy routes only):
  - Read the Authorization: Bearer <key> header.
  - Hash the raw key and look it up in api_keys.
  - If no keys exist yet, allow the request (bootstrapping mode).
  - Otherwise reject with 401 if the key is missing / invalid / revoked.
"""

from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .database import init_db, get_db, DATABASE_PATH
from .router import router as telemetry_router
from .keys_router import router as keys_router, _hash_key
import aiosqlite


# ── Lifespan ────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


# ── App ─────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="AI FinOps Gateway",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(telemetry_router)
app.include_router(keys_router)


# ── Proxy endpoint with API-key auth ────────────────────────────────────────

@app.post("/{provider}/v1/chat/completions")
async def chat_completions_proxy(provider: str, request: Request):
    """
    LLM proxy endpoint.

    Validates the caller's Gateway API key before forwarding the request.
    If no keys have been created yet the request is allowed through so a
    fresh install can still be bootstrapped from the dashboard.
    """
    # --- Auth ---
    async with aiosqlite.connect(DATABASE_PATH) as conn:
        conn.row_factory = aiosqlite.Row

        # Check whether any active keys exist at all
        async with conn.execute(
            "SELECT COUNT(*) as cnt FROM api_keys WHERE is_active = 1"
        ) as cur:
            row = await cur.fetchone()
        total_active = row["cnt"] if row else 0

        if total_active > 0:
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                raise HTTPException(status_code=401, detail="Missing API key")

            raw_key = auth_header.removeprefix("Bearer ").strip()
            key_hash = _hash_key(raw_key)

            async with conn.execute(
                "SELECT id FROM api_keys WHERE key_hash = ? AND is_active = 1",
                (key_hash,),
            ) as cur:
                key_row = await cur.fetchone()

            if not key_row:
                raise HTTPException(status_code=401, detail="Invalid or revoked API key")

            # Update last_used_at
            await conn.execute(
                "UPDATE api_keys SET last_used_at = ? WHERE id = ?",
                (datetime.now(timezone.utc).isoformat(), key_row["id"]),
            )
            await conn.commit()

    # --- Proxy (stub – replace with real httpx forwarding) ---
    payload = await request.json()
    model = payload.get("model", "unknown")

    return {
        "id": "chatcmpl-stub",
        "object": "chat.completion",
        "created": int(datetime.now(timezone.utc).timestamp()),
        "model": model,
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": f"[{provider}] Proxied via AI FinOps Gateway",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30},
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
