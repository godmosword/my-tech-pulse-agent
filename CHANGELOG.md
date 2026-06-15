# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added
- **投資訊號證據治理（Phase 0／投資升級計劃第一階段）**：把「能算出數字」與「能形成可交易信心」分離。新增 `scoring/track_record.py`（純函式校準層）：命中率 + **Wilson 區間**、平均超額 + **bootstrap 區間**、Spearman IC、**有效獨立樣本數**估計（半導體高度相關，名目 n 高估資訊量）、多重比較警示，並產出 `evidence_level`（insufficient/weak/moderate/strong）——**與訊號既有 `conviction`（輸入完整度）分離，決策層只能用它軟化語氣、不得當買賣建議**。`backtest/decision_log.py` 每筆 additive 記 `signal_version`／`factor_set`／逐因子 score/availability／`benchmark`／`universe_asof`，track record 只比同版本（解決 live 含 market_confirmation、backtest 排除之不一致）；`scoring/signal_config.yaml` 加 `version: v1`。`scripts/grade_decisions.py`（嚴格交易日 maturity + skipped 原因分類，point-in-time 走 `backtest/pit_data`）輸出 `backtest/results/track_record.json`。`backtest/universe.py` + `config/historical_universe.json` 提供 point-in-time universe 快照與 **survivorship 覆蓋揭露**（偏誤偏樂觀）。Dashboard `/calibration` 新增 `TrackRecordPanel`（evidence 徽章、Wilson/bootstrap CI、n/有效樣本、survivorship、免責），缺檔時不渲染。`tests/test_track_record.py`、`tests/test_decision_log_schema.py`。純 additive，不改既有訊號決策與對外契約。（營運收尾：排程跑 `grade_decisions.py` 累積戰績——待維護者決定 cadence。）
- **Dashboard 關鍵字搜尋（取代標題前綴）**：搜尋從「標題開頭比對」改為**詞元（token）比對**，解決「搜尋不到文章」。新增 `scoring/search_tokens.py` 為唯一真實來源（英數詞小寫、長度 ≥ 2；CJK 轉**字元 bigram** 使任一 2 字子字串可命中；ticker 小寫；identity 欄位優先、summary 補滿 ≤ 80 token），`memory_store._write_payload` 對全部 4 條 archive 路徑 additive 寫入 `search_tokens`；`dashboard/lib/search-tokens.ts` 為**位元級鏡像**（查詢端），`search-firestore.ts` 改用 `array-contains-any` 並依命中數→新近排序，保留 ticker 精確比對與標題前綴作為未 backfill 文件的 graceful fallback。`scripts/backfill_search_tokens.py`（idempotent、分頁、`--dry-run`/`--force`）回填既有文件。NavSearch 加放大鏡 icon、清除鈕，提示文字改「代號精確比對 · 標題與內文關鍵字」。`tests/test_search_tokens.py` 與 `dashboard/lib/search-tokens.test.ts` 平價釘住契約。免新增 Firestore 索引（單欄陣列預設索引）。
- **財報 Vendor 啟用收尾（C3）**：新增 `earnings_fundamental_enriched_count` 指標（鏡像 Finnhub 的 `earnings_vendor_enriched_count`，additive 進 `pipeline_run_summary`），讓 FMP 啟用可乾淨驗證；`docs/VENDOR_ENABLEMENT.md` 分階段啟用 runbook（成本決策清單、Finnhub free→FMP free→paid 的 go/no-go、雙指標驗證、回滾），並誠實標註 FMP `MAX_FMP_CALLS_PER_RUN` 因 provider 每筆重建而非全輪強制（TODOS follow-up）。`tests/test_fmp_fundamentals.py` 補 `_try_fundamental_enrich` 計數語意測試。vendor 仍預設 off。
- **Pipeline 自動排程（C1）**：`.github/workflows/schedule.yml`（cron + `workflow_dispatch`，重用既有 WIF，**預設停用**：須 `vars.PIPELINE_SCHEDULE_ENABLED=true`；手動 dispatch 不受限；`gcloud run jobs execute --wait`、20 分 timeout、concurrency 防重疊）；`scripts/setup_cloud_scheduler.sh`（idempotent、`DRY_RUN`、Cloud Scheduler→Cloud Run Job 用 **OAuth** SA）；`docs/SCHEDULED_RUNS.md` runbook（兩路徑擇一、UTC↔Taipei 對照、監控靠 pipeline 告警、啟用驗證清單）。純新增，不改既有 CI/pipeline。
- **語義去重可觀測 rollout（A7）**：`_apply_memory_context` 新增 shadow 指標 `semantic_dup_checked`／`_would_drop`／`_dropped`（旗標關閉時仍計算「若開啟會丟幾筆」），逐筆候選 log 以 `SEMANTIC_DUP_SHADOW_LOG` 開關；指標 additive 加入 `pipeline_run_summary` 與 digest funnel（**去重決策與既有鍵不變**）；run 起始重設避免 stale。`docs/SEMANTIC_DEDUP_ROLLOUT.md` runbook（部署索引→shadow 觀測→決策門檻→翻旗→回滾）；`tests/test_semantic_dedup_shadow.py`。（向量索引建置、一週觀測、翻旗屬維護者 GCP 操作。）
- **pyright 型別檢查擴大（D5）**：`pyrightconfig.json` include 從 `sources`/`scoring` 擴到全核心套件（`pipeline`/`delivery`/`llm`/`backtest`/`agents`，維持 basic）；修掉因此暴露的 25 處型別問題（行為保留：`int/float(Optional)` 改用已過濾的 subscript、comprehension 提前轉型、`hasattr`+`is not None`、`assert self._bot is not None`、`Iterable` 守衛）。**型別檢查抓到 2 個真實 bug**：`pipeline/earnings_pipeline.py` 存取不存在的 `EarningsFiling.cik`（必拋 AttributeError，改為 `cik_map.cik_for`）；`backtest/pit_data.py` `until_day` 可能為 None 導致 `date > None` 崩潰（補 guard）。CI step 與 CLAUDE.md 同步。
- **Firestore 索引部署自動化（D4）**：`firebase.json` + `scripts/deploy_firestore_indexes.sh`（驗證 JSON、`npx firebase-tools@13 --non-interactive` 部署、維護者執行）；`tests/test_firestore_indexes.py` 守住既有 3 索引與 2 TTL override；`DEPLOY_CHECKLIST` 指向腳本並註明 prefix/(default) DB 假設與 processed_articles/embeddings TTL 缺口。
- **載入骨架（B2）**：共用 `components/data/PageSkeleton`（中性 shimmer、`role="status"`＋`aria-busy`＋`motion-safe:animate-pulse`，色塊 `aria-hidden`）；`app/(app)/loading.tsx`（主內容欄 Suspense fallback，不重建 chrome）與 `@rail/loading.tsx`（右欄極簡 fallback）；`components/data/PageSkeleton.test.tsx`。
- **圖表 Tooltip 對比與卡片層級（B6）**：`BacktestCharts` 兩個 Tooltip 抽共用樣式常數並補 `color`／`labelStyle`／`itemStyle`（深色模式文字可讀，淺色模式視覺等價）；`globals.css` 巢狀 `.section-band .data-table-card` 改用 `--color-paper`（theme-aware）與外層 band 區隔層級，取代全站陰影方案。
- **評分閾值可配置/可觀測（A5）**：`Scorer.threshold()` 泛化 env override（`SCORE_THRESHOLD` 為 default、`SCORE_THRESHOLD_<TYPE>` 如 `SCORE_THRESHOLD_KOL` 為其餘類型）；新增 `_env_float` 統一解析（未設／空字串／非法值皆回退 yaml 預設，不再因 `SCORE_THRESHOLD=` 崩潰）；`filter_articles` 依 effective_type（default／kol）分桶輸出 `Threshold summary` 通過率日誌供漂移調參；`tests/test_scorer_thresholds.py`；`.env.example` 修正預設註解 7.2→6.8 並補 `SCORE_THRESHOLD_KOL`。預設行為不變。
- **Watchlist 覆蓋稽核（A6）**：`sources/watchlist_audit.py` + `scripts/watchlist_coverage.py`（唯讀，不改 yaml、不臆造 ticker）；報告各 tier 筆數、重複（同 tier）／跨 tier 衝突、tag 分佈、異常 tier 值；`--observed`（CSV ticker/symbol 或 JSON 三種形）／`--tickers` 提供實際觀測資料時列出「不在 watchlist 的候選」供人工確認；`--targets` JSON 計算各 tier 缺口；`tests/test_watchlist_audit.py`。
- **資料表無障礙（B3）**：所有 `<th>` 加 `scope="col"`（共用 `DataTable`、`PortfolioEditorPrototype`、`FundamentalsCard` EPS Surprise 表、`EarningsReportMarkdown` GFM 表）；`PortfolioEditorPrototype`／`FundamentalsCard` 表格以 `aria-labelledby` 指向章節標題取得無障礙名稱；`components/PortfolioEditorPrototype.test.tsx` 斷言 table accessible name 與欄標題。視覺與行為不變。（B4 recharts 懶載／portfolio `Promise.all` 經查證不適用：recharts 已路由隔離於單一 `/calibration` chunk，portfolio 僅單一 async await，其餘載入皆同步。）
- **Portal API 測試補齊（D3）**：`lib/api-routes.test.ts` 新增 `/news/digest`、`/news/deep`、`/news/deep/[itemId]`、`/news/themes`、`/archive/facets`、`/items/[id]` handler 測試（含 422 驗證、404、503 降級、pillar 過濾、facet 統計），覆蓋面 9 → 15 個 v1 handler；保留真實純轉換（themeCounts／buildFacets／serializeItem），僅 stub Firestore 載入。
- **RSS/KOL 抓取重試**：`RSSFetcher._get_with_retry` 對暫時性錯誤（timeout／transport／5xx／429）重試，永久回應（304／其他 4xx／2xx）即時返回；尊重 `Retry-After`（上限 5s）；`RSS_MAX_ATTEMPTS`（預設 2，1 停用）；成功路徑與 304／fallback 行為不變；`tests/test_rss_retry.py`。
- **Dashboard UX：登入 CTA + 統一時區**：`LoginToReadCta`（漸層遮蔽處「登入閱讀完整內容」→ `/login?returnTo=`）；`lib/format-datetime.ts`（`zh-TW` + `Asia/Taipei` 日期／日期時間）；`digest` 日期函式收斂；vitest 含跨日邊界。
- **Dashboard 導覽搜尋**：`GET /api/v1/search?q=`（Zod 驗證、ticker 精確比對 + 標題/公司前綴）；`NavSearch` combobox（debounce 300ms、鍵盤導覽、行動版放大鏡全寬展開）；vitest 覆蓋 API 與元件。
- **Dashboard 列表「載入更多」分頁**：`/archive`、`/earnings`、`/signals` 首頁 40 筆 + client「載入更多」；`GET /api/v1/items`、`/earnings`、`/earnings/signals` 支援 `cursor`／`limit`（Firestore `startAfter`／訊號分數 cursor）；回應新增 `nextCursor`（additive）；`LoadMoreButton`、`pagination-cursor`、vitest 覆蓋。
- **財報 v3 報告頁 Markdown 渲染**：`react-markdown` + `remark-gfm`；`EarningsReportMarkdown` 章節目錄（lg 側欄 sticky / 手機下拉）；`SurpriseBadge` 改用语義色 token；空內容 `EarningsReportEmpty`；vitest 覆蓋。
- **Signal 權重建議離線腳本**：`scripts/suggest_signal_weights.py` + `backtest/weight_suggestions.py`；讀回測 records 計算各因子 Spearman 相關性，輸出 `weight_suggestions.json` / `.md`（不自動改 `signal_config.yaml`；樣本 < 門檻標示資料不足）；`tests/test_weight_suggestions.py`。
- **Telegram 摘要回饋按鈕**：每日 digest intro／item 卡片附 👍／👎 inline keyboard；管線開頭 `getUpdates` 批次拉取 callback → `tech_pulse_feedback`（同 user+target 覆寫）；`delivery/feedback_poller.py`、`scoring/feedback_store.py`；`tests/test_feedback_vote.py`。
- **Pipeline 失敗 Telegram 告警**：未處理例外時經 `delivery/pipeline_alert.py` 發送簡短告警（環境、管線名稱、例外類型、訊息前 200 字、Asia/Taipei 時間戳）；`TELEGRAM_ALERT_CHAT_ID`（未設定時 fallback `TELEGRAM_CHANNEL_ID`）；`main.py` 與 `pipeline/crew.py` entry point；`tests/test_pipeline_alert.py`。
- **Dashboard 共用模組（六階段審查）**：`lib/format-numbers.ts`（`fmtNum`／`fmtPctPlain`／`fmtPctSigned`）、`lib/login-path.ts`（`loginReturnHref`）；`BrandMark`、`InstantCardNewsList`（Today 主題／持倉新聞列表共用）。
- **Agent 工作規範**：根目錄 [`CLAUDE.md`](CLAUDE.md)（繁中 DoD、驗證指令對齊 CI）；[`.cursorignore`](.cursorignore) 排除 build 產物與 lock 檔以降低 token 消耗。
- **CI 品質閘（DoD 工具鏈）**：Python `ruff` / `pyright`（`sources`+`scoring`，basic）/ `vulture` + 白名單；pytest `--cov-fail-under=62`（核心套件）；Dashboard 獨立 `eslint.config.mjs` + `npm run lint`；`dashboard/lib/api-routes.test.ts` 覆蓋 9 個 `/api/v1` handler（health、portfolio、earnings、items、relationships、tickers、digest/today、auth 401/503）。
- **Fiscal boundary fixtures（MSFT / GOOGL / TSM）**：[`docs/fixtures/FISCAL_BOUNDARY_FIXTURES.md`](docs/fixtures/FISCAL_BOUNDARY_FIXTURES.md) + 離線 `companyfacts` JSON；`tests/test_fiscal_boundary_fixtures.py`、`tests/test_sec_xbrl_accession_strict.py`；SEC submissions archive 分頁 fixture。
- **Dashboard 營運摘要 `/health`**：`summarizeHealth()` + vitest；指標卡（最近上線、24h/7d、類型／品質分佈）+ 近期列表連 `/item/[id]`；Nav「營運摘要」；規格 [`docs/superpowers/specs/2026-05-18-pulse-health-dashboard-design.md`](docs/superpowers/specs/2026-05-18-pulse-health-dashboard-design.md)。
- **Dashboard 設計文件**：[`dashboard/DESIGN.md`](dashboard/DESIGN.md)（editorial vs dense token、InstantCard variants、禁止項）。
- **Dashboard UX 五項修復**：`AgentCommentary`（文章頁 wh/why + 空狀態）；`BackLink` + dense 子頁／archive／invest／earnings 返回路徑；editorial 響應式 typography token（`text-editorial-*`）；`PortfolioEditorPrototype`（local 編輯 + 匯出 YAML）；`/earnings/[ticker]` `EarningsInsightPanel`（`loadEarningsInsight`）；Invest「與我持倉相關的新聞」區塊。
- **News takeaway（additive）**：`NewsTakeawayAgent` + `NEWS_TAKEAWAY_MODE`；pipeline 寫入 Firestore `takeaway`；Dashboard `NewsTakeawayBlock` + `tagItemPortfolioRelevance`；`tests/test_news_takeaway.py`、`portfolio-relevance.test.ts`。
- **Finnhub production 啟用指南**：[`docs/FINNHUB_PRODUCTION_SETUP.md`](docs/FINNHUB_PRODUCTION_SETUP.md)、[`scripts/setup_finnhub_production.sh`](scripts/setup_finnhub_production.sh)（Cloud Run env 需 maintainer 批准後執行）。
- **Dashboard Invest 中樞 + PWA + 麵包屑**：導航 7→3（Today / Archive / Invest）；`/invest` 五區塊摘要（持倉、訊號、財報、宏觀、校驗）；`app/manifest.ts` + `public/` 品牌 icon（`npm run gen-icons`）；`Breadcrumb` + `DensePageShell` optional prop；dense 頁與財報／文章詳情頂部返回路徑；`layout` `appleWebApp` / `themeColor`。
- **自動關係層（additive，離線）**：`agents/relationship_models.py`、`relationship_extractor.py`（Gemini 10-K 關係 + `verify_quote_substring`）；`config/company_aliases.yaml`、`scripts/seed_company_aliases.py`、`scripts/extract_relationships.py` → `data/relationships/{ticker}.json`；`scoring/correlation_cluster.py`、`scripts/build_clusters.py` → `data/clusters.json`；`GET /api/v1/relationships`；財報 ticker 頁「關係」區塊 + 持倉頁「曝險穿透」卡；`tests/test_relationship_extractor.py`、`test_correlation_cluster.py`、`dashboard/lib/exposure-passthrough.test.ts`。
- **Dashboard backfill 指引**：`BackfillHint` / `BackfillCode`；`/signals`、`/macro`、`/calibration` 空狀態附本機 backfill 指令與 Vercel 限制說明。
- **Dashboard dense 模式 + 美股語意色**：`globals.css` 新增 `pos/neg/warn/info` token（深淺色）；Tailwind 映射；`components/data/`（`StatCard`、`Delta`、`RatingBadge`、`StackedExposureBar`、`DataTable`、`SourceTag`、`DensePageShell`、`SignalsTable`）；`/portfolio`、`/signals`、`/macro`、`/calibration` 改用 dense 排版；校驗頁引入 `recharts` 分位/校準圖（語意色）。Editorial 頁（digest/文章/財報敘述）不變。
- **Phase 6 — 宏觀與供應鏈對照（additive）**：`sources/macro_fred.py`（FRED，無 key graceful）、`sources/supply_chain.py`（TSM 月營收 + SIA/ASML manual yaml）、`sources/_cache.py`（檔案 TTL 快取）；`agents/macro_context_builder.py`（`theme_bias` 順逆風）；digest synthesizer 末段「宏觀與供應鏈對照」；`pipeline/crew.py` 寫 `output/macro_context_latest.json`；Dashboard `/macro` + `portfolioEnvironment()`；`tests/test_macro_context.py`（7 cases）。
- **Phase 5 — Signal 回測校驗（point-in-time）**：`backtest/`（`pit_data`、`replay`、`metrics`、`decision_log`）、`scripts/backtest_signal.py`；`scoring/signal_engine.py` 支援 `exclude_factors`；live `log_live_signal`；Dashboard `/calibration`；`tests/test_backtest.py`。
- **Phase 4 — 投資訊號引擎**：`scoring/signal_engine.py` + `scoring/signal_config.yaml`（fundamental / surprise / market / quality 因子）；`EarningsReport.investment_signal`；pipeline 掛載 + `decision_log`；Dashboard `/signals`、`InvestmentSignalCard`；`tests/test_signal_engine.py`。
- **財報 Phase 2 — FMP 比率 / 現金流（additive）**：`FmpProvider`、`fmp_normalize`、`FundamentalProvider`（`EARNINGS_FUNDAMENTAL_MODE=off` 預設）；`ValuationRatios` / `SurprisePoint`；`build_financial_health(..., fundamentals=)` 補 FCF/ROIC、SEC vs FMP `source_conflicts`；Dashboard `FundamentalsCard`；`tests/test_fmp_fundamentals.py`（7 cases）。
- **財報 Phase 1 — 多季 Trend**：`QuarterPoint` / `MetricTrend` / `EarningsTrend`；`SecXbrlFetcher.normalize_quarter_series`；`agents/trend_builder.py`；`build_report_from_filing` 填入 `EarningsReport.trend`（`tests/test_quarter_series.py`）。
- **Dashboard 持倉層**：`config/portfolio.yaml`、`sources/portfolio.py`、`scripts/import_ibkr_portfolio.py`、`scripts/export_portfolio_json.py`；`/portfolio` 頁 + Nav「持倉」；`GET /api/v1/portfolio`；earnings API `portfolio_tier`；`portfolio-metrics` vitest + `tests/test_portfolio_store.py`。
- **財報 Phase 3 — 價格反應 `price_reaction`**：`FinnhubProvider.candle`、`price_reaction_builder`（1d/5d vs SOXX、四象限 label）；`EarningsReport.price_reaction`；結論層 payload；Dashboard `/earnings/[ticker]` 市場反應卡。
- **Portal Earnings API（Slice 2）**：`GET /api/v1/earnings/upcoming`、`/{symbol}/insight`、`/watchlist`；Finnhub 行事曆 + Firestore fallback；`config/earnings_watchlist.yaml` 併入 Q-Silicon mega-cap；`scripts/export_earnings_watchlist_json.py`。
- **Portal News API（Slice 1）**：`GET /api/v1/news/digest|deep|deep/{id}|themes`（`dashboard/lib/news-api.ts`），對齊 Q-Silicon `api_routers/news.py`；digest 含 `summary` 供 `TECH_PULSE_URL`。
- **Translation Agent**（`agents/translation_agent.py`）：Extractor 未產出含 CJK 的 `zh_title` / `zh_summary` 時，以 Gemini Flash 補繁中標題與兩句摘要；`pipeline_run_summary.translation_filled_count`；`TRANSLATION_AGENT_ENABLED`（預設 `1`）。
- [`docs/EARNINGS_ENV.md`](docs/EARNINGS_ENV.md) — 財報 v3 Pipeline / Dashboard 環境變數與 API key 對照表。

