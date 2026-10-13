FROM node:24-alpine AS build
WORKDIR /web
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund
COPY . .
# rewrites() is evaluated at build time: the private API address is baked into the standalone server
ARG REGEN_API_URL=http://api:8787
ENV REGEN_API_URL=$REGEN_API_URL
RUN npm run build

FROM node:24-alpine
WORKDIR /web
ENV NODE_ENV=production HOSTNAME=0.0.0.0 PORT=3000
COPY --from=build /web/.next/standalone ./
COPY --from=build /web/.next/static ./.next/static
USER node
CMD ["node", "server.js"]
