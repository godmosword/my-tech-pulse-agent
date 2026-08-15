# 部署設定清單（Vercel + GitHub Actions）

本文件彙整 **Dashboard（Vercel）** 與 **Pipeline（GitHub Actions schedule.yml）** 的環境變數與驗證步驟。適用於 [my-tech-pulse-agent.vercel.app](https://my-tech-pulse-agent.vercel.app/)。

相關文件：

- Dashboard 細節：[`dashboard/README.md`](../dashboard/README.md)
- Staging 語意 prefilter：[`docs/STAGING.md`](STAGING.md)
- Portal 合約：[`docs/PORTAL_CONTRACT.md`](PORTAL_CONTRACT.md)
- 排程：[`docs/SCHEDULED_RUNS.md`](SCHEDULED_RUNS.md)

---

## 已合併功能對照（`main`）

| PR | 狀態 | 影響 |
|----|------|------|
| [#44](https://github.com/godmosword/my-tech-pulse-agent/pull/44) | 已合併 | 新稿自動衍生 `zh_title`；dashboard 讀 `hook` |
| [#46](https://github.com/godmosword/my-tech-pulse-agent/pull/46) | 已合併 | Staging prefilter、NewsAPI、digest 快照、backfill 腳本 |

**注意：** Dashboard 只負責顯示。舊稿若 JSON 無 `zh_title` / `zh_summary`，首頁仍可能顯示英文標題，需執行 [繁中 backfill](#6-舊稿繁中-backfill) 或等 pipeline 重跑 extractor。

---

## 1. Vercel（專案根目錄：`dashboard/`）

在 Vercel 專案設定 → Environment Variables（Production 建議全部設定）。

### 1.1 必填

| 變數 | 範例 / 說明 |
|------|-------------|
| `NEXT_PUBLIC_SITE_URL` | `https://my-tech-pulse-agent.vercel.app`（無結尾 `/`）。供 sitemap、OG、`metadataBase`。 |
| `REVALIDATE_TOKEN` | 可選；GHA commit JSON 後 Vercel 會重建，通常不必再打 ISR。 |

### 1.2 讀取 API（`/api/v1/*`）

二擇一（或兩者並用）：

| 模式 | 變數 | 行為 |
|------|------|------|
| **Bearer API**（整合 / Portal） | `API_READ_TOKEN` | `Authorization: Bearer <token>` 可讀完整欄位；未設定時 `/api/v1/health` 回 `503`。 |
| **公開讀 + 登入** | `DASHBOARD_PUBLIC_READ=true` | 匿名可看標題與 `zh_summary`；完整正文需 `/login`。 |
| 公開讀時必填 | `DASHBOARD_SESSION_SECRET` | ≥32 字元隨機字串（cookie HMAC）。 |
| 公開讀登入帳密 | `DASHBOARD_BASIC_AUTH_USER` / `DASHBOARD_BASIC_AUTH_PASS` | 與 `/login` 表單相同。 |

未啟用 `DASHBOARD_PUBLIC_READ` 且未設 `API_READ_TOKEN` 時，REST API 無法正常服務。

### 1.3 可選

| 變數 | 說明 |
|------|------|
| `DIGEST_HEADER_TIMEZONE` | 預設 `Asia/Taipei`。 |
| `DASHBOARD_BASIC_AUTH_*` | 未開公開讀時，可對全站套用 HTTP Basic（與 SEO 衝突，production 公開站建議用公開讀模式）。 |

### 1.4 Vercel 部署後檢查

```bash
# 健康檢查（需已設 API_READ_TOKEN）
curl -sS -H "Authorization: Bearer $API_READ_TOKEN" \
  "https://my-tech-pulse-agent.vercel.app/api/v1/health"

# ISR webhook（手動測試，token 需與 REVALIDATE_TOKEN 一致）
curl -sS -X POST \
  "https://my-tech-pulse-agent.vercel.app/api/revalidate?path=/" \
  -H "x-revalidate-token: $REVALIDATE_TOKEN"
```

預期：`health` → `200` 且 `{"ok":true,...}`；未設 token → `503` 與 `API_READ_TOKEN not configured`。

合併 `main` 後請在 Vercel 確認 **Production 已 Redeploy** 最新 commit（含 #44–#46）。

---

## 2. GitHub Actions pipeline（Production）

排程見 [`SCHEDULED_RUNS.md`](SCHEDULED_RUNS.md)。Workflow 已寫死 `MEMORY_BACKEND=json`、`STATE_BACKEND=sqlite`、`DASHBOARD_DATA_DIR=dashboard/data`。

### 2.1 Secrets（每次 run 必備）

| Secret | 說明 |
|--------|------|
| `GEMINI_API_KEY` | Gemini 提取 / 打分 / 合成 |
| `TELEGRAM_BOT_TOKEN` | Bot token |
| `TELEGRAM_CHANNEL_ID` | 頻道 ID |
| `TELEGRAM_ALERT_CHAT_ID` | **建議** — 管線未處理例外時的告警 chat |
| `SEC_USER_AGENT` | SEC EDGAR User-Agent（含 email） |

### 2.2 可選 secrets

| Secret | 說明 |
|--------|------|
| `NEWSAPI_KEY` | NewsAPI technology headlines |
| `APIFY_API_KEY` | Social trending + 可選全文擷取 |
| `FINNHUB_API_KEY` | 財報 consensus / surprise |
| `FMP_API_KEY` | FMP 比率 / 現金流 |
| `FRED_API_KEY` | 宏觀利率 / CPI |

完整列表見根目錄 [`.env.example`](../.env.example)。ISR webhook 可省略：GHA commit 後 Vercel 會重建。

### 2.3 Variables

| Variable | 用途 |
|----------|------|
| `PIPELINE_SCHEDULE_ENABLED` | `true` 才跑 cron；手動 `workflow_dispatch` 不受限 |

---

## 3. Staging（可選）

本機或手動 `workflow_dispatch` 設 `TECH_PULSE_ENV=staging` 觀測語意 prefilter。**不要**與 production 共用 Telegram 頻道。詳見 [`STAGING.md`](STAGING.md)。

---

## 4. GitHub Actions CI

`ci.yml` 只跑 pytest / dashboard lint。`dashboard/data/**` 與 `state/**` 的資料 commit **不重跑** CI。

---

## 5. 部署後驗證（端到端）

### 5.1 Pipeline

```bash
# 與 production 相同 env 下執行
python scripts/preflight.py
```

手動觸發 Job 或等排程後，在日誌搜尋 `pipeline_run_summary`，確認例如：

> 自動排程設定見 [`SCHEDULED_RUNS.md`](SCHEDULED_RUNS.md)。切換前請 pause GCP `tech-pulse-daily`。


```json
{
  "summaries_count": 3,
  "newsapi_fetched": 0,
  "semantic_prefilter_enabled": false,
  "tech_pulse_env": "production"
}
```

### 5.2 JSON snapshots

- `dashboard/data/memory_items.json` — 新稿應有 `zh_summary`；#44 後新稿應有 `zh_title`
- `dashboard/data/digests.json` — `DIGEST_SNAPSHOT_ENABLED=1` 且送報成功後有新快照
- `state/dedup.sqlite` — 去重／embedding；必須被 GHA commit 回來，否則下一跑會重送 Telegram

### 5.3 Dashboard（瀏覽器）

- `/` — 今日熱門代號可點 → `/archive?ticker=...`
- `/item/<id>` — 區塊：中文標題／中文摘要／英文摘要
- 有 `zh_*` 的稿件顯示中文標題；僅英文欄位的舊稿仍顯示英文 → 需 backfill

### 5.4 REST API

```bash
export API_READ_TOKEN="<vercel-env>"
curl -sS -H "Authorization: Bearer $API_READ_TOKEN" \
  "https://my-tech-pulse-agent.vercel.app/api/v1/digest/today"
```

---

## 6. 舊稿繁中 backfill

在具備 `GEMINI_API_KEY` 的本機執行（寫入 `dashboard/data/memory_items.json`；**非** Vercel）：

```bash
# 先評估（只抓最近 12 篇，最多處理 8 篇需補 zh_* 的）
python scripts/backfill_zh_fields.py --dry-run --limit 12 --max-updates 8

# 正式寫入
python scripts/backfill_zh_fields.py --limit 12 --max-updates 8
```

腳本讀寫 `dashboard/data/memory_items.json`，再以 **Flash 輕量 JSON**（`llm/zh_backfill.py`）只生成 `zh_title` / `zh_summary` / `hook`。

完成後 commit JSON，Vercel 會隨 push 重建。

---

## 7. 常見問題

| 現象 | 可能原因 | 處理 |
|------|----------|------|
| `/api/v1/health` → 503 | Vercel 未設 `API_READ_TOKEN` | 設定 token 並 redeploy |
| 首頁部分標題仍英文 | 舊稿缺 `zh_title` | 執行 `backfill_zh_fields.py` 或等 pipeline 新稿 |
| 送報後網站未更新 | GHA 未 commit／未 push，或 Vercel 未重建 | 查 `schedule.yml` 與 Vercel deploy |
| Staging 指標全是 0 | 未設 `TECH_PULSE_ENV=staging` | 見 §3 |
| `newsapi_fetched` 永遠 0 | 未設 `NEWSAPI_KEY` | 在 GHA secrets 加上 key |

---

## 8. 快速勾選表

**Vercel**

- [ ] `NEXT_PUBLIC_SITE_URL`
- [ ] `API_READ_TOKEN` **或** `DASHBOARD_PUBLIC_READ` + `DASHBOARD_SESSION_SECRET` + 登入帳密
- [ ] Production redeploy 最新 `main`

**GitHub Actions**

- [ ] Secrets：`GEMINI_API_KEY`、`TELEGRAM_*`、`SEC_USER_AGENT`
- [ ] `vars.PIPELINE_SCHEDULE_ENABLED=true`
- [ ] GCP Console 已 pause `tech-pulse-daily`（避免雙跑）
- [ ] （可選）`NEWSAPI_KEY`、`APIFY_API_KEY`、`FINNHUB_API_KEY`

**資料**

- [ ] `backfill_zh_fields.py` dry-run 後決定是否正式 backfill
