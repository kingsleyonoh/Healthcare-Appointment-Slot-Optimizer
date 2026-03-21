# --- Stage 1: Builder ---
# BOOTSTRAP NOTE: Replace base image and build commands for your stack.
# Examples:
#   Go:     golang:1.23-alpine → go build -o /app ./cmd/...
#   Node:   node:22-alpine → npm ci && npm run build
#   Python: python:3.12-slim → pip install -r requirements.txt

FROM node:22-alpine AS builder

WORKDIR /app

# Copy dependency files first (cache layer)
COPY package*.json ./
RUN npm ci --only=production

# Copy source
COPY . .

# Build (remove if not needed, e.g. plain Node server)
RUN npm run build

# --- Stage 2: Production ---
FROM node:22-alpine AS production

# Security: non-root user
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

WORKDIR /app

# Copy only what's needed from builder
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/dist ./dist
COPY --from=builder /app/package.json ./

# Switch to non-root
USER appuser

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget --no-verbose --tries=1 --spider http://localhost:3000/health || exit 1

EXPOSE 3000

CMD ["node", "dist/index.js"]
