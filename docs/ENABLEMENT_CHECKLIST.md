# 可啟用清單（Enablement Checklist）

最近多數功能以 **additive / shadow / 預設 off** 上線，對外行為刻意不變——好處是安全，代價是「看不到進步」。本清單把目前所有**尚未推上的電閘**集中列出，逐一標注：現況、作用、啟用前置條件、風險、回滾。詳細操作仍以各自 runbook 為準。

> 重點：這些旗標多在 **module import 時讀取**，改 GHA secrets / `.env` 後下一輪 `schedule.yml` 才生效。

## 已啟用基準（baseline，無須動作）

| 旗標 | 預設 | 作用 |
|------|------|------|
| `TRANSLATION_AGENT_ENABLED` | `1` | extractor 缺 CJK 時 Flash 補繁中標題／摘要 |
| `MEMORY_ENABLED` | `1` | archive 摘要 embedding，供檢索與去重 |
| `EARNINGS_REPORTS_ENABLED` | `1` | 寫 `dashboard/data/earnings/` |
| `DIGEST_SNAPSHOT_ENABLED` | `1` | 寫 `dashboard/data/digests.json` |

## 已完成

### ✅ 自動排程（C1）— 改走 GitHub Actions
- **現況**：`.github/workflows/schedule.yml`（`20 23 * * *` UTC = 07:20 Asia/Taipei）直接跑 `python main.py` 並 commit JSON。
- **啟用**：設 `vars.PIPELINE_SCHEDULE_ENABLED=true`；手動 `workflow_dispatch` 不受限。
- **回滾 / 停跑**：把 `PIPELINE_SCHEDULE_ENABLED` 設回非 `true`。手動 `workflow_dispatch` 仍可跑。
- **Runbook**：[`SCHEDULED_RUNS.md`](SCHEDULED_RUNS.md)。來源清單見 [`SOURCES.md`](SOURCES.md)。

## 待啟用（依建議順序，由「高體感低風險」到「需成本決策」）

### 1. 語義去重 shadow log — `SEMANTIC_DUP_SHADOW_LOG`（A7）— 先開這個收資料
- **現況**：**`1`，已啟用（2026-06-14，首班生效 06-15）**。觀測窗起算，~06-22 評估。
- **作用**：逐筆 log「若開啟會丟哪一篇、distance 多少」。**它是第 2 步的前置觀測，不改任何去重決策。**
- **前置**：`MEMORY_ENABLED=1`、sqlite embeddings 已累積（建議 ≥ 7 天）。
- **風險**：幾乎為零（僅增加 log 量）。
- **回滾**：設 `0`。
- **Runbook**：[`SEMANTIC_DEDUP_ROLLOUT.md`](SEMANTIC_DEDUP_ROLLOUT.md) §2

### 2. 語義去重翻旗 — `SEMANTIC_DUP_DROP_ENABLED`（A7）— shadow 最成熟
- **現況**：`0`（只 archive＋觀測，不丟）。
- **作用**：真的丟棄跨 run 近重複（`distance <= SEMANTIC_DUP_DISTANCE_THRESHOLD`，預設 0.12）。
- **前置**（runbook §3，**全部成立**才翻）：
  - [ ] `semantic_dup_checked` 穩定 > 0（sqlite embeddings 有資料）
  - [ ] `would_drop / checked` 落在預期區間（建議 **< 15%**；過高代表 threshold 太鬆）
  - [ ] 抽查 shadow log 的 would-drop 配對確實是重複，無誤判
- **風險**：誤判 → 把實為不同的新聞當重複丟掉。
- **回滾**：設 `0` 立即停丟（gate 永久保留）；誤判偏高則調高 `SEMANTIC_DUP_DISTANCE_THRESHOLD`（更嚴）後重回 shadow。
- **Runbook**：[`SEMANTIC_DEDUP_ROLLOUT.md`](SEMANTIC_DEDUP_ROLLOUT.md) §4

