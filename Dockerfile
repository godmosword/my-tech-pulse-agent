FROM python:3.11-slim

WORKDIR /app
COPY . .

# 安裝專案及其依賴套件
RUN pip install -e .

# 設定單次執行管線的指令
CMD ["python", "-m", "pipeline.crew"]
