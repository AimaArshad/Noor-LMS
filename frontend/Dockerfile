# Targets: `dev` (Vite dev server, used by docker-compose) and `prod` (static build behind nginx).
# Requires package-lock.json (created by your first `npm install`).
FROM node:20-alpine AS base
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .

FROM base AS dev
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

FROM base AS build
# Vite inlines VITE_* values at BUILD time. Pass them with
#   docker build --build-arg VITE_API_BASE_URL=... --build-arg VITE_WS_URL=...
# or let docker-compose's frontend service supply them.
ARG VITE_API_BASE_URL
ARG VITE_WS_URL
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL VITE_WS_URL=$VITE_WS_URL
RUN npm run build

FROM nginx:1.27-alpine AS prod
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
