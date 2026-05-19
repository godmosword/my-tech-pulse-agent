# TODOS

工程待辦與路線圖（非 CI 自動維護；重大里程碑請同步 [`CHANGELOG.md`](CHANGELOG.md)）。開發節奏見 [`docs/WORKFLOW.md`](docs/WORKFLOW.md)。

## 近期已完成（0.2.0）

- [x] Next.js Dashboard MVP（Today / Archive / Item）+ Vercel 部署文件
- [x] 公開讀模式（摘要 SEO + cookie 門控 `zh_body`）
- [x] Pipeline 寫入 `zh_summary` / `zh_body`；Portal 合約 [`docs/PORTAL_CONTRACT.md`](docs/PORTAL_CONTRACT.md)
- [x] Telegram 改為 HTML `parse_mode` + `zh_summary` 卡片
- [x] 送報後 ISR webhook（`DASHBOARD_REVALIDATE_*`）
- [x] Heuristic 三大主題白名單（AI / 半導體 / 加密）
- [x] Heuristic edge-case 測試 + 複合品質閘（主題 + 深度/具體數據）
- [x] GDELT 歷史回填腳本 `scripts/backfill_gdelt.py`

## 進行中 / 下一步

- [ ] **回填驗證**：對目標日期區間跑 `backfill_gdelt` dry-run → `--commit`，抽查 `/archive` 日桶與 Firestore `delivered_at`
- [ ] **舊稿繁中**：既有 `memory_items` 無 `zh_body` 者，評估批次重跑 extractor 或接受英文 fallback
- [ ] **`.env.example`**：補上 `DASHBOARD_REVALIDATE_URL` / `DASHBOARD_REVALIDATE_TOKEN` / `DASHBOARD_REVALIDATE_TIMEOUT` 說明（pipeline 端）
- [ ] **合約 `themes[]`**：pipeline 仍以 `category` 單值為主；若 Portal 需要陣列，additive 寫入 `themes` 並更新合約

## 積壓（Backlog）

- [ ] **Heuristic 通過率觀測**：上線後從 pipeline 日誌聚合 `gate:needs_depth_or_specifics` 與 dropped 計數，評估是否過嚴
- [ ] **Canonical digest snapshot**：若 TS/Python 雙端維護 `digest.ts` / `message_formatter.py` 成本過高，寫入 `tech_pulse_digests/{id}` 供 Telegram + Dashboard 共用
- [ ] **Semantic prefilter rollout**：`SEMANTIC_PREFILTER_ENABLED=1` 在 staging 量測召回/成本後再上 production
- [ ] **Semantic dup drop**：`SEMANTIC_DUP_DROP_ENABLED=1` 需 Firestore vector index ready + 觀察誤殺率
- [ ] **Dashboard**：earnings 專欄、全文搜尋、RSS/Atom 對外訂閱
- [ ] **DIGEST_FORMAT v2**：維持 experimental；production 仍鎖 `v1`（CI deploy 預設）

## 維運檢查清單（每次 deploy 後）

1. Cloud Run Job 日誌出現 `pipeline_run_summary` 且 `summaries_count` > 0
2. Telegram 頻道收到 HTML  digest（無 raw `&lt;` 洩漏或截斷標籤）
3. 若已設 webhook：Dashboard `/` 與 `/archive` 在送報後數秒內更新
4. `python scripts/preflight.py` 在與 production 相同 env 下通過
