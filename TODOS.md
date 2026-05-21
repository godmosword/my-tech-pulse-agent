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

## 進行中 / 下一步
- [x] **`.env.example`**：補上 `DASHBOARD_REVALIDATE_URL` / `DASHBOARD_REVALIDATE_TOKEN` / `DASHBOARD_REVALIDATE_TIMEOUT` 說明（pipeline 端）
- [ ] **合約 `themes[]`**：pipeline 仍以 `category` 單值為主；若 Portal 需要陣列，additive 寫入 `themes` 並更新合約
- [ ] **歸檔舊稿繁中**（可選）：`python scripts/backfill_zh_fields.py --limit 30 --max-updates 20` 補更早的 `memory_items`

## 財報萃取與分析 Roadmap

目標：把現有 `SEC EDGAR RSS → earnings_fetcher → earnings_agent → structured earnings JSON → Telegram + investment-digest` 子流程，升級成「官方結構化數字 + 財報文字敘事 + 精緻投資解讀」的財報雷達。

### P0 — 官方資料源優先：SEC XBRL structured facts

- [ ] 新增 `sources/sec_xbrl_fetcher.py`
  - `get_company_submissions(cik)`：讀 `data.sec.gov/submissions/CIK##########.json`
  - `get_company_facts(cik)`：讀 `data.sec.gov/api/xbrl/companyfacts/CIK##########.json`
  - `get_company_concept(cik, taxonomy, tag)`：讀 `data.sec.gov/api/xbrl/companyconcept/...`
  - `normalize_latest_quarter_facts(...)`：依 fiscal period / filed date / accession number 找最新季度數字
- [ ] 新增 `sources/sec_concept_map.py`
  - Revenue：`us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax`、`us-gaap:Revenues`
  - EPS：`us-gaap:EarningsPerShareDiluted`、`us-gaap:EarningsPerShareBasic`
  - Net income：`us-gaap:NetIncomeLoss`
  - Gross profit / margin：`us-gaap:GrossProfit`
  - Operating income：`us-gaap:OperatingIncomeLoss`
  - Capex / cash flow：`us-gaap:PaymentsToAcquirePropertyPlantAndEquipment`、`us-gaap:NetCashProvidedByUsedInOperatingActivities`
- [ ] 更新 `sources/earnings_fetcher.py`
  - 保留目前 SEC RSS / Atom feed 觸發邏輯
  - 觸發後先用 CIK / ticker 查 structured XBRL facts
  - filing raw text 改作「quote / guidance wording / management tone」來源，不再作為主要數字來源
- [ ] 強化 SEC request hygiene
  - 將 `SEC_HEADERS["User-Agent"]` 改為正式專案名 + 可聯絡 email
  - 加入 rate limit / retry / backoff / cache，避免頻繁打 SEC API

### P1 — 財報資料模型升級

- [ ] 將 `agents/earnings_agent.py` 的 `EarningsOutput` 擴充為 `EarningsReport` / `EarningsFact` 分層模型
  - `EarningsFact`: `metric`, `label_zh`, `value`, `unit`, `period`, `fiscal_year`, `fiscal_period`, `form_type`, `source_type`, `source_url`, `source_tag`, `confidence`
  - `EarningsReport`: `company`, `ticker`, `cik`, `quarter`, `filed_at`, `fiscal_period_end`, `headline_metrics`, `segment_metrics`, `guidance`, `estimates`, `surprise`, `key_quotes`, `management_tone`, `ai_infra_relevance`, `investment_takeaway`, `risk_flags`, `source_documents`, `confidence`
- [ ] `fact_guard` 改成 source-aware 驗證
  - SEC XBRL facts：以 `source_tag + accession + period` 驗證
  - vendor estimates：以 `vendor_name + as_of_date` 驗證
  - filing quotes：以原文 substring 驗證
  - LLM 不得計算、推導、改寫 numeric facts；只可解釋已驗證欄位
- [ ] 新增 JSON fixture 測試
  - NVDA / AMD / MSFT / GOOGL / MU 等科技股範例
  - 測試 revenue / EPS / segment / guidance 缺值時的 graceful degradation

### P2 — 免費 API 先接：FMP + Finnhub free-tier vendor enrichment

原則：SEC 官方 API 作為免費、可信的主數字來源；FMP / Finnhub 免費額度只補 SEC 沒有或不容易取得的資料，例如 analyst consensus、earnings surprise、calendar、transcript、歷史 financial ratios、segment-friendly normalized financials。所有 vendor 資料都必須可關閉、可 fallback、可追蹤用量，不可影響 SEC-only 財報主流程。

