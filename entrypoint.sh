#!/bin/bash
set -e

# 검증용 DB가 없으면 생성 (최초 실행 또는 볼륨 미연결 시)
if [ ! -f "/app/demo/demo.db" ]; then
    echo "=== 검증용 DB 생성 중... (약 60초 소요) ==="
    python3 /app/demo/generate_dataset.py
    echo "=== DB 생성 완료 ==="
fi

# PORT 환경변수 (Railway가 자동 주입, 기본값 8000)
PORT=${PORT:-8000}

echo "=== EWS 서버 시작 (포트 $PORT) ==="
exec uvicorn backend.app.main:app --host 0.0.0.0 --port "$PORT"
