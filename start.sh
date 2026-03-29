#!/bin/bash
PROJECT_ROOT="$(cd "$(dirname "$0")" && pwd)"

echo "======================================"
echo "  iM뱅크 EWS 데모 시스템 시작"
echo "======================================"

# Backend
cd "$PROJECT_ROOT/backend"
python run.py &
BACKEND_PID=$!
echo "백엔드 시작 (PID: $BACKEND_PID, 포트 8000)"
sleep 2

# Frontend
cd "$PROJECT_ROOT/frontend"
npm run dev &
FRONTEND_PID=$!
echo "프론트엔드 시작 (PID: $FRONTEND_PID, 포트 3000)"
sleep 3

echo ""
echo "접속 URL:"
echo "  - EWS 시스템: http://localhost:3000"
echo "  - API 문서:   http://localhost:8000/docs"
echo ""
echo "종료: Ctrl+C"

wait
