FROM node:24-alpine AS build
WORKDIR /web
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund
COPY . .
# the browser calls the API directly: its address is baked into the client bundle at build time
ARG NEXT_PUBLIC_REGEN_API=http://127.0.0.1:8787
ENV NEXT_PUBLIC_REGEN_API=$NEXT_PUBLIC_REGEN_API
RUN npm run build

FROM node:24-alpine
WORKDIR /web
ENV NODE_ENV=production HOSTNAME=0.0.0.0 PORT=3000
COPY --from=build /web/.next/standalone ./
COPY --from=build /web/.next/static ./.next/static
USER node
CMD ["node", "server.js"]
