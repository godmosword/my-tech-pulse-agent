# 使用輕量級的 Python 3.11 映像檔
FROM python:3.11-slim

# 設定工作目錄
WORKDIR /app

# 將當前目錄的所有檔案複製到容器內
COPY . .

# 安裝專案及其依賴套件
RUN pip install -e .

# 正式頻道 digest 版面（📡 / 🧭 / 📈 / 🧠）；Cloud Run 仍可覆寫
ENV DIGEST_FORMAT=v1

# 設定容器啟動時執行的預設指令 (Cloud Run Job 單次執行)
CMD ["python", "main.py"]
