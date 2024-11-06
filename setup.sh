#!/bin/bash

# 顏色設定
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 檢查函數
check_command() {
    if ! command -v $1 &> /dev/null; then
        echo -e "${RED}錯誤: $1 未安裝${NC}"
        echo "請安裝 $1 後再繼續"
        exit 1
    fi
}

# 檢查必要的命令
echo -e "${YELLOW}檢查必要的依賴...${NC}"
check_command docker
check_command docker-compose

# 提示使用者輸入必要的金鑰
echo -e "${YELLOW}請輸入必要的設定資訊：${NC}"
read -p "請輸入你的 Ngrok Authtoken: " ngrok_token
read -p "請輸入你的 OpenAI API Key: " openai_key

# 創建 .env.docker 檔案
echo -e "${YELLOW}創建 .env.docker 檔案...${NC}"
cat << EOT > .env.docker
NGROK_AUTH=${ngrok_token}
OPENAI_API_KEY=${openai_key}
EOT

# 創建 .env.docker.example 檔案
echo -e "${YELLOW}創建 .env.docker.example 檔案...${NC}"
cat << 'EOT' > .env.docker.example
NGROK_AUTH=your_ngrok_authtoken
OPENAI_API_KEY=your_openai_api_key
EOT

# 創建 Dockerfile
echo -e "${YELLOW}創建 Dockerfile...${NC}"
cat << 'EOT' > Dockerfile
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
EOT

# 創建 docker-compose.yml
echo -e "${YELLOW}創建 docker-compose.yml...${NC}"
cat << 'EOT' > docker-compose.yml
version: '3.8'

services:
  chatppt:
    build: .
    restart: always
    volumes:
      - ./outputs:/app/outputs
      - ./temp_images:/app/temp_images
      - ./logs:/app/logs
    env_file:
      - .env.docker
    ports:
      - "7860:7860"

  ngrok:
    image: wernight/ngrok
    env_file:
      - .env.docker
    environment:
      - NGROK_PORT=chatppt:7860
    ports:
      - "4040:4040"
    depends_on:
      - chatppt
EOT

# 更新 .gitignore
echo -e "${YELLOW}更新 .gitignore...${NC}"
if [ -f .gitignore ]; then
    echo ".env.docker" >> .gitignore
    echo "docker-compose.yml" >> .gitignore
else
    cat << 'EOT' > .gitignore
.env.docker
docker-compose.yml
__pycache__/
*.pyc
EOT
fi

echo -e "${GREEN}設置完成！${NC}"
echo -e "${YELLOW}你現在可以：${NC}"
echo "1. 使用以下命令啟動服務："
echo "   docker-compose --env-file .env.docker up -d"
echo "2. 查看服務狀態："
echo "   docker-compose ps"
echo "3. 查看 ngrok URL："
echo "   curl http://localhost:4040/api/tunnels"

EOF

# 使腳本可執行
chmod +x setup.sh
