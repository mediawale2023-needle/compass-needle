# Use Debian-based Node (Tailwind v3 works fine here)
FROM node:18-slim

WORKDIR /app

# Copy package.json only
COPY package.json ./

# Fresh install
RUN npm install

# Copy the rest of the frontend code
COPY . .

# Build the Next.js app
RUN npm run build

# Railway sets PORT — pass it explicitly to next start
CMD ["sh", "-c", "npx next start -H 0.0.0.0 -p ${PORT:-3000}"]
