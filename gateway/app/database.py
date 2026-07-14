"""
Shared database helpers.
Reads DATABASE_PATH from the environment (default: gateway.db in cwd).
"""
import os
import aiosqlite

DATABASE_PATH = os.getenv("DATABASE_PATH", "gateway.db")


async def get_db():
    """FastAPI dependency — yields an open aiosqlite connection."""
    conn = await aiosqlite.connect(DATABASE_PATH)
    conn.row_factory = aiosqlite.Row
    try:
        yield conn
    finally:
        await conn.close()


async def init_db():
    """Create all tables if they don't already exist."""
    async with aiosqlite.connect(DATABASE_PATH) as conn:
        await conn.executescript("""
            CREATE TABLE IF NOT EXISTS telemetry (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_timestamp TEXT NOT NULL,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                prompt TEXT NOT NULL,
                latency_ms INTEGER NOT NULL,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                estimated_cost_usd REAL NOT NULL,
                cached BOOLEAN NOT NULL DEFAULT 0,
                cached_savings_usd REAL DEFAULT 0,
                router_override BOOLEAN NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS request_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                original_model TEXT NOT NULL,
                routed_model TEXT NOT NULL,
                prompt_length INTEGER NOT NULL,
                input_tokens INTEGER NOT NULL,
                output_tokens INTEGER NOT NULL,
                original_cost REAL NOT NULL,
                routed_cost REAL NOT NULL,
                cost_saved REAL NOT NULL,
                cache_hit INTEGER NOT NULL DEFAULT 0,
                api_key_hash TEXT
            );

            CREATE TABLE IF NOT EXISTS prompt_cache (
                prompt_hash TEXT PRIMARY KEY,
                response_json TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                key_hash TEXT NOT NULL UNIQUE,
                key_prefix TEXT NOT NULL,
                created_at TEXT NOT NULL,
                last_used_at TEXT,
                is_active BOOLEAN NOT NULL DEFAULT 1
            );
        """)
        await conn.commit()
