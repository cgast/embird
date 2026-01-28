# Multi-stage build for Vue frontend

# Stage 1: Development
FROM node:20-alpine AS development

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy source code
COPY . .

# Expose Vite dev server port
EXPOSE 5173

# Start development server
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# Stage 2: Build
FROM node:20-alpine AS build

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install dependencies
RUN npm ci

# Copy source code
COPY . .

# Build the application
RUN npm run build

# Stage 3: Production with nginx
FROM nginx:alpine AS production

# Copy nginx config template
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Copy built files from build stage
COPY --from=build /app/dist /usr/share/nginx/html

# Set default environment variables
ENV API_BACKEND_URL=http://webapp:8000
ENV API_BACKEND_HOST=webapp

# Expose port 80
EXPOSE 80

# Start nginx (nginx will automatically process templates in /etc/nginx/templates/)
CMD ["nginx", "-g", "daemon off;"]
