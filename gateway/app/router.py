import os
import json
import hashlib
import sqlite3
import logging
from datetime import datetime
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
import httpx
from .keys_router import _hash_key

# Set up logging so you can see the router work in your terminal
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("gateway-router")

router = APIRouter()

# 1. PRICING RULES (Cost per 1,000,000 tokens in USD)
MODEL_PRICING = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "gemini-1.5-flash": {"input": 0.075, "output": 0.30},
    "deepseek-v4-flash": {"input": 0.14, "output": 0.28},
}

# SQLite database location used by the gateway and the chart endpoint
DB_PATH = os.getenv("DATABASE_PATH", "gateway.db")


def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    ensure_cache_schema(conn)
    return conn

def canonicalize_payload(payload) -> str:
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

# Helper to hash prompt strings for the caching layer
def hash_prompt(prompt) -> str:
    if isinstance(prompt, str):
        normalized = prompt.replace("\r\n", "\n").strip()
    else:
        normalized = canonicalize_payload(prompt)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def ensure_cache_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS prompt_cache (
            prompt_hash TEXT PRIMARY KEY,
            response_json TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()

    try:
        conn.execute("SELECT prompt_hash, response_json FROM prompt_cache LIMIT 1")
    except sqlite3.OperationalError:
        logger.warning("Recreating prompt_cache table with the expected schema.")
        conn.execute("DROP TABLE IF EXISTS prompt_cache")
        conn.execute(
            """
            CREATE TABLE prompt_cache (
                prompt_hash TEXT PRIMARY KEY,
                response_json TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()

# Rough fallback token estimator (1 token ≈ 4 characters)
def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)

# Cost calculation formula
def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = MODEL_PRICING.get(model, MODEL_PRICING["gpt-4o-mini"])
    input_cost = (input_tokens / 1_000_000) * pricing["input"]
    output_cost = (output_tokens / 1_000_000) * pricing["output"]
    return input_cost + output_cost

MOCK_CHOICES = [
    {
        "index": 0,
        "message": {
            "role": "assistant",
            "content": "This is a mock fallback response from the gateway because the upstream provider is unavailable.",
        },
        "finish_reason": "stop",
    }
]


def build_mock_response(model: str, user_prompt: str) -> dict:
    prompt_tokens = estimate_tokens(user_prompt)
    completion_tokens = 12
    return {
        "id": "chatcmpl-mock-fallback",
        "object": "chat.completion",
        "created": int(datetime.utcnow().timestamp()),
        "model": model,
        "choices": MOCK_CHOICES,
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


def get_hourly_chart_data() -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT
                strftime('%Y-%m-%d %H:00:00', timestamp) AS hour_bucket,
                ROUND(COALESCE(SUM(original_cost), 0.0), 2) AS spend,
                SUM(CASE WHEN cache_hit = 1 THEN 1 ELSE 0 END) AS saved
            FROM request_logs
            GROUP BY strftime('%Y-%m-%d %H:00:00', timestamp)
            ORDER BY hour_bucket
            """
        ).fetchall()
    finally:
        conn.close()

    return [
        {
            "date": row["hour_bucket"],
            "spend": float(row["spend"] or 0.0),
            "saved": int(row["saved"] or 0),
        }
        for row in rows
    ]


@router.post("/mock/completions")
async def mock_completions(request: Request):
    body = await request.json()
    return JSONResponse({
        "id": "chatcmpl-mock",
        "object": "chat.completion",
        "created": int(datetime.utcnow().timestamp()),
        "model": body.get("model", "unknown-mock-model"),
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": "This is a successful mock upstream response.",
                },
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": 10,
            "completion_tokens": 10,
            "total_tokens": 20,
        },
    })

@router.get("/api/chart-data")
async def chart_data():
    return JSONResponse(content=get_hourly_chart_data())

