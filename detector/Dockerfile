# 실제 엣지 배포 타겟:
#   Jetson → nvcr.io/nvidia/l4t-pytorch:r35.2.1-pth2.0-py3
#   x86 GPU → nvidia/cuda:12.3.2-runtime-ubuntu22.04
# 여기서는 포터블하게 python:3.11-slim 사용.
FROM python:3.11-slim

# OpenCV 헤드리스 빌드가 필요로 하는 시스템 라이브러리
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ ./src/

CMD ["python", "-m", "src.main"]