### 3. 預抽取語義去重 — `SEMANTIC_PREFILTER_ENABLED`
- **現況**：未設 / `0`。
- **作用**：抽取前對同批近重複先去重（`SEMANTIC_PREFILTER_THRESHOLD`，預設 0.85），省 extractor 呼叫成本。
- **前置**：建議先確認第 2 步行為穩定，避免兩層去重交互難判讀。
- **風險**：在抽取前丟棄，較早介入；threshold 太低會誤併不同題材。
- **回滾**：設 `0`。

### 4. 財報 vendor — `EARNINGS_VENDOR_MODE`（C3，Finnhub）
- **現況**：**`off`（程式與 GHA 預設）**。`schedule.yml` 可注入 `FINNHUB_API_KEY`，**有 key 不代表已開**。舊 Cloud Run 曾設 `free`，已過期。
- **作用**：Finnhub 共識／日曆／股價／逐字稿 enrich 財報（不覆寫 SEC headline）。
- **啟用**：在 `schedule.yml` 設 `EARNINGS_VENDOR_MODE=free`（pipeline，需維護者批准）且 secret 有 `FINNHUB_API_KEY`。
- **注意**：只在**財報日**開火；無 watchlist filing 的日子 `earnings_vendor_enriched_count = 0` 屬正常。
- **回滾**：設回 `off` 或不設。**Runbook**：[`VENDOR_ENABLEMENT.md`](VENDOR_ENABLEMENT.md)。來源見 [`SOURCES.md`](SOURCES.md)。

### 5. 財報基本面 enrich — `EARNINGS_FUNDAMENTAL_MODE`（C3，FMP）
- **現況**：**`off`（程式與 GHA 預設）**。有 `FMP_API_KEY` 不代表已開。
- **作用**：FMP 比率／現金流補 SEC 缺口（FCF、ROIC 等），標 SEC vs FMP `source_conflicts`。
- **啟用**：`EARNINGS_FUNDAMENTAL_MODE=free` + `FMP_API_KEY`（需批准）。
- **驗證**：`pipeline_run_summary.earnings_fundamental_enriched_count`（財報日才 > 0）。
- **回滾**：設回 `off`。

### 6. News takeaway — `NEWS_TAKEAWAY_MODE`
- **現況**：**`off`（程式預設；GHA 未覆寫）**。舊文件寫 production `on`，與現況不符。
- **作用**：每篇新聞加一段 Flash 生成的 takeaway，Dashboard `NewsTakeawayBlock` 呈現。
- **啟用**：設 `on`。**回滾**：設 `off` 或不設。

### 7. NewsAPI 補充 — `NEWSAPI_ENABLED`
- **現況**：**`0`（程式與 GHA 預設）**。有 `NEWSAPI_KEY` 不代表已開。
- **作用**：科技 `top-headlines` 併入 RSS。主源已是 RSS／KOL，預設關以減噪與配額。
- **啟用**：`NEWSAPI_ENABLED=1` + key。**回滾**：設 `0`。見 [`SOURCES.md`](SOURCES.md)。

### 8. 社群趨勢 — `SOCIAL_TRENDING_ENABLED`
- **現況**：**`0`（程式與 GHA 預設）**。`APIFY_API_KEY` 仍可供 deep 全文。
- **作用**：X／Threads hashtag 當評分訊號，不進正文。
- **啟用**：`SOCIAL_TRENDING_ENABLED=1` + Apify key。**回滾**：設 `0`。

## 建議節奏

排程（C1）可手動跑；自動排程由 `PIPELINE_SCHEDULE_ENABLED` 控制。vendor（Finnhub）、FMP、news takeaway **預設關閉**。

1. **第 1 → 2 步**：shadow log 已於 2026-06-14 開啟；embeddings 改 OpenAI 後語意去重是冷啟動，達門檻再翻 `SEMANTIC_DUP_DROP_ENABLED`。
2. **第 3 步**（prefilter）排在第 2 步行為穩定之後。
3. **vendor / FMP / takeaway / NewsAPI / trending**：維持關；要開再翻旗標。見 [`SOURCES.md`](SOURCES.md)。