### Changed
- **Dashboard 程式品質（六階段審查）**：移除 `globals.css` legacy 樣式（`.kicker`／`.dek` 等零引用）；`lib/*` 未用 export 收斂；`ThemeSection`／`HoldingNewsSection` 改共用 `InstantCardNewsList`；`FundamentalsCard`／`PriceReactionCard`／`NavRail` 等接共用格式化與品牌元件。
- **SignalsTable（手機 RWD）**：代號 Link 與展開因子 button 分離，修 nested interactive；補 `aria-expanded`／`aria-controls`／`min-h-[44px]`。
- **RelationshipsSection**：10-K 原文由 hover-only 改 `<details>`／`<summary>`，鍵盤與螢幕閱讀器可達。
- **Pyright**：`pyrightconfig.json` 限定 `sources`+`scoring`；`typeCheckingMode: basic`（strict 在現有 codebase 有 700+ 誤報）；`memory_store._make_vector()` 解決 optional call。
- **Digest 共用邏輯 Consolidation（階段 3）**：deep dedupe、orphan 分組等 helper 收斂至 `digest.ts`；`digest-snapshot.ts` 精簡為 snapshot 合併 + 組裝。
- **死碼清理（階段 2）**：移除 `sources/ir_scraper.py`、dashboard 未用 digest/earnings 函式與 re-export；補列 `server-only` 依賴。
- **Dashboard 今日 digest 多輪合併**：首頁與 `GET /api/v1/digest/today` 合併當日所有 `tech_pulse_digests` snapshot，並納入未進 snapshot 的已 delivery 文章（不再只顯示最新一輪精選）。
- **Dashboard UI/UX 設計審查（Slice A–E）**：`InstantCard` 新增 `list` variant（Today 主題區／持倉新聞列表密度）；`ConfidenceBadge` 僅 warn/bad 顯示；移除 ticker emoji；繁中 kicker/CTA（深度洞見、主題、阅读原文）；Today/Invest/HoldingNews 空狀態人性化；`MobileMasthead` 兩行結構 + a11y 小修。
- **Dashboard 今日主題區**：`ThemeSection` 改以 `InstantCard` 渲染（傳入 `authenticated`）；`InstantCard` footer 接回 `ConfidenceBadge`；保留 `NewsTakeawayBlock`。
- **Portfolio dense UX**：Stat 數字防溢出；「配置漂移」改「目標配置偏差」表格 + 主題中文標籤。
- **`scripts/backfill_earnings.py`**：存檔前附加 `investment_signal`（與 production earnings pipeline 一致）。
- **`.env.example`**：`NEWS_TAKEAWAY_MODE` / `NEWS_TAKEAWAY_*`；`FRED_API_KEY`、`FRED_CACHE_TTL_SEC`、`SUPPLY_CHAIN_CACHE_TTL_SEC`（Phase 6 宏觀／供應鏈快取）。

