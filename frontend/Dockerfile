FROM node:22-slim AS builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm install --ignore-scripts
COPY . .
RUN npx nuxt prepare && npm run build

FROM node:22-slim AS runtime
WORKDIR /app
COPY --from=builder /app/.output .output
EXPOSE 3000
CMD ["node", ".output/server/index.mjs"]