@router.get("/api/metrics")
async def get_metrics():
    conn = get_db_connection()
    try:
        row = conn.execute(
            """
            SELECT SUM(spend) as total_spend, SUM(saved) as total_saved
            FROM (
                SELECT original_cost as spend, cost_saved as saved FROM request_logs
                UNION ALL
                SELECT estimated_cost_usd as spend, cached_savings_usd as saved FROM telemetry
            )
            """
        ).fetchone()
        
        total_spend = float(row["total_spend"] if row else 0.0)
        total_saved = float(row["total_saved"] if row else 0.0)
        active_reductions = 0.0
        
        if (total_spend) > 0:
            active_reductions = (total_saved / total_spend) * 100
            
        return JSONResponse(content={
            "total_spend": total_spend,
            "total_saved": total_saved,
            "active_reductions_percent": active_reductions
        })
    finally:
        conn.close()

@router.get("/api/queries")
async def get_queries():
    conn = get_db_connection()
    try:
        rows = conn.execute(
            """
            SELECT 
                id,
                timestamp,
                original_model,
                routed_model,
                cache_hit
            FROM request_logs
            ORDER BY timestamp DESC
            LIMIT 50
            """
        ).fetchall()
        
        return JSONResponse(content=[
            {
                "id": row["id"],
                "timestamp": row["timestamp"],
                "original_model": row["original_model"],
                "routed_model": row["routed_model"],
                "cached": bool(row["cache_hit"]),
                "latency": 0 # Mock latency since not stored in request_logs
            }
            for row in rows
        ])
    finally:
        conn.close()