- [ ] 建立 `docs/EARNINGS_API_EVALUATION.md`
  - 比較欄位：資料覆蓋、更新速度、EPS / revenue estimates、earnings calendar、transcripts、financial statements、ratios、segment data、API 限額、價格、授權限制、是否允許商用展示
  - 先記錄 free-tier 實測可用 endpoint，再決定是否升級付費
- [ ] 新增 `.env.example` vendor 設定
  - `FMP_API_KEY=`
  - `FINNHUB_API_KEY=`
  - `EARNINGS_VENDOR_MODE=off|free|paid`
  - `EARNINGS_VENDOR_ORDER=fmp,finnhub`
  - `EARNINGS_WATCHLIST=NVDA,AMD,MSFT,GOOGL,AVGO,MU,TSM,AMZN,META,TSLA`
  - `MAX_VENDOR_CALLS_PER_RUN=20`
  - `FMP_DAILY_CALL_BUDGET=200`（保留 buffer；FMP Basic 官方頁面顯示 250 calls/day）
  - `FINNHUB_DAILY_CALL_BUDGET=200`（先以帳號 dashboard 實際額度為準，不在 code 寫死）
- [ ] 設計 vendor abstraction
  - `sources/vendor_earnings_provider.py`
  - 介面：`get_earnings_calendar()`, `get_estimates(ticker)`, `get_transcript(ticker, quarter)`, `get_financials(ticker)`
  - vendor 欄位標記：`source_type="vendor_estimate" | "vendor_financials" | "vendor_transcript"`
  - 回傳 payload 必須附 `vendor_name`, `endpoint`, `as_of_date`, `raw_unit`, `confidence`
- [ ] 新增 FMP free-tier provider
  - `sources/fmp_provider.py`
  - 優先測試：company profile、income statement、key metrics、financial ratios、earnings calendar / analyst estimates（若 free-tier 可用）
  - 若 endpoint 回 403 / plan restricted，標記 `vendor_status="restricted"`，不要讓 pipeline fail
- [ ] 新增 Finnhub free-tier provider
  - `sources/finnhub_provider.py`
  - 優先測試：earnings calendar、earnings estimates、company earnings、company profile、transcripts（若 free-tier 可用）
  - Finnhub 限額與可用 endpoint 以帳號 dashboard / API response 為準；實作時不可硬編免費額度
- [ ] 用量控管與 cache
  - 新增 Firestore collection：`tech_pulse_vendor_api_usage`
  - 每次 vendor call 記錄：`provider`, `endpoint`, `ticker`, `status`, `called_at`, `cache_hit`
  - calendar cache TTL：12 小時
  - estimates cache TTL：24 小時
  - financials cache TTL：7 天
  - transcript cache TTL：永久或 365 天
- [ ] free-tier 執行策略
  - 只對 `EARNINGS_WATCHLIST` 啟用 vendor enrichment
  - 每次 Cloud Run 只處理「本週有財報」或「剛 filing」的 ticker
  - 每個 ticker 最多 2–3 個 vendor endpoint
  - 任何 vendor 失敗都 fallback SEC-only，不加入 `critical_errors`
- [ ] 候選 API：高成本 / 企業級（只列觀察，不接）
  - Intrinio / FactSet / Refinitiv / S&P Capital IQ：若未來要做專業級 consensus、segment、產業比較、歷史估值資料，再評估；現階段先不接，避免成本過早放大

### P3 — LLM 角色調整：從「抽數字」改成「財報分析師」

- [ ] 拆分 `EarningsAgent`
  - `EarningsNarrativeExtractor`：只抽 key quotes、guidance wording、management tone、AI / semiconductor / cloud / memory 相關敘事
  - `EarningsAnalyzer`：根據 verified facts + quotes 產生繁中投資解讀
- [ ] 分析輸出固定包含
  - 一句話結論
  - 核心數字：revenue / EPS / margin / operating income / segment
  - AI 基礎建設關聯：datacenter、GPU、HBM、networking、capex、cloud demand
  - 下季指引與管理層語氣
  - 市場含義：利多、隱憂、供應鏈外溢影響
  - 風險旗標：guidance 下修、margin 壓力、capex 過熱、inventory、China/export control、需求放緩
- [ ] 評分欄位
  - `earnings_quality_score`：營收 / EPS / margin / guidance 綜合
  - `ai_infra_signal`：strong / medium / weak / not_relevant
  - `market_surprise_level`：high / medium / low / unknown

### P4 — Telegram 呈現升級：財報雷達版型

