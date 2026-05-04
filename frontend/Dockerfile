# Multi-stage build for QueryCraft Frontend
# Stage 1: Build
FROM node:20-alpine AS builder

WORKDIR /build
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

# Stage 2: Serve with nginx
FROM nginx:alpine AS runtime

# Copy build output
COPY --from=builder /build/dist /usr/share/nginx/html

# SPA fallback
RUN echo 'server { \
  listen 80; \
  root /usr/share/nginx/html; \
  location / { \
    try_files $uri $uri/ /index.html; \
  } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
