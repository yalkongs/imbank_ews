FROM python:3.11-slim

# Node.js 설치 (프론트엔드 빌드용)
RUN apt-get update && apt-get install -y \
    nodejs npm curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Python 의존성 설치
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# 프론트엔드 의존성 설치 및 빌드
COPY frontend/package*.json ./frontend/
RUN cd frontend && npm ci --legacy-peer-deps

COPY frontend/ ./frontend/
RUN cd frontend && npm run build

# 애플리케이션 코드 복사
COPY backend/ ./backend/
COPY demo/ ./demo/
COPY ml/ ./ml/

# 시작 스크립트
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

EXPOSE 8000

CMD ["./entrypoint.sh"]
