# ── Stage 1: Build ────────────────────────────────────────────────────────────
# Build context is the SmartClinic project root (same pattern as all services).
FROM node:20-alpine AS build

WORKDIR /app

# Install dependencies first — layer-cached unless package files change.
COPY frontend/package.json ./
RUN npm install --legacy-peer-deps

# Copy Angular source and produce a production build.
COPY frontend/ .
RUN npm run build:prod

# ── Stage 2: Serve ─────────────────────────────────────────────────────────────
FROM nginx:1.27-alpine AS serve

# Angular 17+ outputs browser assets to dist/<project>/browser/
COPY --from=build /app/dist/smartclinic-spa/browser /usr/share/nginx/html

# SPA routing: try_files $uri /index.html so Angular router handles deep-links
COPY ops/nginx/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

HEALTHCHECK --interval=10s --timeout=5s --retries=3 \
  CMD wget -qO- http://localhost/ || exit 1
