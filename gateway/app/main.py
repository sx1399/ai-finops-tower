"""
FastAPI application entry-point.

Start-up sequence:
  1. init_db()  – create tables if they don't exist
  2. Mount routers
  3. Register the proxy endpoint + API-key middleware
"""

import json
import hashlib
import httpx
import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone, timedelta

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .database import init_db, get_db, DATABASE_PATH
from .router import router as telemetry_router
from .keys_router import router as keys_router, _hash_key
from .pricing import calculate_cost
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


# ── Helper functions ────────────────────────────────────────────────────────

def is_complex_prompt(prompt_text: str) -> bool:
    keywords = ["code", "architecture", "refactor", "algorithm", "database"]
    prompt_lower = prompt_text.lower()
    return any(keyword in prompt_lower for keyword in keywords)

async def _log_telemetry(
    provider: str,
    original_model: str,
    routed_model: str,
    prompt: str,
    latency_ms: int,
    input_tokens: int,
    output_tokens: int,
    cached: bool,
    router_override: bool
):
    original_cost = calculate_cost(original_model, input_tokens, output_tokens)
    routed_cost = 0.0 if cached else calculate_cost(routed_model, input_tokens, output_tokens)
    cost_saved = original_cost - routed_cost
    
    now = datetime.now(timezone.utc).isoformat()
    
    async with aiosqlite.connect(DATABASE_PATH) as conn:
        # Save to request_logs
        await conn.execute("""
            INSERT INTO request_logs 
            (timestamp, original_model, routed_model, prompt_length, input_tokens, output_tokens, original_cost, routed_cost, cost_saved, cache_hit)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (now, original_model, routed_model, len(prompt), input_tokens, output_tokens, original_cost, routed_cost, cost_saved, 1 if cached else 0))
        
        # Save to telemetry
        await conn.execute("""
            INSERT INTO telemetry 
            (request_timestamp, provider, model, prompt, latency_ms, input_tokens, output_tokens, estimated_cost_usd, cached, cached_savings_usd, router_override)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (now, provider, routed_model, prompt, latency_ms, input_tokens, output_tokens, routed_cost, 1 if cached else 0, cost_saved, 1 if router_override else 0))
        
        await conn.commit()

# ── Proxy endpoint with API-key auth ────────────────────────────────────────

@app.post("/{provider}/v1/chat/completions")
async def chat_completions_proxy(provider: str, request: Request):
    """
    LLM proxy endpoint with cost optimization routing.
    """
    start_time = datetime.now(timezone.utc)
    
    # --- Auth ---
    async with aiosqlite.connect(DATABASE_PATH) as conn:
        conn.row_factory = aiosqlite.Row

        # Check whether any active keys exist at all
        async with conn.execute("SELECT COUNT(*) as cnt FROM api_keys WHERE is_active = 1") as cur:
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

    # --- Read Payload ---
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    original_model = payload.get("model", "unknown")
    routed_model = original_model
    messages = payload.get("messages", [])
    
    # 1. Prompt Extraction & Hashing
    prompt_text = "\n".join(msg.get("content", "") for msg in messages if isinstance(msg.get("content"), str))
    prompt_hash = hashlib.sha256(prompt_text.encode("utf-8")).hexdigest()
    
    # 2. Cache Lookup (60-minute TTL)
    async with aiosqlite.connect(DATABASE_PATH) as conn:
        conn.row_factory = aiosqlite.Row
        async with conn.execute("SELECT response_json, created_at FROM prompt_cache WHERE prompt_hash = ?", (prompt_hash,)) as cur:
            cached_row = await cur.fetchone()
            
        if cached_row:
            created_at = datetime.fromisoformat(cached_row["created_at"])
            # TTL check
            if (datetime.now(timezone.utc) - created_at) < timedelta(minutes=60):
                cached_response = json.loads(cached_row["response_json"])
                
                latency_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
                input_tokens = cached_response.get("usage", {}).get("prompt_tokens", len(prompt_text) // 4)
                output_tokens = cached_response.get("usage", {}).get("completion_tokens", 10)
                
                # Async log telemetry
                asyncio.create_task(_log_telemetry(
                    provider=provider,
                    original_model=original_model,
                    routed_model=routed_model,
                    prompt=prompt_text[:200], # only save first 200 chars to telemetry
                    latency_ms=latency_ms,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cached=True,
                    router_override=False
                ))
                return JSONResponse(content=cached_response)

    # 3. Model Down-Routing
    router_override = False
    if original_model == "gpt-4o" and len(prompt_text) < 200 and not is_complex_prompt(prompt_text):
        routed_model = "gpt-4o-mini"
        payload["model"] = routed_model
        router_override = True

    # 4. Robust Upstream Mocking & Failover
    async def mock_upstream_call(target_model: str):
        # We simulate an upstream call that randomly fails to test failover
        # In a real scenario, this would be an actual httpx call to OpenAI/etc.
        import random
        await asyncio.sleep(random.uniform(0.1, 0.5))
        if target_model == "gpt-4o" and random.random() < 0.2:
            # Simulate a 5xx error occasionally for gpt-4o
            raise httpx.HTTPStatusError("503 Service Unavailable", request=httpx.Request("POST", "url"), response=httpx.Response(503))
            
        input_toks = len(prompt_text) // 4
        output_toks = 15
        return {
            "id": f"chatcmpl-{target_model}",
            "object": "chat.completion",
            "created": int(datetime.now(timezone.utc).timestamp()),
            "model": target_model,
            "choices": [
                {
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": f"[{provider}] Proxied via AI FinOps Gateway using {target_model}",
                    },
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": input_toks, "completion_tokens": output_toks, "total_tokens": input_toks + output_toks},
        }

    try:
        response_data = await mock_upstream_call(routed_model)
    except Exception as e:
        # Failover logic
        print(f"Upstream call failed ({e}). Failing over to gpt-4o-mini...")
        routed_model = "gpt-4o-mini"
        router_override = True
        try:
            response_data = await mock_upstream_call(routed_model)
        except Exception:
            # If failover also fails, return a safe stub
            response_data = {
                "id": "chatcmpl-failover",
                "object": "chat.completion",
                "created": int(datetime.now(timezone.utc).timestamp()),
                "model": "gpt-4o-mini",
                "choices": [{"index": 0, "message": {"role": "assistant", "content": "Failover fallback response."}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": len(prompt_text) // 4, "completion_tokens": 10, "total_tokens": (len(prompt_text) // 4) + 10}
            }

    # Save to cache
    async with aiosqlite.connect(DATABASE_PATH) as conn:
        now = datetime.now(timezone.utc).isoformat()
        await conn.execute("""
            INSERT OR REPLACE INTO prompt_cache (prompt_hash, response_json, created_at)
            VALUES (?, ?, ?)
        """, (prompt_hash, json.dumps(response_data), now))
        await conn.commit()
        
    latency_ms = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
    input_tokens = response_data.get("usage", {}).get("prompt_tokens", len(prompt_text) // 4)
    output_tokens = response_data.get("usage", {}).get("completion_tokens", 10)
    
    # 5. Telemetry Analytics
    asyncio.create_task(_log_telemetry(
        provider=provider,
        original_model=original_model,
        routed_model=routed_model,
        prompt=prompt_text[:200], # store a snippet
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cached=False,
        router_override=router_override
    ))

    return JSONResponse(content=response_data)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
