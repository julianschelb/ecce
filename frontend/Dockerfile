# ECCE frontend: static build served by nginx, proxying /api to the backend.
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginx:1.27-alpine AS runtime
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf.template /etc/nginx/templates/default.conf.template
# nginx's entrypoint renders the template with these variables
ENV PORT=80 BACKEND_URL=http://backend:8000
EXPOSE 80
