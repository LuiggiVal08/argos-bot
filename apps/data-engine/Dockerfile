FROM node:20-alpine AS builder
WORKDIR /app
COPY package*.json ./
RUN npm ci --ignore-scripts
COPY tsconfig.json nest-cli.json ./
COPY src/ src/
RUN npm run build

FROM node:20-alpine AS runner
WORKDIR /app
RUN addgroup --system argos && adduser --system --ingroup argos argos && \
    mkdir -p /app/data && chown argos:argos /app/data
COPY package*.json ./
RUN npm ci --omit=dev --ignore-scripts && npm cache clean --force
COPY --from=builder /app/dist dist/
USER argos
EXPOSE 3000
ENV NODE_ENV=production
CMD ["node", "dist/main.js"]
