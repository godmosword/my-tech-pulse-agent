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

## 財報 — Phase 1 多季 Trend（2026-05-28）

- [x] **模型**：`QuarterPoint` / `MetricTrend` / `EarningsTrend`；`EarningsReport.trend`
- [x] **XBRL**：`SecXbrlFetcher.quarter_series_for_spec` / `normalize_quarter_series`
- [x] **Builder**：`agents/trend_builder.py`；`tests/test_quarter_series.py`
- [x] **Pipeline**：`build_report_from_filing` 填入 trend（Phase 3 merge 遺失已補回）
- [ ] **Dashboard UI（Phase 2）**：`/earnings/[ticker]` 或 report 頁顯示多季 trend 圖表

## Dashboard 持倉層（2026-05-28）

- [x] **`config/portfolio.yaml`** + `scripts/export_portfolio_json.py`（改 yaml 後必跑）
- [x] **`sources/portfolio.py`**、`scripts/import_ibkr_portfolio.py`（IBKR Flex XML）
- [x] **`/portfolio`** 頁、Nav「持倉」、`GET /api/v1/portfolio`
- [x] **Earnings API** `portfolio_tier` 標記
- [x] **測試**：`tests/test_portfolio_store.py`、`dashboard/lib/portfolio-metrics.test.ts`
- [ ] **UI 延伸**：`portfolio_tier` 在更多 earnings 列表／首頁露出；SiC tag 篩選

## 財報 — Phase 3 價格反應（2026-05-28）

- [x] **Finnhub `candle`** + `build_price_reaction`（SOXX 超額、四象限、degraded fallback）
- [x] **`EarningsReport.price_reaction`** + pipeline `_try_attach_price_reaction`
- [x] **ConclusionAgent** payload + 利多不漲／利空出盡規則
- [x] **Dashboard** `PriceReactionCard` on `/earnings/[ticker]`
- [x] **測試** `tests/test_price_reaction.py`（8 cases）

## 財報 — Phase 2 FMP 比率（2026-05-21）

- [x] **Provider**：`sources/fmp_provider.py`、`fmp_normalize.py`、`fundamental_provider.py`（`EARNINGS_FUNDAMENTAL_MODE=off` 預設）
- [x] **模型**：`ValuationRatios`、`SurprisePoint`；`FinancialHealth.source_conflicts`
- [x] **Pipeline**：`_try_fundamental_enrich`；SEC headline 不覆寫；FMP 失敗不影響主流程
- [x] **Dashboard**：`/earnings/[ticker]` 估值比率 + EPS surprise 迷你表
- [x] **測試** `tests/test_fmp_fundamentals.py`（7 cases）
- [ ] **Production env**：Cloud Run 設 `FMP_API_KEY` + `EARNINGS_FUNDAMENTAL_MODE=free`（見「付費 Vendor API」）

## 財報 — Phase 4 投資訊號（2026-05-21）

- [x] **`scoring/signal_engine.py`** + `signal_config.yaml`；`build_investment_signal`
- [x] **Pipeline**：`earnings_pipeline` 掛載 signal + live decision log
- [x] **Dashboard**：`/signals`、`InvestmentSignalCard`；earnings ticker 頁訊號卡
- [x] **測試** `tests/test_signal_engine.py`

## 財報 — Phase 5 Signal 回測（2026-05-21）

- [x] **`backtest/`** point-in-time replay + `scripts/backtest_signal.py`
- [x] **`decision_log`** live signal 記錄 + 事後評估
- [x] **Dashboard** `/calibration` + `BacktestCalibrationPanel`
- [x] **測試** `tests/test_backtest.py`

## 宏觀 — Phase 6 供應鏈對照（2026-05-21）

- [x] **FRED** `sources/macro_fred.py` + `_cache.py`（`FRED_API_KEY` 可選）
- [x] **供應鏈** `sources/supply_chain.py` + `config/supply_chain_manual.yaml`
- [x] **主題映射** `agents/macro_context_builder.py` → digest macro 段落
- [x] **Dashboard** `/macro` + 持倉加權環境 `portfolioEnvironment`
- [x] **測試** `tests/test_macro_context.py`（7 cases）
- [ ] **Production env**：Cloud Run 設 `FRED_API_KEY`（可選）；定期更新 `supply_chain_manual.yaml` as_of

## Dashboard dense 設計系統（2026-05-21）

