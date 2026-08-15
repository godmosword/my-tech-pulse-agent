# Finnhub Production 啟用指南

> **Maintainer 批准後再執行。** 變更 GitHub Actions secrets 會影響下一輪 `schedule.yml`。

## 目標

在 production pipeline 啟用 Finnhub enrich，讓財報 scorecard 含 consensus / surprise，並提升 `dashboard/data/earnings/` insight 品質。

## 前置

1. [Finnhub](https://finnhub.io/) 取得 API key（免費層可測 estimates/calendar）。
2. GitHub repo 可寫 Actions secrets。

## 環境變數（Pipeline / GitHub Actions）

| 變數 | 值 | 說明 |
|------|-----|------|
| `EARNINGS_VENDOR_MODE` | `free` | 啟用 Finnhub（`off` 為預設 stub） |
| `FINNHUB_API_KEY` | `<your-key>` | 必填（GHA secret） |
| `EARNINGS_REPORTS_ENABLED` | `1` | 維持寫入 JSON |
| `FINNHUB_HTTP_TIMEOUT_SEC` | `10` | 可選 |
| `MAX_VENDOR_CALLS_PER_RUN` | `20` | 可選，控管配額 |

完整清單見 [`EARNINGS_ENV.md`](./EARNINGS_ENV.md)。

## 設定

在 GitHub → Settings → Secrets and variables → Actions：

1. 新增 secret `FINNHUB_API_KEY`。
2. 若要改 `EARNINGS_VENDOR_MODE`，在 `.github/workflows/schedule.yml` 的 env 設 `free`（需 maintainer 批准）。

本機驗證可寫在 `.env`，勿 commit。

## 驗證

1. 手動 `workflow_dispatch` 或等排程跑一輪 pipeline。
2. 日誌確認 `earnings_vendor_enriched_count > 0`。
3. Preflight（本地需相同 env）：

```bash
FINNHUB_API_KEY=... EARNINGS_VENDOR_MODE=free python scripts/preflight.py
```

4. Dashboard：`/earnings/MSFT`（或 watchlist 內 ticker）應顯示 insight panel；JSON 報告含 vendor enrich 欄位。

## 回滾

把 `EARNINGS_VENDOR_MODE` 改回 `off`（workflow env 或本機 `.env`）。secret 可保留。

## Dashboard 分工

Finnhub key **只在 pipeline**。Dashboard 讀 committed JSON，不必設 `FINNHUB_API_KEY`。
