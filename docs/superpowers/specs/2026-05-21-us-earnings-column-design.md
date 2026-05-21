# 美股 AI 半導體財報專欄 — 設計規格

**狀態**：已核准方向（全方位 D + 廣覆蓋 + 分層 Watchlist）  
**日期**：2026-05-21  
**相關**：[`TODOS.md`](../../../TODOS.md) 財報 Roadmap P0–P6、[`docs/PORTAL_CONTRACT.md`](../../PORTAL_CONTRACT.md)

---

## 1. 目標與成功標準

### 1.1 產品目標

將現有 `SEC EDGAR RSS → earnings_fetcher → earnings_agent → Telegram + memory_items` 升級為：

1. **可信數字**：SEC XBRL 為主、vendor 為輔、LLM 不計算數字  
2. **正確時序**：列表與日曆以 **`published_at`（SEC filed / accepted，UTC）** 排序，不以 pipeline `delivered_at` 或日曆季度代替  
3. **正確季度**：以公司 **fiscal year / fiscal period / period_end** 為 canonical key，不用日曆 Q1–Q4 推斷  
4. **專用呈現**：Telegram 財報雷達、Dashboard `/earnings` 專欄、Firestore `tech_pulse_earnings_reports`  
5. **廣覆蓋 + 可控成本**：EDGAR RSS 廣抓（方案 D），Watchlist 分層優先 enrich / 推播；硬性 per-run 與 daily cap

### 1.2 驗收（整體完成時）

| 檢查項 | 標準 |
|--------|------|
| 時間 | `tech_pulse_earnings_reports` 每筆有 `published_at`；Dashboard 列表 `orderBy published_at DESC` |
| 季度 | doc id = `{ticker}_{fiscal_year}_{fiscal_period}`；Apple/NVIDIA 等 fiscal 年結不同仍唯一 |
| 數字 | `headline_metrics` 來自 XBRL `source_tag`；LLM 分析失敗仍可 archive facts |
| Watchlist | Tier 1–5 公司 Telegram 優先、vendor enrich、Dashboard tier badge |
| 廣覆蓋 | 非 watchlist 的 RSS 命中仍可 ingest（cap 內），不呼叫 vendor |
| 相容 | `memory_items` `kind=earnings` 保留，Portal v1 不 breaking |
| 失敗 | XBRL 失敗 → 不高信心推送；vendor 失敗 → SEC-only，非 critical |

---

## 2. 範圍決策（已確認）

| 決策 | 選擇 |
|------|------|
| 執行策略 | **方案丙**：分階切片 S0–S7（見 §8） |
| 覆蓋範圍 | **D**：所有 EDGAR `type: earnings` RSS 命中皆進 ingest 佇列；**分層 Watchlist** 控制 enrich / Telegram / UI 強調 |
| 時間主鍵 | **`published_at`** = SEC filed（Atom `updated` / submissions `filingDate`） |
| 季度主鍵 | **`(ticker, fiscal_year, fiscal_period)`** + `period_end` |
| Pipeline 變更 | 需 maintainer 核准後 merge `main`（見 [`docs/WORKFLOW.md`](../../WORKFLOW.md)） |

---

## 3. Watchlist：AI 半導體五層（使用者提供）

配置檔建議：`config/earnings_watchlist.yaml`（或 `.env` `EARNINGS_WATCHLIST` + tier 欄位）。

### 3.1 Tier 定義與行為

| Tier | 語意 | Telegram | Vendor enrich | Dashboard |
|------|------|----------|---------------|-----------|
| **1** | 核心必持 | 必推（除非 duplicate） | 是 | 預設篩選、置頂 |
| **2** | 高成長受益 | 是 | 是 | 預設顯示 |
| **3** | RF / 邊緣 / 特殊製程 | 是 | 是 | 顯示 |
| **4** | 新興 AI / 小型設備 | 是 | 選用（budget 內） | 顯示 |
| **5** | 封裝 / 材料 / 互連 | 是 | 選用 | 顯示 |
| **—** | 非 watchlist（RSS 廣抓） | 否（僅 archive） | 否 | 進階篩選「全部 SEC」 |

### 3.2 已命名標的（實作首期必載 CIK map）

**Tier 1 — 核心必持（8）**  
`NVDA`, `TSM`, `AVGO`, `AMD`, `ASML`, `AMAT`, `LRCX`, `KLAC`

**Tier 2 — 高成長受益（已命名 5；目標 10 檔，其餘由 maintainer 補齊）**  
`MRVL`, `MU`, `CDNS`, `SNPS`, `ARM`