- [x] **語意色 token**：`pos/neg/warn/info` + bg（light/dark）
- [x] **Dense utilities**：`.dense`、`.dense-grid`、`.data-table`、`.stat-hero`、`.section-band`
- [x] **Data components**：`StatCard`、`Delta`、`RatingBadge`、`StackedExposureBar`、`DataTable`、`SourceTag`
- [x] **數據頁重構**：`/portfolio`、`/signals`、`/macro`、`/calibration`
- [x] **校驗圖表**：recharts（僅 calibration 頁）
- [x] **手機 RWD**：DataTable 卡片化、signals 精簡列表 + 展開因子
- [x] **Portfolio UX**：Stat 防溢出、目標配置偏差表、主題中文標籤
- [x] **Backfill 空狀態**：`/signals`、`/macro`、`/calibration` 操作指引（`BackfillHint`）
- [x] **Backfill signal**：`backfill_earnings.py` 寫入 `investment_signal`
- [x] **Invest 中樞 + PWA + 麵包屑**：Nav 7→3（Today / Archive / Invest）；`/invest` 摘要；`manifest.ts` + icon；`Breadcrumb` 掛 dense／詳情頁
- [x] **Dashboard UX 五項**：Agent 評論（item 頁）、BackLink 全路由、editorial typography、持倉編輯原型、earnings insight panel
- [x] **News takeaway**：`NewsTakeawayAgent` + `NEWS_TAKEAWAY_MODE`；InstantCard／Invest 持倉相關新聞；`tests/test_news_takeaway.py`；production Flash JSON 截斷修復（2026-05-29）
- [x] **Refactor-clean（SAFE）**：`crew.py` 移除未用 `IRScraper`／`_archive_delivered_earnings`；`ThemeSection` 接回 `InstantCard` + `ConfidenceBadge`（2026-05-29）
- [x] **Dashboard UI/UX 設計審查（Slice A–E）**：InstantCard `list` variant、空狀態、`DESIGN.md`、`/health` 營運摘要、Mobile nav/a11y（2026-05-29）
- [x] **Dashboard 今日 digest 多輪合併**：合併當日 digest snapshots + 未入 snapshot 的 delivery 文章（2026-05-29）
- [x] **死碼清理（階段 2）**：`ir_scraper`、dashboard 未用 export；補 `server-only`（2026-05-29）
- [x] **Digest 重構（階段 3）**：共用 helper 收斂至 `digest.ts`（2026-05-29）
- [x] **Today fallback 修正（階段 4）**：`loadTodayDigestData()`、stale 提示、Firestore 降級（2026-05-29）
- [x] **CI dashboard job**：typecheck + vitest + production build（2026-05-29）
- [x] **CI 品質閘（DoD）**：ruff / pyright / vulture / pytest coverage ≥62% / Dashboard ESLint + `api-routes` vitest（2026-05-30）
- [x] **Agent 規範**：[`CLAUDE.md`](CLAUDE.md) + [`.cursorignore`](.cursorignore)（2026-05-30）
- [x] **Finnhub 啟用文件**：[`docs/FINNHUB_PRODUCTION_SETUP.md`](docs/FINNHUB_PRODUCTION_SETUP.md) + `scripts/setup_finnhub_production.sh`（production env 待批准執行）
- [x] **Dashboard 六階段審查（2026-05-31）**：legacy CSS 移除、lib export 收斂；共用 `format-numbers`／`login-path`／`BrandMark`／`InstantCardNewsList`；`SignalsTable` 手機版 Link／button 分離；a11y（`:focus-visible`、login `role="alert"`、Relationships `<details>`、BacktestCharts `aria-label`）；`npm run lint` + typecheck + vitest + build 全綠

## 進行中 / 下一步

- [ ] **本機開發設定**：依 [`docs/LOCAL_DEV_SETUP.md`](docs/LOCAL_DEV_SETUP.md) 完成 `.env` / ADC / `main.py` / `backfill_zh_fields.py`（Cloud Run Secret 暫緩）
- [ ] **EarningsAgent 類別**：`agents/earnings_agent.py` 僅 smoke test 引用 — 刪除或保留待決
- [ ] **API route 測試延伸**：其餘 `/api/v1/news/*`、`items/[id]`、`archive/facets` 等 handler vitest
- [x] **Slice 1 Portal News API**：`/api/v1/news/*` + [`docs/QSILICON_INTEGRATION.md`](docs/QSILICON_INTEGRATION.md)
- [x] **Slice 2 Earnings API**：`/api/v1/earnings/upcoming`、`/{symbol}/insight`、`/watchlist`；watchlist 併 Q-Silicon mega-cap
- [ ] **主 repo 瘦身**：依 [`docs/QSILICON_INTEGRATION.md`](docs/QSILICON_INTEGRATION.md) §主 repo 作業清單
- [ ] **合約 `themes[]`**：pipeline 仍以 `category` 單值為主；若 Portal 需要陣列，additive 寫入 `themes` 並更新合約
- [ ] **歸檔舊稿繁中**（可選）：`python scripts/backfill_zh_fields.py --limit 30 --max-updates 20`

### 財報 — 待辦（依優先序）

- [ ] **Backfill v3**：`scripts/backfill_earnings.py` 支援 `--deep-report` 回填歷史 `rendered_markdown_zh`（可選；SEC/XBRL + LLM，不依賴 Vendor key）
- [ ] **P4 Telegram**：長文 chunking 正式測試矩陣（雙擊/雙殺/Mixed EPS/缺 transcript）
- [ ] **P6 Preflight**：SEC 連線 + `tech_pulse_earnings_reports` smoke（Finnhub ping 見下方「付費 Vendor API」）
- [x] **P1 測試**：MSFT / GOOGL / TSM fiscal 邊界 fixture（[`docs/fixtures/FISCAL_BOUNDARY_FIXTURES.md`](docs/fixtures/FISCAL_BOUNDARY_FIXTURES.md)）
- [ ] **Dashboard**：SiC／持倉篩選（`tags: sic`）；TradingView 圖表（可選）
- [ ] **Watchlist**：Tier 2–5 補滿至各 10 檔（不臆造 ticker）
- [ ] **ETF**（SOXX / SMH）曝險參考 — Phase 2+
- [ ] **Legacy**：`EarningsAgent` 保留 smoke/judge；生產路徑僅 v3 agents

