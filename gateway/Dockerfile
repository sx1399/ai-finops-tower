# ──────────────────────────────────────────────
#  AI FinOps Tower – Gateway (FastAPI + SQLite)
# ──────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Run DB migrations + seed on startup, then launch uvicorn
CMD ["sh", "-c", "python seed.py && python -m uvicorn app.main:app --host 0.0.0.0 --port 8000"]
