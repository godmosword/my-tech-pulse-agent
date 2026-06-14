# 可啟用清單（Enablement Checklist）

最近多數功能以 **additive / shadow / 預設 off** 上線，對外行為刻意不變——好處是安全，代價是「看不到進步」。本清單把目前所有**尚未推上的電閘**集中列出，逐一標注：現況、作用、啟用前置條件、風險、回滾。詳細操作仍以各自 runbook 為準。

> 重點：這些旗標多在 **module import 時讀取**，改 env 後須**重新部署 / 重啟 Cloud Run Job** 才生效。

## 已啟用基準（baseline，無須動作）

| 旗標 | 預設 | 作用 |
|------|------|------|
| `TRANSLATION_AGENT_ENABLED` | `1` | extractor 缺 CJK 時 Flash 補繁中標題／摘要 |
| `MEMORY_ENABLED` | `1` | archive 摘要 embedding，供檢索與去重 |
| `EARNINGS_REPORTS_ENABLED` | `1` | 寫 `tech_pulse_earnings_reports` |
| `DIGEST_SNAPSHOT_ENABLED` | `1` | 寫 `tech_pulse_digests` 快照供 Dashboard |

## 待啟用（依建議順序，由「高體感低風險」到「需成本決策」）

### 1. 自動排程 — `PIPELINE_SCHEDULE_ENABLED`（C1）⭐ 體感最大
- **現況**：GitHub repo variable 未設 → `.github/workflows/schedule.yml` cron 停用，pipeline 不會自己跑。
- **作用**：每天自動執行，不必手動 dispatch。**這是把所有隱形工作變成「每天看得到產出」的關鍵一步。**
- **前置**：兩路徑**擇一**（cron workflow **或** Cloud Scheduler），避免雙跑。確認 WIF / Cloud Run Job 正常。
- **風險**：兩者同開 → 重複執行、重複送 Telegram。`schedule.yml` 已有 concurrency 防同檔重疊，但防不了跨路徑。
- **回滾**：移除 variable 或設 `false`（手動 `workflow_dispatch` 不受限）。
- **Runbook**：[`SCHEDULED_RUNS.md`](SCHEDULED_RUNS.md)

### 2. 語義去重 shadow log — `SEMANTIC_DUP_SHADOW_LOG`（A7）— 先開這個收資料
- **現況**：`0`。
- **作用**：逐筆 log「若開啟會丟哪一篇、distance 多少」。**它是第 3 步的前置觀測，不改任何去重決策。**
- **前置**：索引 READY、`MEMORY_ENABLED=1`、memory 已累積（建議 ≥ 7 天）。
- **風險**：幾乎為零（僅增加 log 量）。
- **回滾**：設 `0`。
- **Runbook**：[`SEMANTIC_DEDUP_ROLLOUT.md`](SEMANTIC_DEDUP_ROLLOUT.md) §2

### 3. 語義去重翻旗 — `SEMANTIC_DUP_DROP_ENABLED`（A7）— shadow 最成熟
- **現況**：`0`（只 archive＋觀測，不丟）。
- **作用**：真的丟棄跨 run 近重複（`distance <= SEMANTIC_DUP_DISTANCE_THRESHOLD`，預設 0.12）。
- **前置**（runbook §3，**全部成立**才翻）：
  - [ ] 索引 READY，期間無 missing-index warning（`semantic_dup_checked` 穩定 > 0）
  - [ ] `would_drop / checked` 落在預期區間（建議 **< 15%**；過高代表 threshold 太鬆）
  - [ ] 抽查 shadow log 的 would-drop 配對確實是重複，無誤判
- **風險**：誤判 → 把實為不同的新聞當重複丟掉。
- **回滾**：設 `0` 立即停丟（gate 永久保留）；誤判偏高則調高 `SEMANTIC_DUP_DISTANCE_THRESHOLD`（更嚴）後重回 shadow。
- **Runbook**：[`SEMANTIC_DEDUP_ROLLOUT.md`](SEMANTIC_DEDUP_ROLLOUT.md) §4

### 4. 預抽取語義去重 — `SEMANTIC_PREFILTER_ENABLED`
- **現況**：未設 / `0`。
- **作用**：抽取前對同批近重複先去重（`SEMANTIC_PREFILTER_THRESHOLD`，預設 0.85），省 extractor 呼叫成本。
- **前置**：建議先確認第 3 步行為穩定，避免兩層去重交互難判讀。
- **風險**：在抽取前丟棄，較早介入；threshold 太低會誤併不同題材。
- **回滾**：設 `0`。

### 5. 財報 vendor 啟用 — `EARNINGS_VENDOR_MODE`（C3，Finnhub）
- **現況**：`off`。`off → free → paid` 分階段。
- **作用**：Finnhub 共識／日曆／股價／逐字稿 enrich 財報。
- **前置**：設 `FINNHUB_API_KEY`；成本決策（free tier 額度）；先 `free` 驗證再考慮 `paid`。
- **驗證**：`pipeline_run_summary.earnings_vendor_enriched_count` > 0 且穩定。
- **風險**：額度耗盡 / 逾時拖慢 run（已有 `MAX_VENDOR_CALLS_PER_RUN`、timeout 上限）。
- **回滾**：設 `off`。
- **Runbook**：[`VENDOR_ENABLEMENT.md`](VENDOR_ENABLEMENT.md)

### 6. 財報基本面 enrich — `EARNINGS_FUNDAMENTAL_MODE`（C3，FMP）
- **現況**：`off`（= SEC-only）。`off → free → paid`。
- **作用**：FMP 比率／現金流補 SEC 缺口（FCF、ROIC 等），標 SEC vs FMP `source_conflicts`。
- **前置**：設 `FMP_API_KEY`；成本決策。
- **驗證**：`pipeline_run_summary.earnings_fundamental_enriched_count` > 0。
- **已知限制**：`MAX_FMP_CALLS_PER_RUN` 因 provider 每筆重建而非全輪硬上限（TODOS follow-up）。
- **回滾**：設 `off`。
- **Runbook**：[`VENDOR_ENABLEMENT.md`](VENDOR_ENABLEMENT.md)

### 7. News takeaway — `NEWS_TAKEAWAY_MODE`
- **現況**：`off`（啟用值為 `on`）。
- **作用**：每篇新聞加一段 Flash 生成的 takeaway，Dashboard `NewsTakeawayBlock` 呈現。
- **前置**：無硬性；確認 Flash 成本可接受。
- **風險**：每篇多一次 Gemini 呼叫；解析失敗已有重試與 `NEWS_TAKEAWAY_MAX_OUTPUT_TOKENS` 防截斷。
- **回滾**：設 `off`。

## 建議節奏

1. **先做第 1 步**（排程）——立刻把「每天自動產出」變成可見事實，與其他旗標無關，風險最低。
2. **第 2 → 3 步**串起來：開 shadow log 收 ≥ 7 天資料，達門檻再翻去重旗。
3. **第 5 / 6 步**等你願意付 vendor 成本時，依 runbook 走 free → go/no-go → paid。
4. 第 4、7 步視成本與觀測結果再決定。
