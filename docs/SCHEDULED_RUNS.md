# Pipeline 自動排程

pipeline 由 GitHub Actions 直接跑 `python main.py`，寫入 `dashboard/data` 與 `state/dedup.sqlite` 後 commit，Vercel 重建 dashboard。

| 項目 | 值 |
|------|-----|
| Workflow | `.github/workflows/schedule.yml` |
| Cron | `20 23 * * *` UTC（07:20 Asia/Taipei） |
| 開關 | repo variable `PIPELINE_SCHEDULE_ENABLED=true`（手動 `workflow_dispatch` 不受限） |
| 防重疊 | `concurrency: pipeline-run` |

GitHub schedule 閒置 60 天會停；可用手動 dispatch 喚醒。

## 必備 secrets

`OPENAI_API_KEY`、`SEC_USER_AGENT`。
可選：`NEWSAPI_KEY`、`APIFY_API_KEY`、`FINNHUB_API_KEY`、`FMP_API_KEY`、`FRED_API_KEY`。

## 切換檢查

- [ ] 設 `PIPELINE_SCHEDULE_ENABLED=true`
- [ ] 手動 Run workflow 一次，確認 `dashboard/data` commit 且 Vercel 重建成功
- [ ] `main` 若有 branch protection，放行 `github-actions[bot]` 或改用 PAT

Invest artifacts（`track_record.json` / `invest_brief.json`）已併進同一支 workflow，不再另開 refresh job。
