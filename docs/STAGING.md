# Staging 環境（語意 prefilter 實測）

## 目的

在 **不影響 production** 的前提下，於 staging Cloud Run Job 啟用
`SEMANTIC_PREFILTER_ENABLED`，並從 `pipeline_run_summary` 觀測：

- `semantic_prefilter_dropped` — 本批被語意去重丟棄的篇數
- `articles_after_scoring` — 打分後進入後續流程的篇數

## 啟用方式

設定 Cloud Run Job 環境變數（擇一即可）：

| 變數 | 值 | 說明 |
|------|-----|------|
| `TECH_PULSE_ENV` | `staging` | **推薦**：自動開啟語意 prefilter |
| `SEMANTIC_PREFILTER_ENABLED` | `1` | 強制開啟（production 亦生效，慎用） |

可選調參：

- `SEMANTIC_PREFILTER_THRESHOLD`（預設 `0.85`）

## 觀測

每次 run 結尾日誌含 JSON：

```json
{
  "semantic_prefilter_enabled": true,
  "semantic_prefilter_dropped": 2,
  "tech_pulse_env": "staging",
  "newsapi_fetched": 5
}
```

## GitHub Actions

若 repository 設有 `vars.CLOUD_RUN_STAGING_JOB`，`ci.yml` 的 `deploy-staging` job 會在
`main` push 後部署同一映像並帶上 `TECH_PULSE_ENV=staging`。

未設定該 variable 時，job 會自動 skip。
