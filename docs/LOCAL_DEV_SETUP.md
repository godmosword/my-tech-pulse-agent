# 本機開發設定（Pipeline + Dashboard）

> 暫停 Cloud Run Secret Manager 時，在本機用 `.env` + ADC 跑 pipeline、補繁中、預覽 Dashboard。  
> 雲端部署：[`DEPLOY_CHECKLIST.md`](DEPLOY_CHECKLIST.md) · 財報 env：[`EARNINGS_ENV.md`](EARNINGS_ENV.md)

---

## 一次性準備

在 repo 根目錄：

```bash
cd /path/to/my-tech-pulse-agent
python3 -m venv .venv && source .venv/bin/activate   # 可選
pip install -e .
cp .env.example .env
```

編輯 `.env`（見下方「環境變數」），然後登入 GCP（讀寫 Firestore）：

```bash
gcloud auth application-default login
gcloud config set project my-tech-pulse-agent-494715   # 改成你的 project id
export GOOGLE_CLOUD_PROJECT=my-tech-pulse-agent-494715
```

---

## 環境變數（`.env` 最少填這些）

```bash
GEMINI_API_KEY=你的_key
SEC_USER_AGENT=tech-pulse/0.2 你的@email.com
TELEGRAM_BOT_TOKEN=...          # 若要推播 Telegram
TELEGRAM_CHANNEL_ID=...

MEMORY_ENABLED=1
STATE_BACKEND=auto
FIRESTORE_COLLECTION_PREFIX=tech_pulse

# 繁中標題／摘要（預設開；Extractor 漏譯時 Translation Agent 用 Flash 補）
TRANSLATION_AGENT_ENABLED=1
MAX_TRANSLATION_ARTICLES=8
BACKFILL_GEMINI_MODEL=              # 可省略，預設 Flash
BACKFILL_ZH_OUTPUT_TOKENS=1536
BACKFILL_ZH_RETRY_OUTPUT_TOKENS=2048

# 財報 v3（可選）
EARNINGS_VENDOR_MODE=free
FINNHUB_API_KEY=你的_finnhub_key
EARNINGS_REPORTS_ENABLED=1
```

本機 pipeline **通常不必** 設 `FIREBASE_SERVICE_ACCOUNT_JSON`（用 ADC 即可）。

---

## 本機需執行的指令（依情境）

### A. 跑一輪完整 pipeline（寫 Firestore + 可推 Telegram）

```bash
# 在 repo 根目錄，已 source .venv 且 .env 已填
python scripts/preflight.py          # 可選：檢查 key / env
python main.py
```

跑完在日誌搜尋 `pipeline_run_summary`，例如：

```json
{
  "summaries_count": 5,
  "translation_filled_count": 3
}
```

`translation_filled_count > 0` 表示 Translation Agent 有補上 `zh_title` / `zh_summary`。

---

### B. 舊稿補繁中標題與摘要（Dashboard 仍顯示英文時必做）

**僅在本機或 Cloud Shell** 執行（需 `GEMINI_API_KEY` + Firestore **寫入**權限；**不要在 Vercel 跑**）。

```bash
# 1) 先乾跑：只看會改哪些 doc，不寫入
python scripts/backfill_zh_fields.py --dry-run --limit 30 --max-updates 20

# 2) 確認輸出後正式寫入
python scripts/backfill_zh_fields.py --limit 30 --max-updates 20
```

| 參數 | 說明 |
|------|------|
| `--limit` | 依 `delivered_at` 倒序抓最近 N 篇 |
| `--max-updates` | 最多成功 patch 幾篇（控 Gemini 用量） |
| `--dry-run` | 只 log patch 內容，不寫 Firestore |

腳本用 `llm/zh_backfill.py`（Flash）補 `zh_title`、`zh_summary`、`hook`；與 pipeline 內 Translation Agent 同一套邏輯。

寫入後刷新 production Dashboard，或本機 `pnpm dev` 預覽。

---

### C. 財報歷史回填（可選）

```bash
python scripts/backfill_earnings.py --help
# 例：XBRL 區間回填（詳見腳本 --help）
python scripts/backfill_earnings.py --since 2026-04-01 --until 2026-05-21
```

需 `SEC_USER_AGENT`、Firestore 寫入；`--with-llm` 會多耗 Gemini。

---

### D. Dashboard 本機預覽

```bash
cd dashboard
cp .env.example .env.local
```

`.env.local` 擇一：

| 方式 | 設定 |
|------|------|
| **A** | `FIREBASE_SERVICE_ACCOUNT_JSON=` — 見下方「產生 Vercel 用 SA」 |
| **B** | 留空 + 根目錄已 `gcloud auth application-default login` |

```bash
FIRESTORE_COLLECTION_PREFIX=tech_pulse
pnpm install
pnpm dev
```

瀏覽：

- <http://localhost:3000/> — 今日編排（需 Firestore 有 `tech_pulse_memory_items`）
- <http://localhost:3000/earnings> — 財報列表
- <http://localhost:3000/earnings/report/{reportId}> — 深度報告

---

### E. 產生 `FIREBASE_SERVICE_ACCOUNT_JSON`（給 Vercel，本機也可貼進 `.env.local`）

```bash
PROJECT_ID=my-tech-pulse-agent-494715 ./scripts/setup_dashboard_sa.sh
# 產出 repo 根目錄 dashboard-sa.json（勿 commit）

base64 -w0 dashboard-sa.json    # Linux → 貼 Vercel / dashboard/.env.local
# macOS: base64 -i dashboard-sa.json | pbcopy
```

---

### F. 單元測試（本機）

```bash
# 翻譯 Agent
python3 -m pytest tests/test_translation_agent.py tests/test_zh_backfill.py -q

# 財報 v3
python3 -m pytest tests/test_scorecard_builder.py tests/test_guidance_segment_extractors.py -q
```

---

## 本機 vs 雲端

| 項目 | 本機 Pipeline | 本機 Dashboard | Vercel | Cloud Run Job |
|------|---------------|----------------|--------|---------------|
| `FINNHUB_API_KEY` | `.env` | 不需要 | 不需要 | Secret 或 env |
| `FIREBASE_SERVICE_ACCOUNT_JSON` | 通常不需要（ADC） | `.env.local` 或 ADC | **必填**（唯讀 SA） | Job SA，通常不需要 |
| 補舊稿繁中 | `backfill_zh_fields.py` | — | — | — |
| 新稿繁中 | `main.py` + Translation Agent | — | — | 同左 |

---

## Cloud Run Secret 錯誤（暫緩時可略過）

若部署出現 `Permission denied on secret ... FINNHUB_API_KEY`：

1. `gcloud run jobs describe <JOB> --region=asia-east1 --format='value(spec.template.spec.template.spec.serviceAccountName)'`
2. 對該 SA 授予 `roles/secretmanager.secretAccessor`，或改 Job 一般 env 直接填 `FINNHUB_API_KEY`。

本機開發不受此影響，Finnhub 寫在 `.env` 即可。

---

## 驗證清單

- [ ] `python scripts/preflight.py` 通過（可選）
- [ ] `python main.py` 無 Firestore / Gemini 錯誤
- [ ] 日誌 `translation_filled_count` ≥ 0（有新英文稿時）
- [ ] 舊稿已跑 `backfill_zh_fields.py`（無 `--dry-run`）
- [ ] `pnpm dev` 後首頁標題為繁中、訪客可見 `zh_summary` 導讀
- [ ] `/earnings` 可列出報告（若已跑財報 pipeline / backfill）