@router.post("/openai/v1/chat/completions")
async def chat_completions(request: Request):
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    auth_header = request.headers.get("Authorization", "")
    api_key = auth_header.removeprefix("Bearer ").strip() if auth_header.startswith("Bearer ") else ""
    api_key_hash = _hash_key(api_key) if api_key else ""

    conn = get_db_connection()

    try:
        if api_key_hash:
            today = datetime.utcnow().date().isoformat()
            budget_row = conn.execute(
                "SELECT COALESCE(SUM(original_cost), 0.0) AS total_cost FROM request_logs WHERE timestamp >= ? AND api_key_hash = ?",
                (f"{today}T00:00:00", api_key_hash),
            ).fetchone()
            total_cost = float(budget_row["total_cost"] if budget_row else 0.0)
            if total_cost > 5.0:
                conn.close()
                raise HTTPException(status_code=429, detail="Daily budget limit reached for this API key.")
    except HTTPException:
        raise
    except Exception as e:
        logger.warning(f"Budget check failed: {e}")

    requested_model = body.get("model", "gpt-4o")
    messages = body.get("messages", [])

    # Extract the actual text prompts
    user_prompt = " ".join([m.get("content", "") for m in messages if m.get("role") == "user"])

    if requested_model == "gpt-4o" and len(user_prompt.strip()) < 20:
        body["model"] = "gpt-4o-mini"
        requested_model = body["model"]
        logger.info("📉 Downgraded model to gpt-4o-mini to save costs.")
    prompt_len = len(user_prompt)

    # ---- 1. LOCAL CACHING LAYER ----
    prompt_hash = hash_prompt({"model": requested_model, "messages": messages})
    
    # Check if we already answered this exact question
    cached_record = None
    try:
        cached_record = conn.execute(
            "SELECT response_json FROM prompt_cache WHERE prompt_hash = ? LIMIT 1", 
            (prompt_hash,)
        ).fetchone()
    except Exception as e:
        logger.warning(f"Cache table check failed (it might not be initialized yet): {e}")

    if cached_record:
        logger.info("🎯 Cache HIT! Returning local answer for $0.00.")
        cached_response = json.loads(cached_record["response_json"])
        
        # Calculate what they *would* have paid vs the actual $0.00 cost
        input_tokens = estimate_tokens(user_prompt)
        output_tokens = estimate_tokens(cached_response["choices"][0]["message"]["content"])
        original_cost = calculate_cost(requested_model, input_tokens, output_tokens)
        
        try:
            conn.execute(
                """INSERT INTO request_logs 
                   (timestamp, original_model, routed_model, prompt_length, input_tokens, output_tokens, original_cost, routed_cost, cost_saved, cache_hit, api_key_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (datetime.utcnow().isoformat(), requested_model, "LOCAL_CACHE", prompt_len, input_tokens, output_tokens, original_cost, 0.0, original_cost, 1, api_key_hash)
            )
            conn.commit()
        except Exception as e:
            logger.error(f"Failed to log cache hit to DB: {e}")
            
        conn.close()
        return JSONResponse(content=cached_response)

    # ---- 2. INTELLIGENT MODEL ROUTING ----
    target_model = requested_model
    
    # Complexity Filter: Short prompts under 200 characters without complex keywords get downgraded
    complex_keywords = ["code", "architecture", "refactor", "algorithm", "database", "write a class"]
    is_complex = any(kw in user_prompt.lower() for kw in complex_keywords)

    if requested_model == "gpt-4o" and prompt_len < 200 and not is_complex:
        # Swap the expensive gpt-4o request with our cheap DeepSeek model
        target_model = "deepseek-v4-flash"
        logger.info(f"⚡ Routed short request from '{requested_model}' to '{target_model}'")

    outbound_body = body.copy()
    outbound_body["model"] = target_model

    # ---- 3. SECURE FAILOVER ROUTER ----
    response_data = None
    headers = {"Authorization": f"Bearer {os.getenv('OPENAI_API_KEY', 'mock-key')}"}
    
    async with httpx.AsyncClient() as client:
        try:
            # Check if running in mock mode or live mode
            target_url = "http://localhost:8000/mock/completions" if os.getenv("MOCK_UPSTREAM", "true") == "true" else "https://api.openai.com/v1/chat/completions"
            
            response = await client.post(target_url, json=outbound_body, headers=headers, timeout=10.0)
            response.raise_for_status()
            response_data = response.json()
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            logger.warning(f"🚨 Model '{target_model}' failed! Attempting failover to gpt-4o-mini...")
            
            # If our target failed, seamlessly route to the fallback model
            fallback_model = "gpt-4o-mini"
            outbound_body["model"] = fallback_model
            
            try:
                response = await client.post(target_url, json=outbound_body, headers=headers, timeout=10.0)
                response.raise_for_status()
                response_data = response.json()
                target_model = f"FAILOVER -> {fallback_model}"
                logger.info(f"🛡️ Failover successful! Resolved using '{fallback_model}'.")
            except Exception as final_err:
                logger.warning("❌ Both primary and fallback routes failed. Returning a built-in mock response.")
                response_data = build_mock_response(requested_model, user_prompt)
                target_model = "MOCK_FALLBACK"

    # ---- 4. TELEMETRY LOGGING ----
    usage = response_data.get("usage", {})
    input_tokens = usage.get("prompt_tokens", estimate_tokens(user_prompt))
    output_tokens = usage.get("completion_tokens", 20)
    
    # Pricing Delta calculations
    original_cost = calculate_cost(requested_model, input_tokens, output_tokens)
    actual_cost = calculate_cost(target_model.replace("FAILOVER -> ", ""), input_tokens, output_tokens)
    cost_saved = max(0.0, original_cost - actual_cost)

    # Save details to DB
    try:
        conn.execute(
            """INSERT INTO request_logs 
               (timestamp, original_model, routed_model, prompt_length, input_tokens, output_tokens, original_cost, routed_cost, cost_saved, cache_hit, api_key_hash)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (datetime.utcnow().isoformat(), requested_model, target_model, prompt_len, input_tokens, output_tokens, original_cost, actual_cost, cost_saved, 0, api_key_hash)
        )
        
        # Save to local Cache database
        conn.execute(
            "INSERT OR REPLACE INTO prompt_cache (prompt_hash, response_json) VALUES (?, ?)",
            (prompt_hash, json.dumps(response_data, ensure_ascii=False, sort_keys=True))
        )
        conn.commit()
    except Exception as db_err:
        logger.error(f"Database logging error: {db_err}")

    conn.close()
    return JSONResponse(content=response_data)