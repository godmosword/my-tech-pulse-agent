# GitHub Actions

本 repo **維護三支 workflow**。Dashboard 在 Vercel，不走 GitHub Pages。

| Workflow | 檔案 | 何時跑 | 做什麼 |
|----------|------|--------|--------|
| **CI** | [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) | `main` push（資料 commit 除外）或手動 | Python lint／型別／測試 + dashboard lint／typecheck／test／build |
| **Deploy dashboard** | [`.github/workflows/vercel.yml`](../.github/workflows/vercel.yml) | `main` 且 `dashboard/**` 有改（含 JSON），或手動 | POST Vercel Deploy Hook 部署 production（不依賴 Git push webhook） |
| **Scheduled pipeline run** | [`.github/workflows/schedule.yml`](../.github/workflows/schedule.yml) | 每日 cron，或手動 | `python main.py` → 寫 JSON／sqlite → 重算 invest artifacts → 有變更才 commit |

GitHub 內建的 Dependency Graph 可留著（Dependabot 用）。已刪的 `refresh-invest-artifacts.yml` 與 GitHub Pages 不再跑。

## CI

- 略過：只改 `dashboard/data/**`、`state/**`、`backtest/results/**` 的 commit
- 同 ref 新 push 會取消進行中的 CI
- 對齊命令見 [`AGENT-DOMAIN.md`](AGENT-DOMAIN.md) § 驗證矩陣

## Deploy dashboard

- 觸發：`main` 且路徑含 `dashboard/**`（**包含** `dashboard/data/**`），或手動 `workflow_dispatch`
- 做法：POST GitHub secret `VERCEL_DEPLOY_HOOK_URL`（Vercel hook `gha-main` → `main`）
- `dashboard/vercel.json` 關掉 Git push 自動建，避免 webhook 漏掉或與 Hook 雙重建
- 重建 hook：`npx vercel deploy-hooks create gha-main --ref main --project my-tech-pulse-agent --scope godmoswords-projects`，再 `gh secret set VERCEL_DEPLOY_HOOK_URL`

## 日更 pipeline

| 項目 | 值 |
|------|-----|
| Cron | `20 23 * * *` UTC（07:20 Asia/Taipei） |
| 開關 | repo variable `PIPELINE_SCHEDULE_ENABLED=true` |
| 手動 | `workflow_dispatch` **不受**變數限制 |
| 防重疊 | `concurrency: pipeline-run`（不取消進行中的那輪） |
| Timeout | 20 分鐘 |
| 產出 | `dashboard/data/**`、`state/dedup.sqlite`、`backtest/results/track_record.json`、`invest_brief.json` |

GitHub schedule 閒置 60 天會停；用手動 dispatch 喚醒。cron 常晚幾分鐘到一小時。

`main` push 跑 CI（資料 commit 除外）與 `vercel.yml`（`dashboard/**`）；**不**跑 pipeline。

### 必備 secrets

`OPENAI_API_KEY`、`SEC_USER_AGENT`。

### 已設但預設沒用

`NEWSAPI_KEY`、`APIFY_API_KEY`（workflow 仍注入；須另開 `NEWSAPI_ENABLED`／`SOCIAL_TRENDING_ENABLED`，預設 `0`）。

### 未設（workflow 寫了 key 名，空值則該路 skip）

`FINNHUB_API_KEY`、`FMP_API_KEY`、`FRED_API_KEY`。Vendor 維持 `off`。

### 切換檢查

- [ ] `PIPELINE_SCHEDULE_ENABLED=true`
- [ ] 手動 Run workflow 一次，確認 commit 或 log 寫「No artifact changes」
- [ ] `Deploy dashboard` 有跟 `dashboard/data` commit 重建（GitHub Actions，不是 Git webhook）
- [ ] `main` 若有 branch protection，放行 `github-actions[bot]` 或改用 PAT

Invest artifacts 已併進 `schedule.yml`，**不要**再加獨立 refresh job。
