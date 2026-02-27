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

# Use port 3000 (standard Next.js port)
EXPOSE 3000
ENV PORT=3000

# Start Next.js on 0.0.0.0:3000
CMD ["npx", "next", "start", "-H", "0.0.0.0", "-p", "3000"]
