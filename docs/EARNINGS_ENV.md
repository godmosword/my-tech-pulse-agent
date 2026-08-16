# 財報雷達 — 環境變數與 API Key 清單

Pipeline（GitHub Actions）與 Dashboard（Vercel）分工不同：**Finnhub 只在 pipeline 設定**；Dashboard 讀 `dashboard/data/earnings/`。來源路徑見 [`SOURCES.md`](SOURCES.md)。

**GHA 現況**：`schedule.yml` 未設 `EARNINGS_VENDOR_MODE`／`EARNINGS_FUNDAMENTAL_MODE`，程式預設皆 `off`。有 `FINNHUB_API_KEY`／`FMP_API_KEY` **不代表**已開。Telegram 頻道推送已關；財報只寫 JSON。

## 必要（整體系統）

| 變數 | 在哪設定 | 說明 |
|------|----------|------|
| `OPENAI_API_KEY` | Pipeline | 敘事、分析、逐字稿摘要、結論 |
| `SEC_USER_AGENT` | Pipeline | **必填**，格式含聯絡 email（SEC 政策）。XBRL 與 `earnings_fetcher`／10-K 正文皆走此值 |
| `DASHBOARD_DATA_DIR` | Pipeline | JSON 輸出目錄（預設 `dashboard/data`） |

`TELEGRAM_BOT_TOKEN`／`TELEGRAM_CHANNEL_ID` 已不需要。內容走 `dashboard/data` → Vercel。

## 財報 v3 可選開啟（Finnhub；GHA 預設 off）

| 變數 | 預設 | 說明 |
|------|------|------|
| `EARNINGS_VENDOR_MODE` | `off` | 設 `free`／`paid` 才啟用 Finnhub；`off` 時僅 SEC Scorecard（無 consensus/surprise） |
| `FINNHUB_API_KEY` | （空） | [https://finnhub.io/](https://finnhub.io/)；mode=`off` 時即使有 key 也不 enrich |
| `EARNINGS_REPORTS_ENABLED` | `1` | 寫入 `dashboard/data/earnings/` |
| `FINNHUB_HTTP_TIMEOUT_SEC` | `10` | 報價/共識/日曆 HTTP 逾時 |
| `FINNHUB_TRANSCRIPT_TIMEOUT_SEC` | `15` | 單檔逐字稿逾時 |
| `EARNINGS_TRANSCRIPT_MAX_TIER` | `2` | Tier ≤ 2 才拉逐字稿 + TranscriptAgent |
| `MAX_VENDOR_CALLS_PER_RUN` | `20` | 每輪 pipeline Finnhub 呼叫上限 |

## 財報 v3 可選（FMP 比率 / 現金流補充）

| 變數 | 建議值 | 說明 |
|------|--------|------|
| `EARNINGS_FUNDAMENTAL_MODE` | `off` | GHA 未覆寫。`off` 時純 SEC；`free`/`paid` + key 時以 FMP 補 FCF/ROIC/比率（不覆寫 SEC headline） |
| `FMP_API_KEY` | （FMP 主控台） | [https://financialmodelingprep.com/](https://financialmodelingprep.com/) |
| `MAX_FMP_CALLS_PER_RUN` | `40` | 每輪 pipeline FMP HTTP 呼叫上限 |

## 財報管線調校（可選）

| 變數 | 預設 | 說明 |
|------|------|------|
| `MAX_EARNINGS_FILINGS` | `8` | Watchlist 完整 pipeline 檔數 |
| `MAX_EARNINGS_FILINGS_BROAD` | `30` | 非 watchlist 僅 XBRL 歸檔 |
| `MAX_SEC_API_CALLS_PER_RUN` | `120` | SEC submissions + `companyfacts` 上限 |
| `EARNINGS_WATCHLIST_SUBMISSIONS` | `1` | `1` 時 watchlist 另查 CIK submissions；Atom 仍供廣覆蓋 |
| `EARNINGS_WATCHLIST_SUBMISSIONS_DAYS` | `7` | submissions 回看天數 |
| `EARNINGS_TELEGRAM_MIN_TIER` | `2` | 舊旗標；頻道推送已關，不影響 JSON 歸檔 |
| `EARNINGS_TRANSCRIPT_MODE` | `lazy_sync` | `lazy_sync`（同 Job 末尾）或預留 `async_worker` |

## Dashboard（Vercel）

| 變數 | 必要 | 說明 |
|------|------|------|
| `REVALIDATE_TOKEN` | 可選 | GHA commit 後 Vercel 會重建 |
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