## 付費 Vendor API（暫緩）

程式已合併（Finnhub provider、price_reaction、transcript、vendor enrich、**FMP fundamental enrich**）；**production 暫不申請／不設定付費或配額型 API key**。未設 key 時 pipeline 仍以 SEC XBRL 為主，`price_reaction` / transcript / 共識 estimate / FMP 比率可能為 `degraded` 或略過。評估與 env 對照見 [`docs/EARNINGS_API_EVALUATION.md`](docs/EARNINGS_API_EVALUATION.md)、[`docs/EARNINGS_ENV.md`](docs/EARNINGS_ENV.md)。

- [ ] **Production env**：Cloud Run 設 `FINNHUB_API_KEY`；`EARNINGS_VENDOR_MODE=free`（或 `paid`）；跑一輪 pipeline 驗證 `earnings_vendor_enriched_count`（見 [`docs/FINNHUB_PRODUCTION_SETUP.md`](docs/FINNHUB_PRODUCTION_SETUP.md)）
- [ ] **Production env（FMP）**：`FMP_API_KEY` + `EARNINGS_FUNDAMENTAL_MODE=free`；驗證 report 含 `ratios` / `surprise_history`
- [x] **FMP 程式**：`fmp_provider` / `fundamental_provider` / normalize + pipeline hook（`off` = 純 SEC）
- [ ] **P2 Vendor 實作**：Finnhub HTTP 完整接線；`tech_pulse_vendor_api_usage` + cache TTL（降配額消耗）
- [ ] **Preflight**：Finnhub ping（calendar / quote / candle）
- [ ] **Async transcript worker**：`scripts/process_earnings_transcripts.py`（`EARNINGS_TRANSCRIPT_MODE=async_worker`）；Finnhub transcript 配額
- [ ] **P1 整合測試**：transcript timeout；有 key 時 end-to-end `price_reaction` + scorecard surprise
- [ ] **Backfill（需 key）**：歷史報告補 `price_reaction`、Finnhub 共識／transcript（可選）
- [ ] **其他付費來源**（評估中）：FMP paid tier、NewsAPI / Apify 配額監控與降本

## 積壓（Backlog）

- [ ] **Heuristic 通過率觀測**：上線後從 pipeline 日誌聚合 `gate:needs_depth_or_specifics` 與 dropped 計數
- [x] **Canonical digest snapshot**：pipeline 寫入 `tech_pulse_digests/{id}`；Dashboard 首頁優先讀 snapshot
- [ ] **Semantic prefilter rollout**：staging 已可透過 `TECH_PULSE_ENV=staging` 啟用
- [ ] **Semantic dup drop**：`SEMANTIC_DUP_DROP_ENABLED=1` 需 Firestore vector index
- [ ] **Dashboard a11y／效能（低優先）**：Archive 篩選 `aria-current`、DataTable `scope`、skip link；`/calibration` Recharts `next/dynamic`；Archive 手機篩選位置（列表下方）；首頁 digest 與 `@rail` 重複 fetch（可 `React.cache()`）
- [ ] **Dashboard**：全文搜尋、RSS/Atom 對外訂閱（earnings 專欄基礎頁已完成）
- [ ] **DIGEST_FORMAT v2**：維持 experimental；production 仍鎖 `v1`

## 自動關係層（2026-05-28）

- [x] 10-K 關係抽取（Gemini + quote 驗證）與 `data/relationships/` 離線腳本
- [x] 價格相關性聚類 + `data/clusters.json` 離線腳本
- [x] Dashboard `GET /api/v1/relationships`、財報 ticker 關係區塊、持倉曝險穿透卡
- [ ] 定期 Cron：`extract_relationships.py`（年更）、`build_clusters.py`（週更）；production 填入 `GEMINI_API_KEY` / `FINNHUB_API_KEY` 後重跑

## 維運檢查清單（每次 deploy 後）

完整環境變數與驗證指令見 [`docs/DEPLOY_CHECKLIST.md`](docs/DEPLOY_CHECKLIST.md)。

1. Cloud Run Job 日誌出現 `pipeline_run_summary` 且 `summaries_count` > 0
2. 日誌含 `earnings_xbrl_facts_loaded`、`earnings_reports_archived`（有財報 filing 時）
3. Telegram 頻道收到 HTML digest（無 raw `&lt;` 洩漏）
4. 若已設 webhook（production 已設）：Dashboard `/`、`/archive`、`/earnings` 在送報後數秒內更新（`x-revalidate-token`）
5. `python scripts/preflight.py` 在與 production 相同 env 下通過
