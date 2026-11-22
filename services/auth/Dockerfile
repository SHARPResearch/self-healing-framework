# SHARP web: the dashboard (built with accounts on) and the auth service in one image, on one
# origin (services/auth/src/server.js). Built from the repository root:
#   docker build -f services/auth/Dockerfile -t sharp/web .

# -- the dashboard --------------------------------------------------------------------------------
FROM node:22.21.1-alpine AS dashboard
RUN corepack enable && corepack prepare pnpm@10.13.1 --activate
WORKDIR /src/frontend
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
# explicit copies: never the host's node_modules (built for another OS)
COPY frontend/index.html frontend/vite.config.ts frontend/tsconfig*.json frontend/components.json ./
COPY frontend/public ./public
COPY frontend/src ./src
ENV VITE_AUTH=on
RUN pnpm build

# -- the server -----------------------------------------------------------------------------------
FROM node:22.21.1-alpine
ENV NODE_ENV=production
WORKDIR /app
COPY services/auth/package.json services/auth/package-lock.json ./
RUN npm ci --omit=dev && npm cache clean --force
COPY services/auth/src ./src
COPY --from=dashboard /src/frontend/dist ./public
ENV STATIC_DIR=public
USER node
EXPOSE 10000
CMD ["node", "src/server.js"]
