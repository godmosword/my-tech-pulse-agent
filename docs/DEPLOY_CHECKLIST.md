# 部署設定清單（Vercel + GCP）

本文件彙整 **Dashboard（Vercel）** 與 **Pipeline（Cloud Run Job）** 的環境變數與驗證步驟。適用於 [my-tech-pulse-agent.vercel.app](https://my-tech-pulse-agent.vercel.app/) 與 production/staging Job。

相關文件：

- Dashboard 細節：[`dashboard/README.md`](../dashboard/README.md)
- Staging 語意 prefilter：[`docs/STAGING.md`](STAGING.md)
- Portal / Firestore 合約：[`docs/PORTAL_CONTRACT.md`](PORTAL_CONTRACT.md)
- CI 自動部署：[`README.md`](../README.md#continuous-deployment-github-actions--cloud-run-job)

---

## 已合併功能對照（`main`）

| PR | 狀態 | 影響 |
|----|------|------|
| [#44](https://github.com/godmosword/my-tech-pulse-agent/pull/44) | 已合併 | 新稿自動衍生 `zh_title`；dashboard 讀 `hook` |
| [#46](https://github.com/godmosword/my-tech-pulse-agent/pull/46) | 已合併 | Staging prefilter、NewsAPI、digest 快照、backfill 腳本 |

**注意：** Dashboard 只負責顯示。舊稿若 Firestore 無 `zh_title` / `zh_summary`，首頁仍可能顯示英文標題，需執行 [繁中 backfill](#6-舊稿繁中-backfill) 或等 pipeline 重跑 extractor。

---

## 1. Vercel（專案根目錄：`dashboard/`）

在 Vercel 專案設定 → Environment Variables（Production 建議全部設定）。

### 1.1 必填

| 變數 | 範例 / 說明 |
|------|-------------|
| `FIREBASE_SERVICE_ACCOUNT_JSON` | 唯讀 SA JSON（raw 或 base64）。權限：`roles/datastore.viewer`。可用 [`scripts/setup_dashboard_sa.sh`](../scripts/setup_dashboard_sa.sh) 產生。 |
| `NEXT_PUBLIC_SITE_URL` | `https://my-tech-pulse-agent.vercel.app`（無結尾 `/`）。供 sitemap、OG、`metadataBase`。 |
| `REVALIDATE_TOKEN` | 與 pipeline 的 `DASHBOARD_REVALIDATE_TOKEN` **相同** 的隨機密鑰。 |

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
| `FIRESTORE_COLLECTION_PREFIX` | 預設 `tech_pulse`（collection = `{prefix}_memory_items`）。 |
| `TECH_PULSE_FIRESTORE_COLLECTION` | 覆寫完整 collection 名稱（與 pipeline 一致時才改）。 |
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

## 2. GCP Cloud Run Job（Production）

Runtime 使用 Job 預設服務帳號或自訂 SA，需具備：

- `roles/datastore.user`（Firestore 狀態 + memory）
- Secret Manager 或 Job env 中的 API 金鑰

### 2.1 核心（每次 run 必備）

| 變數 | 說明 |
|------|------|
| `GEMINI_API_KEY` | Gemini 提取 / 打分 / 合成 |
| `TELEGRAM_BOT_TOKEN` | Bot token |
| `TELEGRAM_CHANNEL_ID` | 頻道 ID |
| `TELEGRAM_ALERT_CHAT_ID` | **建議** — 管線未處理例外時的 Telegram 告警 chat（管理者私訊或獨立群組）；未設定時 fallback 至 `TELEGRAM_CHANNEL_ID` 並寫入日誌 |
| `MEMORY_ENABLED` | `1` — 寫入 `tech_pulse_memory_items` |
| `STATE_BACKEND` | `auto` 或 `firestore`（Cloud Run 建議 `auto`） |
| `FIRESTORE_COLLECTION_PREFIX` | `tech_pulse`（與 Dashboard 一致） |
| `TECH_PULSE_ENV` | **`production`**（預設；語意 prefilter 關閉） |
| `DIGEST_SNAPSHOT_ENABLED` | `1` — 寫入 `tech_pulse_digests`（#46） |

### 2.2 Dashboard 連動（建議 production 開啟）

| 變數 | 範例 |
|------|------|
| `DASHBOARD_REVALIDATE_URL` | `https://my-tech-pulse-agent.vercel.app/api/revalidate` |
| `DASHBOARD_REVALIDATE_TOKEN` | 與 Vercel `REVALIDATE_TOKEN` 相同 |
| `DASHBOARD_REVALIDATE_TIMEOUT` | `5`（秒，可省略） |

未設定 URL 或 token 時，pipeline 略過 ISR webhook（本地 / CI 可接受）。

### 2.3 可選增強

| 變數 | 說明 |
|------|------|
| `NEWSAPI_KEY` | 啟用 NewsAPI technology headlines（#46） |
| `APIFY_API_KEY` | Social trending + 可選全文擷取 |
| `NEWSAPI_PAGE_SIZE` | 預設 `20` |
| `SEMANTIC_PREFILTER_ENABLED` | Production **勿** 設 `1`，除非已觀測 staging；見 [`STAGING.md`](STAGING.md) |
| `GITHUB_PAGES_URL` | 若有靜態頁連結 |

完整列表見根目錄 [`.env.example`](../.env.example)。

### 2.4 更新 Job 環境變數（範例）

```bash
export GCP_PROJECT_ID="<your-project>"
export GCP_REGION="asia-east1"
export CLOUD_RUN_SERVICE="tech-pulse"   # Job 名稱

gcloud run jobs update "$CLOUD_RUN_SERVICE" \
  --region "$GCP_REGION" \
  --project "$GCP_PROJECT_ID" \
  --update-env-vars \
TECH_PULSE_ENV=production,\
MEMORY_ENABLED=1,\
DIGEST_SNAPSHOT_ENABLED=1,\
STATE_BACKEND=auto,\
FIRESTORE_COLLECTION_PREFIX=tech_pulse,\
DASHBOARD_REVALIDATE_URL=https://my-tech-pulse-agent.vercel.app/api/revalidate,\
DASHBOARD_REVALIDATE_TOKEN="<same-as-vercel-REVALIDATE_TOKEN>"
```

機密（`GEMINI_API_KEY`、`TELEGRAM_*`）請用 Secret Manager 或 Console 另行設定，勿寫入版本庫。

---

## 3. GCP Staging Job（可選）

用於觀測語意 prefilter，**不應** 與 production 共用 Telegram 頻道（若共用請改為 dry-run 或測試頻道）。

| 步驟 | 說明 |
|------|------|
| 建立第二個 Cloud Run Job | 例如 `tech-pulse-staging` |
| Job env | `TECH_PULSE_ENV=staging`（自動開啟 semantic prefilter） |
| GitHub Variable | `CLOUD_RUN_STAGING_JOB=tech-pulse-staging` |
| CI | `main` push 後 `deploy-staging` 會部署同一映像並帶 `TECH_PULSE_ENV=staging` |

觀測日誌欄位：`semantic_prefilter_dropped`、`newsapi_fetched`、`articles_after_scoring`。詳見 [`STAGING.md`](STAGING.md)。

---

## 4. GitHub Actions（CI → GCP）

**Variables**（Settings → Actions → Variables）：

| Variable | 用途 |
|----------|------|
| `GCP_PROJECT_ID` | GCP 專案 |
| `GCP_REGION` | 區域（如 `asia-east1`） |
| `ARTIFACT_REGISTRY_REPO` | Artifact Registry repo 名 |
| `CLOUD_RUN_SERVICE` | Production Job 名稱 |
| `CLOUD_RUN_STAGING_JOB` | （可選）Staging Job 名稱；空則 skip staging deploy |

**Secrets**（WIF，無 JSON key）：

| Secret | 用途 |
|--------|------|
| `WIF_PROVIDER` | Workload Identity Provider 資源名 |
| `WIF_SERVICE_ACCOUNT` | 具 `run.developer` + `artifactregistry.writer` 的 SA |

每次 deploy 會 `--update-env-vars DIGEST_FORMAT=v1`；其他 env 以 GCP Console / `gcloud` 為準，CI 不會覆寫你手動設的機密。

---

## 5. 部署後驗證（端到端）

### 5.1 Pipeline

```bash
# 與 production 相同 env 下執行
python scripts/preflight.py
```

手動觸發 Job 或等排程後，在日誌搜尋 `pipeline_run_summary`，確認例如：

```json
{
  "summaries_count": 3,
  "newsapi_fetched": 0,
  "semantic_prefilter_enabled": false,
  "tech_pulse_env": "production"
}
```

### 5.2 Firestore

- `tech_pulse_memory_items` — 新稿應有 `zh_summary`；#44 後新稿應有 `zh_title`
- `tech_pulse_digests` — `DIGEST_SNAPSHOT_ENABLED=1` 且送報成功後有新文件

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

在具備 `GEMINI_API_KEY` 與 Firestore 寫入權限的環境執行（**非** Vercel；建議本機或 Cloud Shell）：

```bash
# 先評估（只抓最近 12 篇，最多處理 8 篇需補 zh_* 的）
python scripts/backfill_zh_fields.py --dry-run --limit 12 --max-updates 8

# 正式寫入
python scripts/backfill_zh_fields.py --limit 12 --max-updates 8
```

腳本會先一次抓完 Firestore，再以 **Flash 輕量 JSON**（`llm/zh_backfill.py`）只生成 `zh_title` / `zh_summary` / `hook`，避免完整 Pro extractor 輸出過大導致 `zh_*` 被截斷。

完成後對 Vercel 觸發 revalidate（或等下次 pipeline run 自動 POST webhook）。

---

## 7. 常見問題

| 現象 | 可能原因 | 處理 |
|------|----------|------|
| `/api/v1/health` → 503 | Vercel 未設 `API_READ_TOKEN` | 設定 token 並 redeploy |
| 首頁部分標題仍英文 | 舊稿缺 `zh_title` | 執行 `backfill_zh_fields.py` 或等 pipeline 新稿 |
| 送報後網站未更新 | 未設 `DASHBOARD_REVALIDATE_*` 或 token 不一致 | 對照 §1.1 與 §2.2 |
| Staging 指標全是 0 | 未跑 staging Job 或 `TECH_PULSE_ENV` 非 `staging` | 見 §3 |
| `newsapi_fetched` 永遠 0 | 未設 `NEWSAPI_KEY` | 在 Job 加上 key |

---

## 8. 快速勾選表

**Vercel**

- [ ] `FIREBASE_SERVICE_ACCOUNT_JSON`
- [ ] `NEXT_PUBLIC_SITE_URL`
- [ ] `REVALIDATE_TOKEN`
- [ ] `API_READ_TOKEN` **或** `DASHBOARD_PUBLIC_READ` + `DASHBOARD_SESSION_SECRET` + 登入帳密
- [ ] Production redeploy 最新 `main`

**GCP Production Job**

- [ ] `GEMINI_API_KEY`、`TELEGRAM_*`
- [ ] `MEMORY_ENABLED=1`、`STATE_BACKEND=auto`、`TECH_PULSE_ENV=production`
- [ ] `DIGEST_SNAPSHOT_ENABLED=1`
- [ ] `DASHBOARD_REVALIDATE_URL` + `DASHBOARD_REVALIDATE_TOKEN`
- [ ] Firestore IAM + 索引部署：`GCP_PROJECT_ID=<project> bash scripts/deploy_firestore_indexes.sh`
      （部署 `firestore.indexes.json` 的複合 + 向量索引；向量索引為 semantic dup drop 前置。
      假設 `FIRESTORE_COLLECTION_PREFIX=tech_pulse` 與預設資料庫 `(default)`。
      註：`processed_articles`／`article_embeddings` 的 `expires_at` 目前**未**納入 Firestore TTL fieldOverride，
      若要自動過期清理需由維護者另行決定並補入 artifact。）
- [ ] （可選）`NEWSAPI_KEY`、`APIFY_API_KEY`

**GCP Staging（可選）**

- [ ] 獨立 Job + `TECH_PULSE_ENV=staging`
- [ ] `vars.CLOUD_RUN_STAGING_JOB` 已設

**資料**

- [ ] `backfill_zh_fields.py` dry-run 後決定是否正式 backfill
