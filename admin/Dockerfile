FROM node:18-slim

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .

# NEXT_PUBLIC_* vars must be set at BUILD TIME for Next.js to bake them in.
# Vercel/CI must set this at build time; fallback keeps local builds usable.
ARG NEXT_PUBLIC_API_URL=http://localhost:8000
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL

RUN npm run build

ENV PORT=3000
EXPOSE 3000

CMD ["npm", "start"]