**Tier 3 — RF / 邊緣 / 特殊製程（已命名 4；目標 10）**  
`ON`, `WOLF`, `TXN`, `ADI`

**Tier 4 — 新興 AI 推論 / 小型設備（已命名 3；目標 10）**  
`SMCI`, `RMBS`, `ACLS`

**Tier 5 — 先進封裝 / 材料 / 互連（已命名 4；目標 10）**  
`AMKR`, `ASX`, `ENTG`, `NVTS`

> **備註**：Tier 2–5 使用者敘述為各 10 檔，訊息中僅列部分代號。規格要求 YAML 保留 `tier` + `ticker` + `notes_zh`；未列名額度標 `pending: true`，由 maintainer 補齊，**實作不得臆造 ticker**。

### 3.3 ETF（可選、次級）

`SOXX`, `SMH` — **不**走單公司 XBRL 季報流程；若支援則：

- 僅 Dashboard「曝險參考」區塊或連結 holdings 財報彙總（Phase 2+）  
- 首期 **不** 納入 `EARNINGS_WATCHLIST` pipeline 處理

### 3.4 投資組合對照（產品提示，非程式邏輯）

使用者已持倉：`MRVL`, `AVGO`, `TSM`, `MU`, `NVDA`（Tier 1/2 核心覆蓋）；SiC 標的 `ON`, `WOLF` 與產業 insight 重疊 — Dashboard 可選「與 SiC 生態相關」篩選（`tags: ["sic"]` additive）。

---

## 4. 廣覆蓋（D）與資源上限

### 4.1 兩條路徑

```
EDGAR RSS (registry type=earnings)
    → 全部進 candidate queue（rolling 7d window）
    → 去重 accession
    → 若 ticker ∈ watchlist：完整 S1–S5 pipeline + Telegram
    → 否則：僅 XBRL 輕量 ingest + archive（無 vendor、無 Telegram）

Watchlist ticker
    → 優先佇列（Tier 1 最先）
    → vendor calendar 補「本週財報」提醒
```

### 4.2 建議環境變數（cap）

| 變數 | 建議初值 | 說明 |
|------|----------|------|
| `MAX_EARNINGS_FILINGS` | `8` → 分階提高到 `15` | 每 run 完整處理（含 LLM）上限 |
| `MAX_EARNINGS_FILINGS_BROAD` | `30` | 廣覆蓋僅 XBRL + archive 上限 |
| `MAX_SEC_API_CALLS_PER_RUN` | `60` | submissions + companyfacts + concept |
| `MAX_VENDOR_CALLS_PER_RUN` | `20` | 僅 watchlist |
| `EARNINGS_VENDOR_MODE` | `off` → `free` | 有 key 才開 |
| `EARNINGS_TELEGRAM_MIN_TIER` | `1` 或 `2` | 低於此 tier 不推 Telegram（仍 archive） |