### Fixed
- **Dashboard 導覽搜尋命中率**：`search-firestore.ts` 在 token／ticker／標題前綴仍不足時，以最近 400 篇 in-memory fallback（`search-text-match.ts`：子字串 + 即時 token 比對）；`search_tokens_for_payload` 的 `extra_texts` 擴至 `zh_summary`／`summary`／`zh_body[:500]`，讓標題中段與摘要關鍵字可索引；vitest／pytest 補覆蓋。
- **Pyright CI**：`state_store._cosine_similarity` 改以 `importlib` 載入可選 `numpy`，避免 CI 未安裝 numpy 時 `reportMissingImports` 失敗。
- **SEC XBRL accession strict（D1）**：`SecXbrlFetcher` 在 accession 無匹配 XBRL 列時回傳 `None`，不再 fallback 最新季（backfill / live 一致）。
- **SEC submissions archive（D2）**：`list_filings_in_range` 依 `filings.files[]` 拉 archive 分頁，支援超出 `recent` 窗口的 backfill。
- **`backfill_earnings.py`**：`--since` 晚於 `--until` 拒絕；skip 原因分類計數（no_xbrl / date / duplicate）。
- **Dashboard Today fallback（階段 4）**：共用 `loadTodayDigestData()`；stale 時跳過今日 snapshot、顯示「Latest Pulse」與繁中提示；Firestore 失敗降級；首頁 `totalShown === 0` 邊界；`/api/revalidate` timing-safe token；`FIREBASE_SERVICE_ACCOUNT_JSON` 無效 JSON 明確錯誤；今日 items/snapshot 上限 100/48。
- **CI**：新增 `dashboard` job（typecheck、vitest、production build）。
- **Pipeline dead code**：移除 `crew.py` 未使用的 `IRScraper` 與 `_archive_delivered_earnings`。
- **News takeaway production**：Gemini Flash 明確 `thinking_budget=0`，避免 JSON 被 thinking 截斷；解析失敗重試 + 預設 `NEWS_TAKEAWAY_MAX_OUTPUT_TOKENS=1024`。
- **Apify deep scrape**：REST actor 路徑 `owner/name` → `owner~name`；`APIFY_API_KEY` `.strip()` 避免 Secret 尾端換行 401。
- **Phase 1 trend pipeline**：Phase 3 merge 遺失 `build_report_from_filing` 內 `build_earnings_trend` 掛載；已恢復（與 `fc10e03` 一致）。

