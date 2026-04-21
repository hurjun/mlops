FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

# 0.0.0.0: 컨테이너 외부에서 접근 가능하도록 모든 인터페이스에서 수신
# workers 1: in-memory broadcaster는 단일 프로세스 전제 (멀티워커 시 Redis 필요)
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
