# Use Debian-based Node (NOT Alpine — Tailwind v4 needs glibc)
FROM node:18-slim

WORKDIR /app

# Copy package.json only
COPY package.json ./

# Clean install for correct Linux native bindings
RUN npm install --no-optional && npm install @tailwindcss/oxide

# Copy the rest of the frontend code
COPY . .

# Build the Next.js app
RUN npm run build

# Start the application
CMD ["npm", "start"]
