# 開發流程（Development Workflow）

本文件定義 **人類與 AI agent** 在本 repo 的預設工作方式。與 [Karpathy 準則](../AGENTS.md) 並用；衝突時以本文件的 **Git／文件同步／pipeline 確認** 規則為準。

## 1. 段落完成 → 直接上 `main`

**「段落」**：一個可獨立描述、可驗證的工作單元，例如：

- 單一 bugfix 或單一 UI 區塊
- 一組相關測試通過的 refactor
- 一份文件或設定檔的完整更新

段落完成且驗證通過後：

1. `git checkout main && git pull origin main`
2. 提交變更（訊息用完整句子，說明「做了什麼／為什麼」）
3. **同一輪**更新 [`CHANGELOG.md`](../CHANGELOG.md) 與 [`TODOS.md`](../TODOS.md)（可與功能同一 commit，或緊接著的 docs commit）
4. `git push origin main`

不需為例行段落另開長壽命 feature branch；`main` 上的 push 會觸發 [CI and Deploy](../.github/workflows/ci.yml)。

### CHANGELOG 怎麼寫

- 進行中的工作寫在 `## [Unreleased]`（Added / Changed / Fixed）
- 段落對外可視為一個里程碑時，可另開版本標題（例如 `## [0.2.1] — YYYY-MM-DD`）並清空 `[Unreleased]`

### TODOS 怎麼寫

- 完成的段落：在「近期已完成」打 `[x]`，或移到已完成小節並簡述
- 新發現的工作：加入「進行中」或「積壓」
- 勿讓 TODOS 與 CHANGELOG 長期矛盾

## 2. 動到 pipeline → 先跟維護者確認

下列路徑或行為視為 **pipeline 改動**。在 **實作、commit、push `main` 之前** 必須先向 repo 維護者說明並取得同意（PR 描述、issue、或對話中明確「可以改」）：

| 範圍 | 路徑／觸發點 |
|------|----------------|
| 編排 | `pipeline/`、`main.py` |
| Agent / LLM | `agents/`、`llm/` |
| 來源與評分 | `sources/`、`scoring/` |
| 送報 | `delivery/`（含 Telegram 格式、ISR webhook） |
| 型別與設定 | `pyproject.toml` / `setup.cfg` 中影響 runtime 的依賴；根目錄 `.env.example` 中 **pipeline 執行**相關變數 |
| 營運腳本 | `scripts/preflight.py` 等會改變 **生產跑法或 Firestore 寫入** 的腳本 |
| 部署契約 | `.github/workflows/ci.yml` 中 **deploy 步驟**（映像、env、Cloud Run 參數） |

**不需事先確認**（仍須段落完成後更新 CHANGELOG／TODOS 並 push `main`）：

- `dashboard/`（Next.js 讀者端）
- `docs/`、`README.md`、`TODOS.md`、`CHANGELOG.md`
- `tests/`（除非測試改動 **順帶修改** 上述 pipeline 行為）
- 純註解、不影響執行路徑的排版

**灰色地帶**：`tests/` 與 pipeline 檔案同一 PR 時，以 pipeline 規則為準——先確認再 push。

### 確認時應提供

1. 要改的檔案與行為差異（一句話 + 關鍵 env／成本影響）
2. 如何驗證（例如 `pytest -q`、dry-run、staging 觀察欄位）
3. 是否會觸發 Cloud Run 自動 deploy（`main` push 預設會）

維護者同意前：可調查、寫草稿、開 draft PR，**不要** push 會改變 production pipeline 的 commit 到 `main`。

## 3. 建議的段落收尾檢查

```bash
pytest -q                    # pipeline / 共用邏輯
# dashboard 變更時：
cd dashboard && pnpm build   # 或專案慣用的 build
python scripts/preflight.py  # 僅在動到 production 設定或 deploy 相關時
```

推送前確認：

- [ ] `CHANGELOG.md` 已反映本段落
- [ ] `TODOS.md` 已勾選或新增後續項
- [ ] 若為 pipeline 改動 → 已取得維護者確認

## 4. 相關文件

- [README.md](../README.md) — 架構與環境變數
- [CHANGELOG.md](../CHANGELOG.md) — 版本紀錄
- [TODOS.md](../TODOS.md) — 待辦與路線圖
- [dashboard/README.md](../dashboard/README.md) — 前端部署
- [.cursor/rules/workflow.mdc](../.cursor/rules/workflow.mdc) — Cursor agent 自動套用摘要
