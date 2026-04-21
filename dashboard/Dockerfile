# ── 멀티 스테이지 빌드 ────────────────────────────────────────────────────────
# 스테이지를 나누는 이유:
#   빌드 도구(node_modules, 컴파일러 등)는 실행에 불필요하다.
#   최종 이미지에는 실행에 필요한 파일만 담아 이미지 크기를 줄인다.
#   (안 나누면 수백 MB, 나누면 수십 MB)

# ── 1단계: 의존성 설치 ─────────────────────────────────────────────────────────
FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci  # npm install 보다 빠르고 lock 파일 기준으로 정확히 설치

# ── 2단계: 빌드 ───────────────────────────────────────────────────────────────
FROM node:20-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules  # 1단계에서 설치한 모듈 복사
COPY . .
RUN npm run build  # Next.js 빌드 → .next/standalone 생성

# ── 3단계: 실행 이미지 (최소 크기) ────────────────────────────────────────────
FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production

# 빌드 결과물만 복사 (소스코드, node_modules 제외)
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static

EXPOSE 3000
CMD ["node", "server.js"]  # standalone 빌드의 실행 진입점
