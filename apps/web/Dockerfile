FROM node:22-alpine AS build
WORKDIR /workspace
COPY package.json package-lock.json* ./
COPY apps/web/package.json ./apps/web/package.json
COPY packages/shared/package.json ./packages/shared/package.json
RUN npm install
COPY apps/web ./apps/web
COPY packages/shared ./packages/shared
ARG VITE_API_BASE_URL
ARG VITE_OIDC_AUTHORIZATION_URL
ARG VITE_OIDC_TOKEN_URL
ARG VITE_OIDC_CLIENT_ID
ARG VITE_OIDC_REDIRECT_URI
ARG VITE_OIDC_SCOPES
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL \
    VITE_OIDC_AUTHORIZATION_URL=$VITE_OIDC_AUTHORIZATION_URL \
    VITE_OIDC_TOKEN_URL=$VITE_OIDC_TOKEN_URL \
    VITE_OIDC_CLIENT_ID=$VITE_OIDC_CLIENT_ID \
    VITE_OIDC_REDIRECT_URI=$VITE_OIDC_REDIRECT_URI \
    VITE_OIDC_SCOPES=$VITE_OIDC_SCOPES
RUN npm run build

FROM nginx:1.27-alpine
COPY --from=build /workspace/apps/web/dist /usr/share/nginx/html
COPY apps/web/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
