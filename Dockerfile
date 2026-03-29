FROM python:3.11-slim

WORKDIR /app

# Python 의존성 설치
COPY backend/requirements.txt ./backend/
RUN pip install --no-cache-dir -r backend/requirements.txt

# 애플리케이션 코드 복사
COPY backend/ ./backend/
COPY demo/ ./demo/
COPY ml/ ./ml/

# 시작 스크립트
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

EXPOSE 8000

CMD ["./entrypoint.sh"]
