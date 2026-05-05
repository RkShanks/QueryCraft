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

# SPA fallback + API proxy to backend
RUN echo 'server { \
  listen 80; \
  root /usr/share/nginx/html; \
  location /api/v1/ { \
    proxy_pass http://backend:8000/api/v1/; \
    proxy_http_version 1.1; \
    proxy_set_header Host $host; \
    proxy_set_header X-Real-IP $remote_addr; \
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for; \
    proxy_set_header X-Forwarded-Proto $scheme; \
  } \
  location / { \
    try_files $uri $uri/ /index.html; \
  } \
}' > /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
