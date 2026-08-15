# 語義去重 Rollout Runbook（SEMANTIC_DUP_DROP_ENABLED）

跨 run 的語義去重程式碼已完整實作並以 feature gate 保護。本文件描述如何**安全上線**：
先以 shadow 模式觀測「若開啟會丟多少筆」，確認比例合理且無誤判後，再翻旗。

## 0. 兩套語義去重（勿混淆）

| 機制 | 旗標 | 範圍 | 觀測指標 |
|------|------|------|----------|
| `_semantic_prefilter` | `SEMANTIC_PREFILTER_ENABLED` | **同一批** extraction 前，省 LLM token | `semantic_prefilter_dropped` |
| `_apply_memory_context` | `SEMANTIC_DUP_DROP_ENABLED` | **跨 run** 對 sqlite embeddings | `semantic_dup_*`（本文件主題） |

## 1. 前置

1. 確認 `STATE_BACKEND=sqlite` 且 `state/dedup.sqlite` 會被 GHA commit 回來（embeddings 存在 `article_embeddings`）。
2. 確認 `MEMORY_ENABLED=1`，讓每日 run 持續 archive 摘要 embedding（建議累積 ≥ 7 天再評估）。

## 2. Shadow 觀測（旗標仍關閉）

維持 `SEMANTIC_DUP_DROP_ENABLED=0`，可選 `SEMANTIC_DUP_SHADOW_LOG=1` 以逐筆記錄候選。
> 注意：這些旗標在 module import 時讀取，**改 env 後下一輪 `schedule.yml` 才生效**。

每日 run 的 `pipeline_run_summary`（**primary source**；digest snapshot funnel 僅在 delivery 成功時寫入，僅供輔助）會包含：

```json
{
  "semantic_dup_drop_enabled": false,
  "semantic_dup_checked": 18,      // 成功進入 memory search 的摘要數（分母）
  "semantic_dup_would_drop": 2,    // 近重複候選數（distance <= 0.12）
  "semantic_dup_dropped": 0        // 實際丟棄（旗標關閉時為 0）
}
```

判讀：
- `checked > 0, would_drop = 0`：memory 有資料但本輪無近重複 —— 正常。
- `checked = 0`：memory search 未真正執行 —— 檢查 `state/dedup.sqlite` 是否有 `article_embeddings`，以及 `MEMORY_ENABLED=1`。
- `would_drop / checked` 即潛在丟棄比例，用於決策。

逐筆候選（`SEMANTIC_DUP_SHADOW_LOG=1`）：
```
Semantic dup candidate: '<title>' distance=0.07<=0.12 nearest='<prior title>' drop_enabled=False
```
抽查這些候選是否為**真重複**（同事件改寫）還是**誤判**（同 ticker 不同新聞、標題相近但內容不同）。

## 3. 決策門檻（建議）

觀測 ≥ 7 天後，全部成立才翻旗：
- [ ] 索引 READY，期間無 missing-index warning（`checked` 穩定 > 0）。
- [ ] `would_drop / checked` 落在預期區間（例如 < 15%；過高代表 threshold 太鬆）。
- [ ] 人工抽查 ≥ 20 筆候選，誤判率可接受（建議 0 誤判；偶發可調 `SEMANTIC_DUP_DISTANCE_THRESHOLD`）。

## 4. 翻旗上線

設 `SEMANTIC_DUP_DROP_ENABLED=1` 並重新部署/重啟 Job。之後 `semantic_dup_dropped` 應 ≈ `semantic_dup_would_drop`。

## 5. 回滾

設 `SEMANTIC_DUP_DROP_ENABLED=0` 重啟即停止丟棄（gate 永久保留）。若誤判偏高，調高 `SEMANTIC_DUP_DISTANCE_THRESHOLD`（更嚴）後重回 shadow 觀測。
