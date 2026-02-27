# Use Node.js as the base image
FROM node:18-alpine

# Set the working directory
WORKDIR /app

# Copy package.json only (not package-lock.json — it has wrong native bindings)
COPY package.json ./

# Fresh install to get correct native bindings for Linux
RUN npm install

# Copy the rest of the frontend code
COPY . .

# Remove any macOS-specific lock files that might have been copied
RUN rm -f package-lock.json

# Build the Next.js app
RUN npm run build

# Expose the port Next.js runs on
EXPOSE 3000

# Start the application
CMD ["npm", "start"]
