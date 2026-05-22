# 本機開發設定（Pipeline + Dashboard）

> 暫停 Cloud Run Secret Manager 設定時，可先用本機 `.env` 跑通財報 v3 與 Dashboard。  
> 雲端部署見 [`DEPLOY_CHECKLIST.md`](DEPLOY_CHECKLIST.md)、財報 env 見 [`EARNINGS_ENV.md`](EARNINGS_ENV.md)。

## 1. Pipeline（repo 根目錄）

```bash
cd /path/to/my-tech-pulse-agent
cp .env.example .env
```

編輯 `.env`，至少：

```bash
GEMINI_API_KEY=你的_key
SEC_USER_AGENT=tech-pulse/0.2 你的@email.com
TELEGRAM_BOT_TOKEN=...          # 若要推播
TELEGRAM_CHANNEL_ID=...

# 財報 v3 + Finnhub（本機直接寫在 .env，不必 Secret Manager）
EARNINGS_VENDOR_MODE=free
FINNHUB_API_KEY=你的_finnhub_key
EARNINGS_REPORTS_ENABLED=1

# 可選（省略則用程式預設）
FINNHUB_HTTP_TIMEOUT_SEC=10
FINNHUB_TRANSCRIPT_TIMEOUT_SEC=15
EARNINGS_TRANSCRIPT_MAX_TIER=2
MAX_VENDOR_CALLS_PER_RUN=20
```

Firestore（本機建議 **ADC**，不必設 `FIREBASE_SERVICE_ACCOUNT_JSON`）：

```bash
gcloud auth application-default login
gcloud config set project my-tech-pulse-agent-494715   # 改成你的 project id
export GOOGLE_CLOUD_PROJECT=my-tech-pulse-agent-494715
```

執行：

```bash
pip install -e .
python main.py
```

單元測試（財報相關）：

```bash
python3 -m pytest tests/test_scorecard_builder.py tests/test_guidance_segment_extractors.py -q
```

## 2. Dashboard（本機預覽 `/earnings`）

```bash
cd dashboard
cp .env.example .env.local
```

`.env.local` 擇一：

| 方式 | 設定 |
|------|------|
| **A** | `FIREBASE_SERVICE_ACCOUNT_JSON=` — 貼 `scripts/setup_dashboard_sa.sh` 產生的 JSON（raw 或 base64） |
| **B** | 留空 + 本機已 `gcloud auth application-default login` |

建議一併設定：

```bash
FIRESTORE_COLLECTION_PREFIX=tech_pulse
```

啟動：

```bash
pnpm install && pnpm dev
```

瀏覽：<http://localhost:3000/earnings>、<http://localhost:3000/earnings/report/{reportId}>

## 3. 本機 vs 雲端

| 變數 / 項目 | 本機 Pipeline | 本機 Dashboard | Vercel | Cloud Run Job |
|-------------|---------------|----------------|--------|---------------|
| `FINNHUB_API_KEY` | `.env` | 不需要 | 不需要 | Secret 或 env（需 SA 有 `secretAccessor`） |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | 通常不需要（ADC） | `.env.local` 或 ADC | **必填**（唯讀 SA） | 通常不需要（Job SA + `datastore.user`） |
| Firestore 連線 | ADC | ADC 或 JSON | JSON | Job 服務帳號 |

## 4. 之後再接 Cloud Run Secret（擱置中）

若部署出現：

`Permission denied on secret ... FINNHUB_API_KEY ... 1045005084188-compute@developer.gserviceaccount.com`

1. `gcloud run jobs describe <JOB> --format='value(spec.template.spec.template.spec.serviceAccountName)'` 確認 **實際 SA**。
2. 對該 SA 在 secret 或專案層授予 `roles/secretmanager.secretAccessor`。
3. 或暫時改 Job **一般環境變數** 直接填 `FINNHUB_API_KEY`（不用 `secretKeyRef`）先讓 revision 起來。

## 5. 驗證清單

- [ ] `python main.py` 跑完無 Firestore / Finnhub 認證錯誤
- [ ] 日誌有 `earnings_vendor_enriched_count`（Finnhub 已開時）
- [ ] `pnpm dev` 後 `/earnings` 可列出 `tech_pulse_earnings_reports`
