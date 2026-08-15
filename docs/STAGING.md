# Staging 環境（語意 prefilter 實測）

## 目的

在 **不影響 production Telegram** 的前提下啟用 `SEMANTIC_PREFILTER_ENABLED`，並從 `pipeline_run_summary` 觀測：

- `semantic_prefilter_dropped` — 本批被語意去重丟棄的篇數
- `articles_after_scoring` — 打分後進入後續流程的篇數

## 啟用方式

本機或手動 `workflow_dispatch` 設環境變數（擇一即可）：

| 變數 | 值 | 說明 |
|------|-----|------|
| `TECH_PULSE_ENV` | `staging` | **推薦**：自動開啟語意 prefilter |
| `SEMANTIC_PREFILTER_ENABLED` | `1` | 強制開啟（production 亦生效，慎用） |

可選調參：

- `SEMANTIC_PREFILTER_THRESHOLD`（預設 `0.85`）

**不要**與 production 共用 `TELEGRAM_CHANNEL_ID`。

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