### Docs
- **可啟用清單**：[`docs/ENABLEMENT_CHECKLIST.md`](docs/ENABLEMENT_CHECKLIST.md) 集中列出 shadow / 預設 off 旗標（語義去重 shadow→drop、prefilter、Finnhub / FMP vendor、news takeaway）的現況、啟用前置、風險、回滾與建議節奏，並標注排程（C1）已上線、勿開第二條觸發路徑；README 加指標連結。
- `README.md` 同步近期演進：排程（C1，`docs/SCHEDULED_RUNS.md` 兩路徑擇一、`PIPELINE_SCHEDULE_ENABLED`）、語義去重 shadow rollout（A7，`SEMANTIC_DUP_SHADOW_LOG`、`docs/SEMANTIC_DEDUP_ROLLOUT.md`）、per-type 評分閾值（A5，`SCORE_THRESHOLD` / `SCORE_THRESHOLD_<TYPE>`）、vendor 啟用 runbook（C3，`docs/VENDOR_ENABLEMENT.md` + 雙 enrich 指標）、Firestore 索引部署腳本（D4，`scripts/deploy_firestore_indexes.sh`）。
- `README.md`、`TODOS.md`、`dashboard/README.md` 同步 Dashboard 六階段審查（共用模組、驗證指令、a11y follow-up）。
- `README.md`、`TODOS.md`、`dashboard/README.md` 同步財報深度報告 v3（Finnhub、六段報告、待辦）。
- `CHANGELOG.md`、`TODOS.md` 同步 Phase 4–6（訊號、回測、宏觀）。
- [`docs/LOCAL_DEV_SETUP.md`](docs/LOCAL_DEV_SETUP.md) — 本機指令：`main.py`、`backfill_zh_fields.py`、Dashboard、`setup_dashboard_sa.sh`、驗證清單。