- [ ] 重寫 `delivery/message_formatter.py::format_earnings()`
  - 標題：`💰 財報雷達｜{ticker} {quarter}`
  - 區塊：一句話結論 / 核心數字 / AI 基礎建設重點 / 下季指引 / 市場解讀 / 風險旗標 / 原文依據
  - 數字一律附 `source_type` 或 `source_tag`，避免讀者誤以為是 LLM 推算
- [ ] 根據內容長度支援 chunking
  - 短版：Telegram 單則快訊
  - 長版：intro + metric card + analysis card + source card
- [ ] 新增 formatting tests
  - 高信心完整資料
  - 缺 analyst estimate
  - 缺 EPS
  - 有 quote 但無 guidance
  - vendor API 不可用時仍可顯示 SEC-only 財報

### P5 — Firestore / Dashboard 專用財報資料庫

- [ ] 新增 collection：`tech_pulse_earnings_reports/{ticker}_{fiscal_period}`
  - `ticker`, `company`, `cik`, `quarter`, `filed_at`, `source_documents`
  - `headline_metrics`, `segment_metrics`, `guidance`, `estimates`, `surprise`
  - `one_line_takeaway_zh`, `ai_infra_takeaway_zh`, `investment_takeaway_zh`, `risk_flags`, `key_quotes`
  - `confidence`, `schema_version="earnings_v2"`
- [ ] 保留 `tech_pulse_memory_items` 的 `kind="earnings"`
  - 用於既有 Portal / memory search 相容
  - 但 dashboard 財報頁優先讀 `tech_pulse_earnings_reports`
- [ ] Dashboard 新增頁面
  - `/earnings`：最近財報雷達列表
  - `/earnings/[ticker]`：單一公司財報歷史與 AI infra signal
  - `/api/v1/earnings?limit=20&ticker=NVDA`
  - `/api/v1/earnings/{ticker}/{quarter}`
  - `/api/v1/earnings/calendar?horizon=30d`
  - `/api/v1/earnings/ai-infra`
- [ ] Dashboard UI 卡片
  - revenue / EPS / guidance badge
  - AI infra signal badge
  - surprise / estimate badge（若 vendor 有提供）
  - confidence / source badge
  - 原文 filing / transcript 連結

### P6 — 財報工作流與監控

- [ ] 新增 preflight checks
  - SEC API connectivity
  - ticker → CIK mapping availability
  - vendor API key 是否存在但不強制 required
  - Firestore earnings collection write/read smoke test
- [ ] 新增 pipeline run summary 欄位
  - `earnings_filings_seen`
  - `earnings_xbrl_facts_loaded`
  - `earnings_vendor_calls`
  - `earnings_reports_archived`
  - `earnings_sec_only_count`
  - `earnings_vendor_enriched_count`
- [ ] 新增 failure policy
  - SEC XBRL 失敗：不送高信心財報，只送低信心 filing notice 或跳過
  - vendor API 失敗：fallback SEC-only，不視為 critical error
  - LLM analysis 失敗：仍 archive verified facts，Telegram 可延後送分析

## 積壓（Backlog）

- [ ] **Heuristic 通過率觀測**：上線後從 pipeline 日誌聚合 `gate:needs_depth_or_specifics` 與 dropped 計數，評估是否過嚴
- [x] **Canonical digest snapshot**：pipeline 寫入 `tech_pulse_digests/{id}`；Dashboard 首頁優先讀 snapshot
- [ ] **Semantic prefilter rollout**：staging 已可透過 `TECH_PULSE_ENV=staging` 啟用；觀測 `pipeline_run_summary.semantic_prefilter_dropped` 後再上 production
- [ ] **Semantic dup drop**：`SEMANTIC_DUP_DROP_ENABLED=1` 需 Firestore vector index ready + 觀察誤殺率
- [ ] **Dashboard**：earnings 專欄、全文搜尋、RSS/Atom 對外訂閱
- [ ] **DIGEST_FORMAT v2**：維持 experimental；production 仍鎖 `v1`（CI deploy 預設）

## 維運檢查清單（每次 deploy 後）

完整環境變數與驗證指令見 [`docs/DEPLOY_CHECKLIST.md`](docs/DEPLOY_CHECKLIST.md)。

1. Cloud Run Job 日誌出現 `pipeline_run_summary` 且 `summaries_count` > 0
2. Telegram 頻道收到 HTML  digest（無 raw `&lt;` 洩漏或截斷標籤）
3. 若已設 webhook：Dashboard `/` 與 `/archive` 在送報後數秒內更新
4. `python scripts/preflight.py` 在與 production 相同 env 下通過