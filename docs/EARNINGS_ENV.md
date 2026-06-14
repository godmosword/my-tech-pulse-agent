# 財報雷達 — 環境變數與 API Key 清單

Pipeline（Cloud Run Job）與 Dashboard（Vercel）分工不同：**Finnhub 只在 pipeline 設定**；Dashboard 只需 Firestore 讀取 `tech_pulse_earnings_reports`。

## 必要（整體系統）

| 變數 | 在哪設定 | 說明 |
|------|----------|------|
| `GEMINI_API_KEY` | Pipeline | 敘事、分析、逐字稿摘要、結論 |
| `TELEGRAM_BOT_TOKEN` | Pipeline | 財報深度摘要推送（可選但 production 通常有） |
| `TELEGRAM_CHANNEL_ID` | Pipeline | 目標頻道 |
| `SEC_USER_AGENT` | Pipeline | **必填**，格式含聯絡 email（SEC 政策） |
| `FIREBASE_SERVICE_ACCOUNT_JSON` 或 GCP ADC | Pipeline + Dashboard | 寫入/讀取 Firestore |

## 財報 v3 建議開啟（Finnhub）

| 變數 | 建議值 | 說明 |
|------|--------|------|
| `EARNINGS_VENDOR_MODE` | `free` | 啟用 Finnhub；`off` 時僅 SEC Scorecard（無 consensus/surprise） |
| `FINNHUB_API_KEY` | （Finnhub 主控台） | [https://finnhub.io/](https://finnhub.io/) 免費層即可測 estimates/calendar/quote；逐字稿依方案配額 |
| `EARNINGS_REPORTS_ENABLED` | `1` | 寫入 `tech_pulse_earnings_reports` |
| `FINNHUB_HTTP_TIMEOUT_SEC` | `10` | 報價/共識/日曆 HTTP 逾時 |
| `FINNHUB_TRANSCRIPT_TIMEOUT_SEC` | `15` | 單檔逐字稿逾時（避免拖垮 Cloud Run） |
| `EARNINGS_TRANSCRIPT_MAX_TIER` | `2` | Tier ≤ 2 才拉逐字稿 + TranscriptAgent |
| `MAX_VENDOR_CALLS_PER_RUN` | `20` | 每輪 pipeline Finnhub 呼叫上限 |

## 財報 v3 可選（FMP 比率 / 現金流補充）

| 變數 | 建議值 | 說明 |
|------|--------|------|
| `EARNINGS_FUNDAMENTAL_MODE` | `off` | `off` 時純 SEC；`free`/`paid` + key 時以 FMP 補 FCF/ROIC/比率（不覆寫 SEC headline） |
| `FMP_API_KEY` | （FMP 主控台） | [https://financialmodelingprep.com/](https://financialmodelingprep.com/) |
| `MAX_FMP_CALLS_PER_RUN` | `40` | 每輪 pipeline FMP HTTP 呼叫上限 |

## 財報管線調校（可選）

| 變數 | 預設 | 說明 |
|------|------|------|
| `MAX_EARNINGS_FILINGS` | `8` | Watchlist 完整 pipeline 檔數 |
| `MAX_EARNINGS_FILINGS_BROAD` | `30` | 非 watchlist 僅 XBRL 歸檔 |
| `MAX_SEC_API_CALLS_PER_RUN` | `60` | SEC `companyfacts` 上限 |
| `EARNINGS_TELEGRAM_MIN_TIER` | `2` | Tier ≤ N 才推 Telegram |
| `EARNINGS_TRANSCRIPT_MODE` | `lazy_sync` | `lazy_sync`（同 Job 末尾）或預留 `async_worker` |

## Dashboard（Vercel）

| 變數 | 必要 | 說明 |
|------|------|------|
| `FIREBASE_SERVICE_ACCOUNT_JSON` | ✅ | 讀取 `tech_pulse_earnings_reports`（`datastore.viewer`） |
| `FIRESTORE_COLLECTION_PREFIX` | ❌ | 與 pipeline 一致，預設 `tech_pulse` |
| `REVALIDATE_TOKEN` | 建議 | 與 pipeline `DASHBOARD_REVALIDATE_TOKEN` 相同 |
| `NEXT_PUBLIC_SITE_URL` | 建議 | 公開站 canonical |
| `API_READ_TOKEN` | 視模式 | REST `/api/v1/earnings*` Bearer |

**不必**在 Vercel 設定 `FINNHUB_API_KEY`。

## 驗證

```bash
# 單元測試
python3 -m pytest tests/test_scorecard_builder.py tests/test_guidance_segment_extractors.py -q

# Pipeline 跑完後日誌應含：
# earnings_vendor_enriched_count > 0       （當 FINNHUB 已開）
# earnings_fundamental_enriched_count > 0  （當 FMP 已開）
# earnings_reports_archived > 0
#
# 分階段啟用、成本決策清單與回滾見 docs/VENDOR_ENABLEMENT.md

# Dashboard
open https://<your-host>/earnings
open https://<your-host>/earnings/report/<report_id>
```

完整部署勾選表：[`DEPLOY_CHECKLIST.md`](DEPLOY_CHECKLIST.md)。
