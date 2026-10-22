FROM node:24-alpine AS build

WORKDIR /workspace/apps/web

COPY apps/web/.npmrc ./.npmrc
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci
COPY apps/web/index.html apps/web/tsconfig.json apps/web/vite.config.ts ./
COPY apps/web/src ./src
RUN npm run build

FROM nginx:1.28-alpine
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /workspace/apps/web/dist /usr/share/nginx/html
