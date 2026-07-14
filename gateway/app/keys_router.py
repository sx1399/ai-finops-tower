"""
API Key management endpoints.

POST   /api/keys          – generate a new key
GET    /api/keys          – list all keys (name, prefix, created_at, last_used_at, is_active)
DELETE /api/keys/{id}     – revoke (soft-delete) a key
"""
import secrets
import hashlib
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
import aiosqlite

from .database import get_db

router = APIRouter(prefix="/api/keys", tags=["api-keys"])


class CreateKeyRequest(BaseModel):
    name: str


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


@router.post("", status_code=201)
async def create_key(body: CreateKeyRequest, conn: aiosqlite.Connection = Depends(get_db)):
    """Generate a new API key. The raw key is only returned once – store it safely!"""
    raw_key = "gw-" + secrets.token_urlsafe(32)
    key_hash = _hash_key(raw_key)
    prefix = raw_key[:10]  # e.g. "gw-abc123"
    now = datetime.now(timezone.utc).isoformat()

    await conn.execute(
        "INSERT INTO api_keys (name, key_hash, key_prefix, created_at) VALUES (?, ?, ?, ?)",
        (body.name, key_hash, prefix, now),
    )
    await conn.commit()

    return {
        "key": raw_key,   # shown ONCE
        "prefix": prefix,
        "name": body.name,
        "created_at": now,
    }


@router.get("")
async def list_keys(conn: aiosqlite.Connection = Depends(get_db)):
    """List all API keys (never exposes the raw key)."""
    async with conn.execute(
        "SELECT id, name, key_prefix, created_at, last_used_at, is_active FROM api_keys ORDER BY created_at DESC"
    ) as cur:
        rows = await cur.fetchall()

    return [
        {
            "id": row["id"],
            "name": row["name"],
            "prefix": row["key_prefix"],
            "created_at": row["created_at"],
            "last_used_at": row["last_used_at"],
            "is_active": bool(row["is_active"]),
        }
        for row in rows
    ]


@router.delete("/{key_id}", status_code=200)
async def revoke_key(key_id: int, conn: aiosqlite.Connection = Depends(get_db)):
    """Revoke (soft-delete) an API key by ID."""
    async with conn.execute("SELECT id FROM api_keys WHERE id = ?", (key_id,)) as cur:
        row = await cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Key not found")

    await conn.execute("UPDATE api_keys SET is_active = 0 WHERE id = ?", (key_id,))
    await conn.commit()
    return {"message": "Key revoked successfully"}
