# TODOS

工程待辦與路線圖（非 CI 自動維護；重大里程碑請同步 [`CHANGELOG.md`](CHANGELOG.md)）。開發節奏見 [`docs/WORKFLOW.md`](docs/WORKFLOW.md)。

## 近期已完成（0.2.0）

- [x] Next.js Dashboard MVP（Today / Archive / Item）+ Vercel 部署文件
- [x] 公開讀模式（摘要 SEO + cookie 門控 `zh_body`）
- [x] Pipeline 寫入 `zh_summary` / `zh_body`；Portal 合約 [`docs/PORTAL_CONTRACT.md`](docs/PORTAL_CONTRACT.md)
- [x] Telegram 改為 HTML `parse_mode` + `zh_summary` 卡片
- [x] 送報後 ISR webhook（`DASHBOARD_REVALIDATE_*`）
- [x] Heuristic 三大主題白名單（AI / 半導體 / 加密）
- [x] Heuristic edge-case 測試 + 複合品質閘（主題 + 深度/具體數據）
- [x] Dashboard Archive：弱 `zh_title` fallback 至 `title`、精簡 kicker、列表顯示 `zh_summary`
- [x] Dashboard：今日熱門代號連結歸檔、中文標題 fallback、內文頁三欄（中文標題／中文摘要／英文摘要）
- [x] Staging 語意 prefilter、`NEWSAPI` 取料、`tech_pulse_digests` 快照、backfill 腳本
- [x] 部署清單 [`docs/DEPLOY_CHECKLIST.md`](docs/DEPLOY_CHECKLIST.md)；Vercel `API_READ_TOKEN` + ISR；本機 backfill 近期稿（Flash `zh_backfill`）

## 財報雷達 — 首期（2026-05-21 已合併 main）

- [x] **P0 SEC XBRL**：`sec_xbrl_fetcher`、`sec_concept_map`、`sec_submissions`、`sec_client`、fixture 測試
- [x] **P0 觸發**：`earnings_fetcher` RSS + CIK；filing 文字僅供敘事（非主數字）
- [x] **P1 模型**：`EarningsReport` / `EarningsFact`（`earnings_v2`）、`earnings_report_store`
- [x] **P5 儲存與 UI（基礎）**：`tech_pulse_earnings_reports`、`/earnings`、`/earnings/[ticker]`、`GET /api/v1/earnings`
- [x] **廣覆蓋 D**：watchlist 完整 pipeline + 非 watchlist `MAX_EARNINGS_FILINGS_BROAD` archive-only
- [x] **Watchlist**：`config/earnings_watchlist.yaml` Tier 1–5（Tier 2–5 部分 ticker 待 maintainer 補齊）
- [x] **Backfill**：`scripts/backfill_earnings.py`（`--with-llm` 可選）

## 財報雷達 — S3–S7（本輪）

- [x] **S3** `earnings_narrative_extractor` + `earnings_analyzer`；`earnings_fact_guard` v2；pipeline 不再用 LLM 抽 headline 數字
- [x] **S5** `format_earnings_v2` + `TelegramBot.send_earnings_report`
- [x] **S4（stub）** `vendor_earnings_provider`（`EARNINGS_VENDOR_MODE=off` 預設）
- [x] **S7** `pipeline_run_summary` earnings 欄位；[`docs/EARNINGS_PORTAL.md`](docs/EARNINGS_PORTAL.md)、[`docs/EARNINGS_API_EVALUATION.md`](docs/EARNINGS_API_EVALUATION.md)
- [x] **S6（API）** `GET /api/v1/earnings/calendar`、`GET /api/v1/earnings/report/{reportId}`

## 財報雷達 — 上線收工（2026-05-21）

- [x] **Production 資料**：`scripts/backfill_earnings.py`（2026-04-01〜05-21）寫入 `tech_pulse_earnings_reports`（19 筆，XBRL）；`/earnings` 與 `GET /api/v1/earnings` 已可讀
- [x] **Bugfix**：`archive_earnings_report` 移至 `FirestoreMemoryService`（backfill / pipeline memory 不再 `AttributeError`）
- [x] **Dashboard**：`GET /api/v1/earnings/report/{reportId}` 修正動態 route auth（對齊 `items/[id]`）
- [x] **ISR webhook**：Vercel `REVALIDATE_TOKEN` 與 Cloud Run `DASHBOARD_REVALIDATE_URL` + `DASHBOARD_REVALIDATE_TOKEN` 已對齊（見 [`docs/DEPLOY_CHECKLIST.md`](docs/DEPLOY_CHECKLIST.md) §1.1 / §2.2）

