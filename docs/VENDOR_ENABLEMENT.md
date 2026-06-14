# 財報 Vendor 啟用 Runbook（C3：Finnhub + FMP）

兩個 vendor enrichment 早已實裝，預設**關閉**。SEC XBRL 永遠是必備主路徑；
vendor 只是補強（consensus/surprise/quote、ratios/cash-flow），不覆寫 SEC headline。

- Finnhub（`EARNINGS_VENDOR_MODE`）：estimates / calendar / quote /（依方案）transcript。
- FMP（`EARNINGS_FUNDAMENTAL_MODE`）：FCF / ROIC / 比率補填。

> 既有參考（不在此重複）：env 清單見 [`EARNINGS_ENV.md`](EARNINGS_ENV.md)；
> Finnhub 部署細節見 [`FINNHUB_PRODUCTION_SETUP.md`](FINNHUB_PRODUCTION_SETUP.md)。

## 0. 成本/配額決策清單（啟用前逐項確認）

vendor 方案與配額常變，**以各自 dashboard 為準**，不寫死數字。啟用前確認：

- [ ] 目前方案是否允許所需 endpoint：Finnhub→ estimates/calendar/quote（+ transcript 視方案）；FMP→ ratios/cash-flow。
- [ ] 每日可用 calls 是否足夠（watchlist 檔數 × 每檔呼叫數）。
- [ ] 是否允許 production usage（部分免費層僅限個人/非商用）。
- [ ] HTTP 429 行為與當日配額耗盡的影響可接受。
- [ ] paid 方案月費是否在預算內（先用 free 驗證再決定升級）。

> **已知限制（FMP per-run cap 並非全域）**：`MAX_FMP_CALLS_PER_RUN` 由
> `FundamentalProvider` 實例內計數，但目前每筆 report 會 **新建** provider 實例
> （`_try_fundamental_enrich` 內 `FundamentalProvider()`），計數隨之歸零。因此該 cap
> 只限制「單筆 report 內」的呼叫，**不保證整輪 pipeline 的配額上限**。最壞情況約
> `MAX_FMP_CALLS_PER_RUN × 本輪 enrich 的 report 數`。啟用 paid 前請以此估算成本；
> 若需嚴格全域配額，須改 provider 生命週期（已列 follow-up，見本檔末）。

## 1. 分階段啟用（先 free，逐項 go/no-go）

每階段以 `gcloud run jobs update` 更新 Cloud Run Job env（不寫死 key 進程式碼；
key 走 Secret/env）：

### 階段 1 — Finnhub free
```bash
gcloud run jobs update "$CLOUD_RUN_SERVICE" --region "$GCP_REGION" --project "$GCP_PROJECT_ID" \
  --update-env-vars="EARNINGS_VENDOR_MODE=free" \
  --update-secrets="FINNHUB_API_KEY=finnhub-api-key:latest"   # 或 --update-env-vars 帶 key（不建議）
```
Go/No-go（觀測 ≥ 2–3 輪）：
- [ ] `filings_seen > 0` 時 `earnings_vendor_enriched_count > 0`。
- [ ] 日誌無連續 401/403/429。
- [ ] `earnings_vendor_calls` 未逼近配額。
- [ ] Dashboard 抽查至少一筆報告有 consensus/surprise，SEC headline 未被覆寫。

### 階段 2 — FMP free（階段 1 穩定後）
```bash
gcloud run jobs update "$CLOUD_RUN_SERVICE" --region "$GCP_REGION" --project "$GCP_PROJECT_ID" \
  --update-env-vars="EARNINGS_FUNDAMENTAL_MODE=free" \
  --update-secrets="FMP_API_KEY=fmp-api-key:latest"
```
Go/No-go：
- [ ] `filings_seen > 0` 時 `earnings_fundamental_enriched_count > 0`。
- [ ] 日誌無 `FMP enrich failed` 連續錯誤、無連續 429。
- [ ] Dashboard FundamentalsCard 有 FCF/ROIC/比率，且 SEC headline 未被覆寫。
- [ ] 以「已知限制」公式估算的呼叫量在配額內。

### 階段 3 — 評估 paid（選用）
僅在 free 配額不足且補強價值已驗證時升級；升級後重跑階段 1/2 的 go/no-go。

## 2. 驗證指標（pipeline_run_summary / Cloud Logging）

| 指標 | 對應 vendor | 期望 |
|------|------------|------|
| `earnings_vendor_enriched_count` | Finnhub | filings_seen>0 時 > 0 |
| `earnings_fundamental_enriched_count` | FMP | filings_seen>0 時 > 0 |
| `earnings_filings_seen` | — | 分母；為 0 時上述可為 0（非錯誤） |

本機 preflight：`FINNHUB_API_KEY=... EARNINGS_VENDOR_MODE=free python scripts/preflight.py`。

## 3. 回滾

```bash
gcloud run jobs update "$CLOUD_RUN_SERVICE" --region "$GCP_REGION" --project "$GCP_PROJECT_ID" \
  --update-env-vars="EARNINGS_VENDOR_MODE=off,EARNINGS_FUNDAMENTAL_MODE=off"
```
回滾驗證：下一輪 `earnings_vendor_enriched_count == 0` 且 `earnings_fundamental_enriched_count == 0`，
報告仍以 SEC-only 正常產生。key secret 可保留，不需刪除。

## Follow-up（未在本 slice 處理）
- FMP 全域 per-run cap：將 `FundamentalProvider` 改為整輪重用同一實例（或集中計數），
  使 `MAX_FMP_CALLS_PER_RUN` 成為真正的全輪上限。
