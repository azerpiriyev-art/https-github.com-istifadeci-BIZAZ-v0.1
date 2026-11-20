# Install production dependencies for the target runtime architecture.
# This stage may use QEMU on an ARM64 CI runner, but does not run next build.
FROM --platform=$TARGETPLATFORM node:24-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --omit=dev

# Compile Next.js on the native BuildKit architecture. The ARM64-emulated
# Next.js/SWC build worker can SIGILL under QEMU, so never run next build here.
FROM --platform=$BUILDPLATFORM node:24-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG NEXT_PUBLIC_API_URL=""
ENV NEXT_PUBLIC_API_URL=${NEXT_PUBLIC_API_URL}
RUN npm run build

# Runtime base and installed production dependencies match TARGETPLATFORM.
FROM --platform=$TARGETPLATFORM node:24-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

RUN addgroup -S -g 1001 nodejs \
    && adduser -S -u 1001 -G nodejs nextjs

COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

# The standalone build contains build-platform node_modules. Replace them with
# the target-platform production dependencies before switching to the app user.
RUN rm -rf ./node_modules
COPY --from=deps --chown=nextjs:nodejs /app/node_modules ./node_modules

USER nextjs
EXPOSE 3000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD node -e "fetch('http://127.0.0.1:3000/login').then(r => process.exit(r.status < 400 ? 0 : 1)).catch(() => process.exit(1))"

CMD ["node", "server.js"]