## 財報深度報告 v3（Finnhub + Slice A–E，2026-05-22 已合併 main）

- [x] **Slice A**：`finnhub_provider`、`scorecard_builder`（GAAP/Non-GAAP basis alignment）、`eps_non_gaap_extractor`、`/earnings/[ticker]` Firestore 修復
- [x] **Slice B**：`guidance_extractor`、`segment_extractor`、`financial_health`（XBRL FCF/CapEx）
- [x] **Slice C**：`transcript_agent` + Finnhub transcript（lazy sync + timeout）；Tier ≤ 2
- [x] **Slice D**：`conclusion_agent`、完整六段 `rendered_markdown_zh`、Telegram v3 精簡 + chunk
- [x] **Slice E**：`/earnings/report/[reportId]`、首頁「今日財報」、同 Tier 橫向比較、`GET /api/v1/earnings/ai-infra`、v2→v3 Firestore adapter

## 進行中 / 下一步

- [ ] **本機開發設定**：依 [`docs/LOCAL_DEV_SETUP.md`](docs/LOCAL_DEV_SETUP.md) 完成 `.env` / ADC / `main.py` / `backfill_zh_fields.py`（Cloud Run Secret 暫緩）
- [ ] **合約 `themes[]`**：pipeline 仍以 `category` 單值為主；若 Portal 需要陣列，additive 寫入 `themes` 並更新合約
- [ ] **歸檔舊稿繁中**（可選）：`python scripts/backfill_zh_fields.py --limit 30 --max-updates 20`

### 財報 — 待辦（依優先序）

- [ ] **Production env**：Cloud Run 設 `FINNHUB_API_KEY` + `EARNINGS_VENDOR_MODE=free`；跑一輪 pipeline 驗證 `earnings_vendor_enriched_count`
- [ ] **Backfill v3**：`scripts/backfill_earnings.py` 支援 `--deep-report` 回填歷史 `rendered_markdown_zh`（可選）
- [ ] **P4 Telegram**：長文 chunking 正式測試矩陣（雙擊/雙殺/Mixed EPS/缺 transcript）
- [ ] **P6 Preflight**：SEC + Finnhub ping + `tech_pulse_earnings_reports` smoke
- [ ] **P1 測試**：MSFT / GOOGL / TSM fiscal 邊界 fixture；transcript timeout 整合測試
- [ ] **Vendor 維運**：`tech_pulse_vendor_api_usage` + cache TTL（降 Finnhub 配額消耗）
- [ ] **Dashboard**：SiC／持倉篩選（`tags: sic`）；TradingView 圖表（可選）
- [ ] **Watchlist**：Tier 2–5 補滿至各 10 檔（不臆造 ticker）
- [ ] **Async transcript worker**：`scripts/process_earnings_transcripts.py`（`EARNINGS_TRANSCRIPT_MODE=async_worker`）
- [ ] **ETF**（SOXX / SMH）曝險參考 — Phase 2+
- [ ] **Legacy**：`EarningsAgent` 保留 smoke/judge；生產路徑僅 v3 agents

## 積壓（Backlog）

- [ ] **Heuristic 通過率觀測**：上線後從 pipeline 日誌聚合 `gate:needs_depth_or_specifics` 與 dropped 計數
- [x] **Canonical digest snapshot**：pipeline 寫入 `tech_pulse_digests/{id}`；Dashboard 首頁優先讀 snapshot
- [ ] **Semantic prefilter rollout**：staging 已可透過 `TECH_PULSE_ENV=staging` 啟用
- [ ] **Semantic dup drop**：`SEMANTIC_DUP_DROP_ENABLED=1` 需 Firestore vector index
- [ ] **Dashboard**：全文搜尋、RSS/Atom 對外訂閱（earnings 專欄基礎頁已完成）
- [ ] **DIGEST_FORMAT v2**：維持 experimental；production 仍鎖 `v1`

## 維運檢查清單（每次 deploy 後）

完整環境變數與驗證指令見 [`docs/DEPLOY_CHECKLIST.md`](docs/DEPLOY_CHECKLIST.md)。

1. Cloud Run Job 日誌出現 `pipeline_run_summary` 且 `summaries_count` > 0
2. 日誌含 `earnings_xbrl_facts_loaded`、`earnings_reports_archived`（有財報 filing 時）
3. Telegram 頻道收到 HTML digest（無 raw `&lt;` 洩漏）
4. 若已設 webhook（production 已設）：Dashboard `/`、`/archive`、`/earnings` 在送報後數秒內更新（`x-revalidate-token`）
5. `python scripts/preflight.py` 在與 production 相同 env 下通過
