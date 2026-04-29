# 使用輕量級的 Python 3.11 映像檔
FROM python:3.11-slim

# 設定工作目錄
WORKDIR /app

# 將當前目錄的所有檔案複製到容器內
COPY . .

# 安裝專案及其依賴套件
RUN pip install -e .

# 設定容器啟動時執行的預設指令 (單次執行管線)
CMD ["python", "-m", "pipeline.crew"]