## [0.2.1] — 2026-05-22

### Added
- **財報深度報告 v3（完整）**：Finnhub 共識/日曆/股價/逐字稿；`scorecard_builder`（GAAP vs Non-GAAP 對齊，Mixed 不計 surprise）；六段 Markdown `rendered_markdown_zh`（Scorecard、指引/CapEx、分部、電話會議、財務體質、牛熊結論）。
- **Pipeline agents**：`guidance_extractor`、`segment_extractor`、`financial_health_builder`、`transcript_agent`、`conclusion_agent`、`earnings_v3_enrich`。
- **Dashboard 財報**：`/earnings/report/[reportId]`、首頁「今日財報」、`/earnings` 深度報告連結、同 Tier 橫向比較；`GET /api/v1/earnings/ai-infra`；Firestore v2→v3 adapter。
- **財報雷達 S3–S7**：`EarningsNarrativeExtractor` + `EarningsAnalyzer`；`earnings_fact_guard` v2；Telegram `format_earnings_v2`；`VendorEarningsProvider`（預設 `EARNINGS_VENDOR_MODE=off`）；`pipeline_run_summary` earnings 指標；[`docs/EARNINGS_PORTAL.md`](docs/EARNINGS_PORTAL.md)、[`docs/EARNINGS_API_EVALUATION.md`](docs/EARNINGS_API_EVALUATION.md)。
- **財報 API（S6）**：`GET /api/v1/earnings/calendar`、`GET /api/v1/earnings/report/{reportId}`。
- **財報雷達（首期）**：SEC XBRL 主數字、`config/earnings_watchlist.yaml`、`tech_pulse_earnings_reports`、Dashboard [`/earnings`](/earnings) 與 `GET /api/v1/earnings`。
- **部署設定清單**：[`docs/DEPLOY_CHECKLIST.md`](docs/DEPLOY_CHECKLIST.md) — Vercel / GCP Production / Staging / 驗證與 backfill 步驟。
- **Staging 語意 prefilter**：`TECH_PULSE_ENV=staging` 自動啟用語意去重；`pipeline_run_summary` 新增 `semantic_prefilter_dropped` / `newsapi_fetched`；見 [`docs/STAGING.md`](docs/STAGING.md)。
- **NewsAPI 取料**：`sources/newsapi_fetcher.py` 在設定 `NEWSAPI_KEY` 時併入 RSS 流程。
- **Digest 快照**：`scoring/digest_store.py` 寫入 `tech_pulse_digests`；Dashboard `resolveDigestView()` 優先採用快照。
- **繁中 backfill**：[`scripts/backfill_zh_fields.py`](scripts/backfill_zh_fields.py) + [`llm/zh_backfill.py`](llm/zh_backfill.py)（Flash 輕量 JSON，只寫 `zh_title` / `zh_summary` / `hook`）；[`scripts/local_post_deploy_verify.sh`](scripts/local_post_deploy_verify.sh) 一鍵驗證 API、revalidate、backfill。
- **開發流程**：[`docs/WORKFLOW.md`](docs/WORKFLOW.md) 與 [`.cursor/rules/workflow.mdc`](.cursor/rules/workflow.mdc) — 段落完成直接 push `main` 並同步 CHANGELOG/TODOS；pipeline 路徑改動須先經維護者確認。
- **Heuristic edge tests**：[`tests/test_heuristic_filter.py`](tests/test_heuristic_filter.py) 覆蓋主題白名單、促銷/學術/薄稿、複合品質閘與歧義詞誤命中（`arm`/`sol`/`near`/`agent`）。

