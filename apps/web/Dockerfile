# Spotify Insights web app
FROM node:22-alpine

WORKDIR /app

# Install dependencies first so source edits do not invalidate this layer.
COPY package.json package-lock.json* ./
RUN npm ci

COPY . .

EXPOSE 3010

# Vite dev server: the proxy forwards /api and /health to the API container,
# so the browser needs no cross-origin configuration. --host binds 0.0.0.0 so
# the port is reachable from outside the container.
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "3010"]