SEC [fair access](https://www.sec.gov/os/webmaster-faq#developers)：`User-Agent` 含專案名 + 聯絡 email；全域 rate limit + exponential backoff + 可選 disk cache。

---

## 5. 資料模型 `earnings_v2`

### 5.1 Firestore：`tech_pulse_earnings_reports`

**Document ID**：`{ticker}_{fiscal_year}_{fiscal_period}`  
例：`NVDA_2026_FY2025Q4`

| 欄位 | 型別 | 必填 | 說明 |
|------|------|------|------|
| `report_id` | string | ✅ | 同 doc id |
| `ticker` | string | ✅ | |
| `company` | string | ✅ | |
| `cik` | string | ✅ | 10 位零補齊 |
| `tier` | int \| null | ❌ | 1–5；null = 非 watchlist |
| `fiscal_year` | int | ✅ | 公司 FY |
| `fiscal_period` | string | ✅ | XBRL `fp` 原文 |
| `period_end` | timestamp | ✅ | 會計期間結束 |
| `quarter_label` | string | ✅ | 繁中顯示，含 period_end |
| `published_at` | timestamp | ✅ | **排序主鍵** |
| `filed_at` | timestamp | ✅ | 通常等同 published_at |
| `delivered_at` | timestamp | ❌ | 我方送報 |
| `headline_metrics` | EarningsFact[] | ✅ | revenue, EPS, … |
| `segment_metrics` | EarningsFact[] | ❌ | |
| `guidance` | object | ❌ | |
| `estimates` | object | ❌ | vendor |
| `surprise` | object | ❌ | vendor |
| `key_quotes` | string[] | ❌ | substring fact_guard |
| `management_tone` | string | ❌ | LLM |
| `ai_infra_relevance` | string | ❌ | LLM |
| `investment_takeaway_zh` | string | ❌ | LLM |
| `risk_flags` | string[] | ❌ | LLM |
| `source_documents` | object[] | ✅ | accession, form_type, url |
| `confidence` | enum | ✅ | high / medium / low |
| `schema_version` | string | ✅ | `earnings_v2` |

### 5.2 `EarningsFact`

```json
{
  "metric": "revenue",
  "label_zh": "營收",
  "value": 39300000000,
  "unit": "USD",
  "period": "FY2025Q4",
  "fiscal_year": 2026,
  "fiscal_period": "FY2025Q4",
  "form_type": "10-Q",
  "source_type": "sec_xbrl",
  "source_url": "https://www.sec.gov/...",
  "source_tag": "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
  "confidence": "high"
}
```

### 5.3 `memory_items` 相容列

- `kind`: `earnings`  
- `item_id`: `sha256("earnings:{report_id}")`  
- `published_at`: 同步自 report  
- `source_url`: `source_documents[0].url`  
- `category`: `earnings`  
- `score_status`: report `confidence`  
- additive：`report_id`, `tier`, `ticker`

---

## 6. 邊界條件與失敗策略

| # | 情境 | 行為 |
|---|------|------|
| E1 | 多個 Revenue XBRL tag | `sec_concept_map` 優先序；取最新 `filed` 且 `fp` 匹配 |
| E2 | 僅 8-K Item 2.02、無 10-Q 數字 | `confidence=medium`；標「待季報」；可推 narrative-only |
| E3 | 8-K/A 修正 | 新 accession；merge 同 `report_id`；`supersedes_accession` |
| E4 | `published_at` 解析失敗 | **不** 進公開列表；寫 `earnings_quarantine` log |
| E5 | TSM / ASML 等 ADR | CIK 以 SEC 為準；`ticker` 用使用者 watchlist 代號 |
| E6 | Fiscal 年結非 12 月 | 僅信 XBRL `fy`/`fp`/`end`，禁止日曆推斷 |
| E7 | 同 run 重複送 Telegram | `state_store` key `earnings:{report_id}` |
| E8 | XBRL 失敗 | 不送 `confidence=high`；可 SEC-only low 或 skip Telegram |
| E9 | Vendor 失敗 | SEC-only；`estimates`/`surprise` 空 |
| E10 | LLM 失敗 | archive facts；Telegram 可僅 metrics 模板 |
| E11 | 超過 `MAX_*_PER_RUN` | Tier 1 優先；其餘 defer 下一 run |
| E12 | 非 watchlist 廣抓 | archive only；Dashboard「全部」標籤 |

---

## 7. 系統元件

### 7.1 新增 / 修改模組

| 模組 | 動作 |
|------|------|
| `sources/sec_xbrl_fetcher.py` | 新增 |
| `sources/sec_concept_map.py` | 新增 |
| `sources/ticker_cik_map.py` | 新增（watchlist + SEC company_tickers） |
| `sources/earnings_fetcher.py` | RSS 觸發 + CIK 解析 + 佇列 |
| `sources/vendor_earnings_provider.py` | 新增（optional） |
| `agents/earnings_narrative_extractor.py` | 拆分 narrative |
| `agents/earnings_analyzer.py` | 繁中 takeaway |
| `agents/earnings_agent.py` | 過渡期保留或 thin wrapper |
| `scoring/earnings_report_store.py` | 寫 `tech_pulse_earnings_reports` |
| `pipeline/crew.py` | `_run_earnings_pipeline` 重寫 |
| `delivery/message_formatter.py` | `format_earnings_v2` |
| `dashboard/app/(app)/earnings/` | 列表 + `[ticker]` |
| `dashboard/app/api/v1/earnings/` | REST |
| `config/earnings_watchlist.yaml` | Tier 清單 |

### 7.2 Agent 角色

- **禁止**：LLM 計算 beat%、推導 revenue、改寫 XBRL 數字  
- **允許**：在 `EarningsFact[]` 已驗證前提下產生 `investment_takeaway_zh`、`ai_infra_relevance`、`management_tone`  
- **fact_guard v2**：XBRL 驗 `source_tag+accession+period`；quote 驗 substring；vendor 驗 `vendor+as_of`

---

## 8. 分階切片（實作順序）

| Slice | 內容 | 驗收 |
|-------|------|------|
| **S0** | `ticker_cik_map` + watchlist YAML + SEC UA / rate limit | preflight CIK for Tier 1 全過 |
| **S1** | `sec_xbrl_fetcher` + `sec_concept_map` + normalize | fixture NVDA/AMD/TSM revenue+EPS |
| **S2** | `EarningsReport` + `earnings_report_store` + crew 寫入；`published_at` | Firestore doc 可查 |
| **S3** | Narrative + Analyzer 拆分；fact_guard v2 | 測試：篡改數字被清空 |
| **S4** | Vendor optional + calendar；tier 優先佇列 | `VENDOR_MODE=off` 仍通 |
| **S5** | Telegram 財報雷達 v2 + dedupe + 本週 tier1/2 | HTML 訊息正確 |
| **S6** | Dashboard `/earnings` + API + Nav + ISR | 排序 published_at；tier badge |
| **S7** | run summary metrics、failure policy、`docs/EARNINGS_PORTAL.md` | 日誌有 `earnings_xbrl_facts_loaded` |

**並行**：S6 UI 可用 mock / staging collection；S0–S5 需 pipeline 核准。

---

## 9. Dashboard 專欄

### 9.1 路由

- `/earnings` — 列表（預設：watchlist Tier ≤3 + 最近 30 天）  
- `/earnings/[ticker]` — 單公司 fiscal 時間軸（`period_end` DESC）  
- `GET /api/v1/earnings?limit=&ticker=&tier=&since=`  
- `GET /api/v1/earnings/[ticker]/[fiscal_year]/[fiscal_period]`  
- `GET /api/v1/earnings/calendar?horizon=30d`  

### 9.2 UI 元素

- Metrics badge（revenue / EPS / margin）  
- Surprise / estimate badge（vendor 有資料時）  
- `ai_infra_relevance` badge  
- `confidence` + `source_type`  
- Tier 色條（1=accent, 5=muted）  
- Filing / transcript 連結  
- 篩選：Tier、SiC tag、僅已持倉（可選，讀 env 或靜態 list）

### 9.3 首頁整合（可選 S6+）

「今日財報」區塊：`published_at >= startOfTodayTaipei`，最多 5 則，不取代 digest。

---

## 10. Telegram

- 標題：`💰 財報雷達｜{ticker} {quarter_label}`  
- 區塊：headline_metrics → surprise（若有）→ `investment_takeaway_zh`（一句）→ filing link  
- `EARNINGS_TELEGRAM_MIN_TIER`：預設 `2`（Tier 1–2 必推；3–5 可設 `1` 全推）  
- 與 digest「財報焦點」配額獨立（沿用 `EARNINGS_THEME_RATIO_CAP`）

---

## 11. 測試策略

| 類型 | 內容 |
|------|------|
| Unit | `normalize_latest_quarter_facts`、concept fallback、date parse |
| Fixture | NVDA, AMD, MSFT, TSM, AAPL fiscal 邊界（1 月 / 9 月 FY） |
| Integration | mock SEC JSON → report → Firestore write |
| Dashboard | API contract test；`published_at` 排序 |
| Regression | `memory_items` 舊 `kind=earnings` 仍可讀 |

---

## 12. 合約與文件

- **Additive**：[`docs/PORTAL_CONTRACT.md`](../../PORTAL_CONTRACT.md) 不 breaking  
- **新增**：`docs/EARNINGS_PORTAL.md`（`tech_pulse_earnings_reports` 欄位）  
- **新增**：`docs/EARNINGS_API_EVALUATION.md`（vendor 評估，S4 前）  
- **更新**：`TODOS.md`、`CHANGELOG.md`（每 slice 完成時）

---

## 13. 風險與緩解

| 風險 | 緩解 |
|------|------|
| SEC rate limit | backoff + cache + cap |
| D 覆蓋過廣 | 雙 cap + 非 watchlist archive-only |
| Tier 2–5 未列滿 | YAML `pending`；不臆造 ticker |
| TSM 等 foreign issuer 表單差異 | 以實際 `form_type` + XBRL 為準；測試 fixture |
| Pipeline deploy | maintainer 核准；staging `TECH_PULSE_ENV=staging` 先跑 |

---

## 14. 核准記錄

| 項目 | 狀態 |
|------|------|
| 方案丙分階 S0–S7 | ✅ |
| `published_at` 排序 | ✅ |
| Fiscal canonical key | ✅ |
| 覆蓋 D + 分層 Watchlist | ✅ |
| 五層標的清單（部分 pending） | ✅ |

**下一步**：使用者審閱本 spec → 核准後 invoke **writing-plans** 產出實作計畫（含 maintainer pipeline 核准檢查點）。
