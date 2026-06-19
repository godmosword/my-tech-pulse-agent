# CLAUDE.md

本檔案定義此專案中 AI agent 的工作規範。每次任務前請先閱讀，並在工作過程中遵守。

## 1. 溝通與回報
- 一律使用繁體中文回報。
- 只給差異摘要與重點，不要貼整個檔案內容。
- 不確定的事先問，不要自行猜測後直接修改。
- 不要宣稱「完成」或「完美」，改用「完成定義」逐項對照回報通過與否。
- 複雜任務先提計畫並等確認再動手，不要一次大量修改。

## 2. 修改原則
- 不改變對外行為：對外 API、介面契約、函式簽名、回傳格式維持不變，除非明確被要求。
- 一次只做一類改動（清理、重構、修 bug 不要混在同一批）。
- 刪除任何檔案、函式、import 前，先確認沒有動態引用（字串 import、反射、設定檔指定、環境變數路徑等）。
- 不確定能否安全刪除的，列出來問，不要直接刪。
- 不要用 eslint-disable、type: ignore、any 等手段逃避檢查；有必要時須說明理由並徵得同意。

## 3. 程式碼品質
- 同一行為只有一處實作，重複邏輯收斂為共用函式／模組。
- 函式單一職責，避免過度巢狀，過長函式應拆分。
- 命名清楚一致，遵循專案既有風格。
- 移除死碼：未使用的 import、變數、函式、檔案、被註解掉的舊程式碼。
- 移除未使用的相依套件（對照 `dashboard/package.json`、`pyproject.toml`）。
- 所有非同步流程都要有錯誤處理，不可有未捕捉的 Promise / 例外。
- 注意邊界條件與空值處理。

## 4. 驗證（每次改動後必跑）

在專案根目錄執行。未全部通過前，不得回報任務完成。

**Python（pipeline / agents / sources / scoring 等）**

```bash
ruff check .
pyright
vulture . scripts/vulture_whitelist.py --exclude dashboard,node_modules,.venv,venv --min-confidence 80
pytest -q --cov=agents --cov=sources --cov=scoring --cov=pipeline --cov=delivery --cov=llm --cov=backtest --cov-fail-under=62
```

**Dashboard（Next.js，`dashboard/`）**

```bash
cd dashboard && npm run lint && npm run typecheck && npm run test
```

對照標準：
- **Lint**：`ruff check .` 零錯誤；`npm run lint`（ESLint）零錯誤、零警告
- **Type check**：`pyright` 全綠（核心套件 `sources`/`scoring`/`pipeline`/`delivery`/`llm`/`backtest`/`agents`，`typeCheckingMode: basic`，見 `pyrightconfig.json`）；`npm run typecheck`（`tsc --noEmit`，strict）全綠
- **Dead code**：`vulture` 全綠（含 `scripts/vulture_whitelist.py`）
- **測試**：`pytest` 全數通過，核心套件 coverage ≥ 62%；`vitest run` 全數通過
- 若無測試，列出建議補測試的關鍵路徑，不要自行大量新增

## 5. 完成定義（Definition of Done）

任務視為完成須逐項對照並回報通過與否：

1. **Lint 零錯誤、零警告** — `ruff check .`；`cd dashboard && npm run lint`
2. **Type check 全綠** — `pyright`（Python 核心套件 sources/scoring/pipeline/delivery/llm/backtest/agents）；`cd dashboard && npm run typecheck`（TypeScript strict）
3. **既有測試全數通過，覆蓋率不低於基準** — `pytest -q --cov=... --cov-fail-under=62`；`cd dashboard && npm run test`
4. **無未使用的 import / 變數 / 函式 / 檔案 / 相依套件** — 含 `vulture` 掃描
5. **無重複邏輯**
6. **所有 async 流程皆有錯誤處理**，無未捕捉的 Promise / 例外
7. **對外介面行為未改變**
8. **改動範圍與原任務一致**，無夾帶非預期修改

## 6. Token 效率
- 不要重複讀取已在 context 中的檔案。
- 大檔案先看結構或目標區段，不要整檔載入。
- 善用 `.cursorignore` / `.gitignore` 排除 build 產物、依賴目錄、log、快取。
- 回報與計畫力求精簡，不重述已知資訊。

## 7. 安全
- 不得將密鑰、token、密碼、API key 寫進程式碼或 commit。
- 機敏設定走環境變數 / `.env`，且 `.env` 須在 `.gitignore` 中。
- 發現既有程式碼有寫死的機敏資訊，立即回報。

## 8. 持續改進
- 每當發現 agent 重複犯的錯誤，把對應規則補進本檔案或新增對應 lint rule。
- 本檔案是專案規範的單一真實來源，隨專案演進持續更新。

## 9. Agent 編排（Cursor）

複雜任務可用 slash 指令進入 Leader 編排模式（Meta 流程 + 本 repo Domain 紅線／驗證矩陣）：

- 編排流程：[`docs/AGENT-WORKFLOW.md`](docs/AGENT-WORKFLOW.md)
- 專案 Domain（Bootstrap、紅線、驗證、Ship）：[`docs/AGENT-DOMAIN.md`](docs/AGENT-DOMAIN.md)
- 指令：`/agent-plan`（Plan + 雙審）、`/agent-action`（依 Approved Plan 派工）
