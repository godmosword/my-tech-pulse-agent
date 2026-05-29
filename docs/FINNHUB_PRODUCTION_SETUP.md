# Finnhub Production 啟用指南

> **Maintainer 批准後再執行。** 變更 Cloud Run Job 環境會影響 pipeline 執行與 deploy（`main` push 觸發 CI deploy）。

## 目標

在 Production Cloud Run Job 啟用 Finnhub enrich，讓財報 scorecard 含 consensus / surprise，並提升 `tech_pulse_earnings_reports` insight 品質。

## 前置

1. [Finnhub](https://finnhub.io/) 取得 API key（免費層可測 estimates/calendar）。
2. GCP 專案權限：`gcloud run jobs update`、Secret Manager（若用 secret 注入 key）。

## 環境變數（Pipeline / Cloud Run Job）

| 變數 | 值 | 說明 |
|------|-----|------|
| `EARNINGS_VENDOR_MODE` | `free` | 啟用 Finnhub（`off` 為預設 stub） |
| `FINNHUB_API_KEY` | `<your-key>` | 必填 |
| `EARNINGS_REPORTS_ENABLED` | `1` | 維持寫入 Firestore |
| `FINNHUB_HTTP_TIMEOUT_SEC` | `10` | 可選 |
| `MAX_VENDOR_CALLS_PER_RUN` | `20` | 可選，控管配額 |

完整清單見 [`EARNINGS_ENV.md`](./EARNINGS_ENV.md)。

## 設定方式 A — 直接 env（小團隊）

```bash
export CLOUD_RUN_JOB="tech-pulse-pipeline"   # 替換為 vars.CLOUD_RUN_SERVICE 實際名稱
export GCP_REGION="us-central1"
export FINNHUB_API_KEY="your_key_here"

gcloud run jobs update "$CLOUD_RUN_JOB" \
  --region="$GCP_REGION" \
  --update-env-vars="EARNINGS_VENDOR_MODE=free,EARNINGS_REPORTS_ENABLED=1" \
  --update-secrets="FINNHUB_API_KEY=finnhub-api-key:latest"
```

若不用 Secret Manager，可改 `--set-env-vars` 含 `FINNHUB_API_KEY=...`（不建議 commit key）。

## 設定方式 B — 使用 repo 腳本

```bash
./scripts/setup_finnhub_production.sh --job tech-pulse-pipeline --region us-central1
```

腳本會提示輸入 key 或讀取 `FINNHUB_API_KEY` 環境變數；**不會**把 key 寫入 git。

## 驗證

1. 手動觸發 Cloud Run Job 或等排程跑一輪 pipeline。
2. 日誌確認 `earnings_vendor_enriched_count > 0`。
3. Preflight（本地需相同 env）：

```bash
FINNHUB_API_KEY=... EARNINGS_VENDOR_MODE=free python scripts/preflight.py
```

4. Dashboard：`/earnings/MSFT`（或 watchlist 內 ticker）應顯示 insight panel；Firestore 報告含 vendor enrich 欄位。

## 回滾

```bash
gcloud run jobs update "$CLOUD_RUN_JOB" \
  --region="$GCP_REGION" \
  --update-env-vars="EARNINGS_VENDOR_MODE=off"
```

## Dashboard 分工

Vercel **不需要** `FINNHUB_API_KEY`；Dashboard 只讀 Firestore。Insight UI 見 `dashboard/app/(app)/earnings/[ticker]/page.tsx` + `loadEarningsInsight`。