### Changed
- **財報 pipeline**：watchlist 路徑改為 XBRL → narrative → analyzer → fact_guard v2；Telegram 送 `EarningsReport`（v2 版型）；`scripts/backfill_earnings.py --with-llm` 同步新路徑。
- **Heuristic prefilter**（[`scoring/heuristic_filter.py`](scoring/heuristic_filter.py)）：主題命中後須有 `depth_markers` 或具體數字才進 Gemini；`reason` 新增 `gate:needs_depth_or_specifics`；收緊易誤命中詞彙。
- **Dashboard Archive**：`displayTitle()` 在 `zh_title` 過短或等同 `entity` 時改顯示英文 `title`；歸檔列表精簡 kicker（快訊不再每行 `Dispatch`）、有 `zh_summary` 時顯示副標一行。
- **Dashboard 首頁／內文**：`displayTitle()` 在缺 `zh_title` 時改以 `zh_summary` 首句作中文標題；內文頁固定呈現「中文標題／中文摘要／英文摘要」；「今日熱門代號」可點擊並以 `/archive?ticker=` 篩選相關文章。
- **繁中標題資料鏈**：extractor／`memory_store` 在缺 `zh_title` 時從 `zh_summary`／`zh_body`／`hook` 自動衍生；dashboard 讀取 `hook` 並僅在含漢字時採用繁中 fallback（避免英文 fallback 誤當標題）。
- **Dashboard REST `/api/v1`**：`items`、`items/{id}`、`digest/today`、`tickers`、`archive/facets`、`health`；`API_READ_TOKEN` Bearer 授權。
- **Social trending 接線**：Apify 熱門 hashtag 提升 `lexicon_score`（`SOCIAL_TRENDING_LEXICON_BOOST`），影響 Flash 打分候選排序。
- **財報 Telegram**：`schema_version=earnings_v3` 時送精簡 Scorecard + 結論摘要；超長自動 chunk。
- **ISR**：pipeline revalidate 預設路徑含 `/earnings`。
- **Dashboard 排版**：UI 字級（`text-kicker` / `text-meta`）加大；dark mode 主文字與次要色提亮。

### Fixed
- **財報 memory**：`archive_earnings_report` 實作誤放在 `MemoryService` Protocol，導致 `backfill_earnings` 與 production pipeline 寫入 memory 時 `AttributeError`；已移至 `FirestoreMemoryService`。
- **Dashboard 財報 API**：`/api/v1/earnings/report/[reportId]` 動態 route 改為與 `items/[id]` 相同 auth 模式（修正 Vercel build）。
- **Dashboard `/earnings/[ticker]`**：依 ticker 篩選時不再使用需複合索引的 `where + orderBy` 查詢；`metricBadge` 略過非數值指標。

