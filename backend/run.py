"""
백엔드 서버 실행 스크립트
"""
import uvicorn
import sys
import os
import subprocess


def kill_existing_process(port: int):
    """기존 포트 점유 프로세스 종료"""
    try:
        result = subprocess.run(
            f"lsof -ti:{port}",
            shell=True,
            capture_output=True,
            text=True
        )
        pids = result.stdout.strip()
        if pids:
            subprocess.run(f"kill -9 {pids}", shell=True)
            print(f"포트 {port} 기존 프로세스 종료됨 (PID: {pids})")
    except Exception as e:
        print(f"포트 정리 중 오류: {e}")


# 프로젝트 루트를 Python 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8000

    # 기존 프로세스 정리
    kill_existing_process(port)

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        log_level="info"
    )
