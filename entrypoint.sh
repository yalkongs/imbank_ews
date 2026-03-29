#!/bin/bash
set -e

# 검증용 DB가 없으면 백그라운드에서 생성 (서버는 즉시 시작)
if [ ! -f "/app/demo/demo.db" ]; then
    echo "=== 검증용 DB 백그라운드 생성 시작 (약 60~120초 소요) ==="
    python3 /app/demo/generate_dataset.py &
    echo "=== DB 준비 전까지 API는 503 반환됩니다 ==="
fi

# PORT 환경변수 (Railway가 자동 주입, 기본값 8000)
PORT=${PORT:-8000}

echo "=== EWS 서버 시작 (포트 $PORT) ==="
exec uvicorn backend.app.main:app --host 0.0.0.0 --port "$PORT"
