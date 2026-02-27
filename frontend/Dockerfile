FROM node:18-slim

WORKDIR /app

# Copy package.json only
COPY package.json ./

# Fresh install
RUN npm install

# Copy source code
COPY . .

# Build Next.js in standalone mode
RUN npm run build

# Standalone output goes to .next/standalone
# Copy static and public assets into standalone
RUN cp -r .next/static .next/standalone/.next/static 2>/dev/null || true
RUN cp -r public .next/standalone/public 2>/dev/null || true

WORKDIR /app/.next/standalone

# The standalone server.js respects PORT env var natively
ENV PORT=3000
EXPOSE 3000

CMD ["node", "server.js"]
