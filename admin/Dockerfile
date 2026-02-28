FROM node:18-slim

WORKDIR /app

# Copy only admin app files (build context is repo root)
COPY admin/package.json admin/package-lock.json* ./
RUN npm install

COPY admin/ .
RUN npm run build

ENV PORT=3000
EXPOSE 3000

CMD ["npm", "start"]
