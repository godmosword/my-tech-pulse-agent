# Q-Silicon（my-investment-ai-agent）整合

tech-pulse Vercel 為 **內容 SSOT**；主 repo 改為 HTTP 消費者，可刪除重複 Firestore 讀取與 PWA 新聞／財報 UI。

**Base（兩個 slice 共用）**

```
https://<your-vercel-host>/api/v1
```

授權：`Authorization: Bearer $API_READ_TOKEN`（公開讀模式可匿名讀部分欄位）。

---

## Slice 1 — News API（已完成）

路徑前綴：`/api/v1/news`

| 方法 | 路徑 | 說明 |
|------|------|------|
| `GET` | `/digest?date=&limit=` | 快訊 + `themes` + **`summary`**（`TECH_PULSE_URL`） |
| `GET` | `/deep?pillar=&limit=` | 深度稿 |
| `GET` | `/deep/{itemId}` | 單篇深度 |
| `GET` | `/themes?limit=` | 標籤聚合 |

主 repo：

```bash
TECH_PULSE_IN_BRIEF=1
TECH_PULSE_URL=https://my-tech-pulse-agent.vercel.app/api/v1/news/digest?limit=12
```

---

## Slice 2 — Earnings API（已完成）

路徑前綴：`/api/v1/earnings`

| 方法 | 路徑 | 對齊主 repo | 說明 |
|------|------|-------------|------|
| `GET` | `/upcoming?days=14` | `/api/earnings/upcoming` | 行事曆（Finnhub + watchlist）；無 key 時 fallback 近期 Firestore 財報 |
| `GET` | `/{symbol}/insight` | `/api/earnings/{symbol}/insight` | 最新 `tech_pulse_earnings_reports` v3 報告 + `report_url_path` |
| `GET` | `/watchlist` | — | 匯出之 yaml watchlist（45 檔，含 Q-Silicon mega-cap） |
| `GET` | `/calendar?horizon=` | — | 相容舊名；內部等同 upcoming |
| `GET` | `/report/{reportId}` | — | 單篇完整報告（既有） |
| `GET` | `/` | — | 列表（既有） |

### Vercel 建議 env（行事曆）

```bash
FINNHUB_API_KEY=...          # 與 pipeline 相同 key 即可
FINNHUB_HTTP_TIMEOUT_SEC=10
```

### Watchlist 單一來源

- 編輯：`config/earnings_watchlist.yaml`
- 匯出 Dashboard JSON：`python3 scripts/export_earnings_watchlist_json.py`

---

## 主 repo 作業清單（一次做完）

在 **my-investment-ai-agent** 依序處理（tech-pulse 已部署 `main` 後）：

### 1. 環境變數

```bash
# 日報 exclusion（Slice 1）
TECH_PULSE_IN_BRIEF=1
TECH_PULSE_URL=https://my-tech-pulse-agent.vercel.app/api/v1/news/digest?limit=12

# 若 tech_pulse_tool 尚未支援 Bearer，可二選一：
#   A) Vercel 設 DASHBOARD_PUBLIC_READ=1（digest 可匿名）
#   B) 改 tech_pulse_tool.py 加上 Authorization: Bearer <API_READ_TOKEN>

# 財報 API base（Slice 2 — 給 PWA / 內部 client 用，擇一實作）
TECH_PULSE_API_BASE=https://my-tech-pulse-agent.vercel.app/api/v1
TECH_PULSE_API_TOKEN=<與 Vercel API_READ_TOKEN 相同>
```

### 2. 程式碼瘦身（建議 PR）

| 動作 | 檔案／區域 |
|------|------------|
| **Deprecated** | `api_routers/news.py` → 改呼叫 `$TECH_PULSE_API_BASE/news/*` 或刪除 router |
| **Deprecated** | PWA `/news` 頁 → 外連 Vercel `/` 或 `/archive` |
| **替換** | `api_routers/earnings.py` 的 `upcoming` / `insight` → proxy `GET .../earnings/upcoming`、`.../earnings/{sym}/insight` |
| **刪除依賴** | `DEEP_FILING_ANALYSIS_FILE` JSONL scaffold（改讀 tech-pulse `rendered_markdown_zh`） |
| **可留** | `tools/tech_pulse_tool.py`（只改 URL） |
| **可留** | `earnings_watchlist.py` 的 `MEGA_CAP_*` 改為註解「已併入 tech-pulse yaml」或從 `GET .../earnings/watchlist` 同步 |

### 3. 驗證 curl（替換後）

```bash
export BASE=https://my-tech-pulse-agent.vercel.app
export TOKEN=...

curl -sS -H "Authorization: Bearer $TOKEN" "$BASE/api/v1/earnings/upcoming?days=14" | head -c 400
curl -sS -H "Authorization: Bearer $TOKEN" "$BASE/api/v1/earnings/NVDA/insight" | head -c 400
curl -sS -H "Authorization: Bearer $TOKEN" "$BASE/api/v1/news/digest?limit=5" | head -c 400
```

### 4. 不必改

- 日報 `main.py` Crew / LangGraph / `validate_report`
- Portfolio / paper / execution-intents
- CoinGlass / 鏈上工具

---

## Slice 3+（未做）

- `tech_pulse_tool` 內建 Bearer
- 主 repo 刪除 `data-verification-ui` 科技新聞板塊（僅留連結）
