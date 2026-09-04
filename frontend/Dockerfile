# SettleSense dashboard image (dev/preview packaging for phase 1).
# Production static+nginx packaging is a later increment; this image runs
# the Vite dev server so the /health + /api proxy config applies in compose.
FROM node:20-alpine

WORKDIR /app

COPY frontend/package.json ./package.json
RUN npm install

COPY frontend ./frontend
WORKDIR /app/frontend

# Vite dev server: binds all interfaces; proxies /health and /api to the
# backend service (see vite.config.js; target overridden via env in compose).
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