### Added (ops / backfill)
- **Backfill**：先批次讀取 Firestore（避免 stream 逾時）；覆寫缺 CJK 的 `zh_*`；Pro 全量 extractor 改為 Flash zh-only，避免 JSON 截斷導致 `updated=0`。

### Ops
- **Production 維運**：Vercel `REVALIDATE_TOKEN` 與 Cloud Run `DASHBOARD_REVALIDATE_*` 對齊。
- **財報雷達資料**：`backfill_earnings`（2026-04-01〜05-21）寫入 production `tech_pulse_earnings_reports`（watchlist 19 筆 XBRL 報告）；Dashboard `/earnings` 不再空列表。

## [0.2.0] — 2026-05-19

### Added
- **Dashboard** (`dashboard/`): Next.js 15 web reader for `tech_pulse_memory_items` — Today (`/`)、Archive (`/archive`)、item detail (`/item/[id]`). Editorial layout (paper / serif / kicker), bilingual cards, facet sidebar, manual light/dark/system theme. TypeScript port of digest grouping in `lib/digest.ts` (theme tables, score badges, deep↔instant dedupe) aligned with `delivery/message_formatter.py`.
- **Public read mode**: `DASHBOARD_PUBLIC_READ` exposes title + `zh_summary` (or truncated English) to anonymous visitors; full `zh_body` behind `/login` + signed cookie (`DASHBOARD_SESSION_SECRET`). SEO via `sitemap.xml` / `robots.txt` without leaking full `summary` in HTML. See [`dashboard/README.md`](dashboard/README.md).
- **Pipeline → Dashboard ISR**: `delivery/revalidate.py` POSTs to `/api/revalidate` after delivery when `DASHBOARD_REVALIDATE_URL` + `DASHBOARD_REVALIDATE_TOKEN` are set; `scripts/setup_dashboard_sa.sh` provisions a read-only Firestore SA for Vercel.
- **繁中欄位**: Pipeline writes additive `zh_summary` / `zh_body` on memory archive; dashboard and Portal contract document the fields ([`docs/PORTAL_CONTRACT.md`](docs/PORTAL_CONTRACT.md)).
- **RSS sources**: Additional feeds in `sources/source_registry.yaml`; KOL registry tweaks.
- **Tests**: `test_dashboard_revalidate.py`, `test_zh_field_handling.py`, `test_extractor_quality_gate.py`, `test_regression_lenny_misclassification.py`, expanded formatter/smoke coverage for HTML digests.

### Changed
- **Telegram delivery**: Digest and deep cards use **`parse_mode=HTML`** (was MarkdownV2). `message_formatter.py` escapes dynamic text; `zh_summary` surfaces as card lead where present.
- **Digest formatter (v1)**: De-dupe deep insights from instant theme sections; softer score/confidence badges; cleaner meta lines (aligned with dashboard display).
- **Heuristic prefilter**: Topic whitelist — articles must hit at least one of AI / semiconductor / crypto term clusters before Gemini scoring (`scoring/heuristic_filter.py`).
- **Chinese quality**: Softer extractor gate for zh fields; drop mechanical `zh_body` from English-summary fallback (dashboard falls back to English `summary` when `zh_body` empty).
- **Web reader UX**: Scores hidden on public dashboard cards; standalone login route; `/api/revalidate` excluded from Basic Auth middleware.

### Fixed
- **Empty digest**: Fallback path when instant pool is thin after scoring/dedup.
- **KOL theme guard**: Reject deep briefs outside allowed theme set (`test_kol_allowed_themes.py`).
- **Dashboard auth**: Non-ASCII removed from `WWW-Authenticate` realm; logout route restores `Request` param for redirect URL.
- **Extractor tests**: Prompt null-assertion wording aligned with current extractor instructions.

## [0.1.4] — 2026-05-09

### Fixed
- **Digest header clock**: `📡 科技脈搏 · …` / v2 header times use **`DIGEST_HEADER_TIMEZONE`** (default `Asia/Taipei`) instead of formatting UTC as if it were local wall clock.

### Changed
- **`MAX_UNSCORED_TAIL`**: Scorer default matches Telegram formatter (`3`, was `1`) so ops expectations align when scoring fails for multiple articles.
- **Minimum digest padding**: `_ensure_minimum_summaries` pulls fallback headlines from the merged instant pool **and** full `scored_articles` when the instant shortlist is too thin (still skips URLs already extracted).

## [0.1.3] — 2026-05-09

### Fixed
- **Telegram `📈 市場含義` vs 開頭敘事**：`SynthesizerAgent.build_market_takeaway` 優先使用 narrative **第二段**（並以句號／問號等做句子邊界截斷），避免與第一段 `narrative_excerpt` 重複或在字元 180 處硬切；單段 narrative 時改為用主題名串接。`message_formatter` 若偵測 `market_takeaway` 為 `narrative_excerpt` 前綴則略過「市場含義」區塊，雙重避免重複。

