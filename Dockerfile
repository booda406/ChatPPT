FROM python:3.11-slim

WORKDIR /app

# 安裝系統依賴
RUN apt-get update && apt-get install -y \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# 複製專案文件
COPY . .

# 安裝 Python 依賴
RUN pip install --no-cache-dir -r requirements.txt

# 設置環境變數
ENV PYTHONPATH=/app
ENV GRADIO_SERVER_NAME=0.0.0.0
ENV GRADIO_SERVER_PORT=7860

# 執行應用
CMD ["python", "src/gradio_server.py"]
