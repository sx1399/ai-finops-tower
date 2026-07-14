# ──────────────────────────────────────────────
#  AI FinOps Tower – Dashboard (Next.js)
# ──────────────────────────────────────────────

# --- Stage 1: Build ---
FROM node:22-alpine AS builder

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# The backend URL is baked in at build time via env var
ARG NEXT_PUBLIC_API_URL=http://gateway:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npm run build

# --- Stage 2: Run ---
FROM node:22-alpine AS runner

WORKDIR /app

ENV NODE_ENV=production

COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000

CMD ["node", "server.js"]