### Changed
- **`DIGEST_FORMAT`**: Module constants `CANONICAL_DIGEST_FORMAT` / `EXPERIMENTAL_DIGEST_FORMAT`; unrecognized values fall back to v1 at runtime. `scripts/preflight.py` warns on `v2` or unknown layout and prepends repo root to `sys.path` so `python scripts/preflight.py` runs from project root. README + regression tests for v1 fallback / v2 opt-in. Docker image defaults `ENV DIGEST_FORMAT=v1`; CI deploy passes `--update-env-vars DIGEST_FORMAT=v1` to Cloud Run Job.
- **Digest synthesis gate**: Default `ITEM_DIGEST_THEME_MIN_SUMMARIES` is **2** (was 3). Runs with only two extracted summaries still produce headline / themes / narrative; thin RSS windows no longer drop straight to “items-only” Telegram. Set env to `3` if you prefer to skip synthesis unless there are three items. Observability: log line when synthesis is skipped (`Skipping digest synthesis: …`).
- **`pipeline_run_summary`**: Includes RSS/scoring funnel (`articles_fetched`, `articles_after_dedup`, `articles_after_scoring`, `instant_candidates`) so empty runs are obvious in one JSON log line.
- **Telegram**: Items digest increments `delivery_attempted` only when there is deliverable content (`_has_deliverable_item_signal`). Skipped sends log `Telegram items digest skipped: nothing deliverable…` instead of misleading `attempted=1 succeeded=0` with no message.
- **Firestore**: Queries use `FieldFilter` (`filter=` keyword) to silence `google-cloud-firestore` deprecation warnings on Cloud Run.
- **EDGAR earnings RSS**: Strip BOM / whitespace before XML parse; on `ParseError` log response length and a short safe head for debugging (empty body, HTML error pages, etc.).

## [2026-05-06]

### Fixed
- **Gemini JSON robustness**: Strip prose preamble (e.g. “Here is the JSON…”) and markdown ``json`` code fences before parsing; wider parse-error log (`raw_head`). Flash scoring omits thinking by default (`GEMINI_DISABLE_THINKING_FOR_FLASH`) to preserve JSON output budget.
- **Scorer**: Default Flash output tokens 512 / retry 1024; compact retry prompt; on parse failure attach full raw text (`GeminiJsonParseError`) and regex-recover `relevance`/`novelty`/`depth`/`score` when truncated (`SCORE_FLASH_OUTPUT_TOKENS`, `SCORE_FLASH_RETRY_OUTPUT_TOKENS`).
- **Reviewer**: Higher default `REVIEWER_MAX_OUTPUT_TOKENS` (1024); regex recovery of `fact_error` / `inferred` / `needs_retry` / `review_comment` when Gemini JSON is truncated mid-field (parse errors still logged from `gemini_client`).
- **RSS / Atom feeds**: Sanitize XML before parse — strip illegal control characters and escape bare `&` outside CDATA (common broken WordPress feeds); retry parse after sanitization.

### Changed
- **Digest content richness**: Lower default synthesis gate (`ITEM_DIGEST_THEME_MIN_SUMMARIES` → `3`) so headline / themes / narrative run more often; raise Telegram per-item body budget (`MAX_SUMMARY_CHARS` → `340`).
- **Extractor**: Configurable article slice (`EXTRACTOR_MAX_INPUT_CHARS`, default `6000`); prompt requires at least one verifiable anchor in `what_happened` or `confidence=low`; structured `extraction_metrics` logs.
- **Reviewer**: If `what_happened` is shorter than `MIN_WHAT_HAPPENED_CHARS` (default `45`), trigger one grounded extraction retry (same budget as LLM `needs_retry`); `ReviewerOutput.extract_retry_used`; `summary_metrics` logs.
- **Docs**: README / `.env.example` document new tuning knobs; consolidate duplicate boilerplate in `AGENTS.md` / `CLAUDE.md`.

### Added
- `tests/test_reviewer_thin_retry.py` for thin-fact retry behavior.
- `tests/test_reviewer_partial_json.py`, `tests/test_scorer_partial_json.py`, `tests/test_rss_feed_sanitize.py` for truncated JSON recovery and feed sanitization.
- **Digest readability & observability**: Sentence-boundary `narrative_excerpt` (env `NARRATIVE_EXCERPT_MAX_CHARS`); synthesizer prompt + `build_market_takeaway` dedupe vs headline (`difflib.SequenceMatcher`); optional Apify full-page Top-K before extraction (`EXTRACTOR_FULLTEXT_TOP_K`, `EXTRACTOR_FULLTEXT_MIN_WORDS`, `EXTRACTOR_FULLTEXT_TIMEOUT_SECONDS`); structured `pipeline_run_summary` JSON log at end of `crew.run`.
- `tests/test_narrative_excerpt.py`, `tests/test_synthesizer_takeaway.py`.

## [2026-05-02]

### Fixed
- **Smart Telegram message chunking at theme boundaries**: Messages exceeding 4096 characters are now intelligently split at newline (theme) boundaries instead of hard character limits. This prevents formatting corruption and broken escape sequences under HTML `parse_mode`. Added:
  - `_smart_chunk_text()`: Splits text at theme boundaries when possible, falls back to character splitting only for oversized single lines
  - `_validate_markdown_boundaries()`: Validates chunk boundaries (legacy name; used for HTML escape integrity)
  - `TELEGRAM_CHUNK_DELAY_MS`: Configurable inter-message delay to prevent rate limiting (default 500ms)
  - Comprehensive test suite (`tests/test_telegram_chunking.py`) with 15 tests covering chunking logic and edge cases

## [2026-04-25]

### Added
- **Pre-extraction semantic deduplication**: New `is_semantically_duplicate()` method in state store detects same-batch near-duplicates before expensive extractor calls
  - SQLite and Firestore backends support 7-day embedding window with configurable cosine similarity threshold (default 0.85)
  - Reduces redundant summaries when multiple KOL sources cover the same technical story
  - Controlled by `SEMANTIC_PREFILTER_ENABLED` flag (default disabled for conservative rollout)

### Changed
- Tightened digest quality with memory context gating and unscored article tail cap
- Normalize OpenCC Taiwan terms for consistent Traditional Chinese output

## [2026-04-20]

### Added
- **Deep insight zh-TW enforcement**: All deep insight briefs now produce 100-200 character Traditional Chinese output with structured sections (Insight / Tech Rationale / Implication)
- Chinese-focused insight upgrade with localization improvements

## [2026-04-15]

### Fixed
- Skip fallback-only digests when extracted items are insufficient

## Earlier Releases

See git log for full history of scoring refinements, Gemini agent patterns, and state backend improvements.
