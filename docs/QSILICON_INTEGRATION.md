# Q-Silicon（my-investment-ai-agent）整合 — Slice 1

tech-pulse Vercel Dashboard 提供與主 repo `api_routers/news.py` 對齊的 **Portal News API**。主 repo 可停用自建 Firestore 新聞讀取，改呼叫下列端點。

## Base URL

```
https://<your-vercel-host>/api/v1/news
```

本機：`http://localhost:3000/api/v1/news`

## 授權

與其他 `/api/v1/*` 相同：

```bash
curl -sS -H "Authorization: Bearer $API_READ_TOKEN" \
  "https://my-tech-pulse-agent.vercel.app/api/v1/news/digest?limit=10"
```

公開讀模式（`DASHBOARD_PUBLIC_READ=1`）下，匿名可讀摘要層級欄位；完整 `zh_body` 等仍建議帶 token。

## 端點（對齊主 repo FastAPI）

| 方法 | 路徑 | 查詢參數 | 說明 |
|------|------|----------|------|
| `GET` | `/digest` | `date=YYYY-MM-DD`、`limit=1..50` | 快訊列表 + `themes` + 頂層 **`summary`**（給日報 exclusion） |
| `GET` | `/deep` | `pillar=ai\|semiconductor\|crypto`、`limit=1..50` | 深度稿列表 |
| `GET` | `/deep/{itemId}` | — | 單篇深度稿 |
| `GET` | `/themes` | `limit=1..200` | 近期標籤聚合 |

### 回應欄位（單則 item）

| 欄位 | 來源（Firestore） |
|------|-------------------|
| `headline` / `title` | `zh_title` → `hook` → `zh_summary` → `title` |
| `commentary_zh` | `zh_summary`（含 CJK）或 fallback |
| `gemini_take` / `summary` | 英文 `summary` / `what_happened` |
| `pillar_key` | `ai` / `semiconductor` / `crypto`（關鍵字推斷） |
| `confidence` | `score`（0–10 量級，非機率） |
| `source_domain` | `source_url` hostname 或 `source_name` |

## 主 repo `.env` 建議（取代自建 `/api/news`）

```bash
TECH_PULSE_IN_BRIEF=1
TECH_PULSE_URL=https://my-tech-pulse-agent.vercel.app/api/v1/news/digest?limit=12
# tools/tech_pulse_tool.py 會解析 JSON 的 summary 欄位（digest 回應已內建）
```

若需 Bearer token，需在 `tech_pulse_tool.py` 加 Header（Phase 1.1）；目前可將 digest 設為公開讀或透過 Vercel 同域反代。

## 主 repo 可標記 deprecated

- `api_routers/news.py`（改讀 tech-pulse URL）
- PWA `/news` 直接連結 Vercel 或嵌入 iframe（產品選擇）

## Slice 2+（未做）

- `GET /api/earnings/upcoming` proxy
- 共用 watchlist yaml
