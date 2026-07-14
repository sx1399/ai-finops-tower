import asyncio
import aiosqlite
from datetime import datetime, timedelta
import random

DATABASE_URL = "gateway.db"

async def seed():
    try:
        async with aiosqlite.connect(DATABASE_URL) as conn:
            print("Connected to SQLite!")
            
            # Create tables
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

                CREATE TABLE IF NOT EXISTS prompt_cache (
                    prompt_hash TEXT PRIMARY KEY,
                    response_json TEXT NOT NULL,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
            """)
            
            # Insert seed data if empty
            async with conn.execute("SELECT COUNT(*) FROM telemetry") as cursor:
                row = await cursor.fetchone()
                count = row[0] if row else 0

            if count == 0:
                print("Seeding data...")
                models = ["gpt-4o", "claude-3-opus", "gpt-3.5-turbo", "gemini-3.5-flash"]
                for i in range(50):
                    original = random.choice(models)
                    routed = "gemini-3.5-flash" if random.random() > 0.7 else original
                    cached = 1 if random.random() > 0.8 else 0
                    
                    cost = random.uniform(0.01, 0.5)
                    saved = cost * 0.9 if cached else (cost * 0.5 if routed != original else 0)
                    override = 1 if routed != original else 0
                    
                    await conn.execute("""
                        INSERT INTO telemetry 
                        (request_timestamp, provider, model, prompt, latency_ms, input_tokens, output_tokens, estimated_cost_usd, cached, cached_savings_usd, router_override)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, 
                    (
                        (datetime.now() - timedelta(minutes=i*15, days=random.randint(0, 5))).isoformat(), 
                        "openai", 
                        routed, 
                        "test prompt", 
                        random.randint(150, 1500), 
                        random.randint(50, 500), 
                        random.randint(50, 500), 
                        cost, 
                        cached, 
                        saved, 
                        override
                    ))
                
                await conn.commit()
                print("Seeding complete.")
            else:
                print(f"Table already has {count} rows.")
                
    except Exception as e:
        print("Error connecting to database:", e)

if __name__ == "__main__":
    asyncio.run(seed())
