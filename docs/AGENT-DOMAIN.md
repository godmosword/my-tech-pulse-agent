# Agent Domain Sheet — tech-pulse

> `/agent-plan` 與 `/agent-action` 會讀此檔的 Bootstrap、紅線、驗證矩陣。  
> Meta 流程見 [`AGENT-WORKFLOW.md`](AGENT-WORKFLOW.md)。

---

## 專案識別

| 欄位 | 值 |
|------|-----|
| **專案名稱** | tech-pulse（my-tech-pulse-agent） |
| **主要技術棧** | Python 3.11 pipeline（Gemini agents、Firestore）+ Next.js dashboard（Vercel） |
| **回應語言** | 繁體中文 |

---

## Bootstrap（Plan / Action 必讀）

大任務或不熟模組時依序讀：

| 優先 | 檔案 | 用途 |
|------|------|------|
| 1 | `CLAUDE.md` / `AGENTS.md` | 完成定義、驗證命令、修改原則 |
| 2 | `docs/WORKFLOW.md` | Git／段落 ship、**pipeline 改動須先確認** |
| 3 | `README.md` | 架構概覽、建置、CI 對齊 |
| 4 | `TODOS.md` / `CHANGELOG.md` | 待辦與已 ship（**TODOS 檔首可能落後**，以 CHANGELOG／程式為準） |

### 依任務加讀

| 任務類型 | 加讀 |
|----------|------|
| Pipeline／agents／LLM | `pipeline/`、`agents/`、`llm/`、`main.py` |
| 評分／Firestore 寫入 | `scoring/`、`docs/PORTAL_CONTRACT.md` |
| 送報／Telegram | `delivery/`、`message_formatter.py` |
| Earnings v3 | `docs/EARNINGS_PORTAL.md`、`docs/EARNINGS_ENV.md` |
| Dashboard | `dashboard/README.md` |
| Portal 整合 | `docs/QSILICON_INTEGRATION.md`、`docs/PORTAL_CONTRACT.md` |
| 本地開發 | `docs/LOCAL_DEV_SETUP.md` |

---

## 紅線（Plan 違反 → CRITICAL）

| 紅線 | 說明 |
|------|------|
| **Pipeline 未核准** | 動到 `pipeline/`、`main.py`、`agents/`、`llm/`、`sources/`、`scoring/`、`delivery/`、production 相關 `scripts/`、deploy 步驟或 pipeline 用 `.env.example` 變數 → **須先取得維護者同意**（見 `docs/WORKFLOW.md` §2） |
| **Portal 契約** | 不可破壞 [`docs/PORTAL_CONTRACT.md`](PORTAL_CONTRACT.md) 對外語意；Firestore 欄位 alias 以 `scoring/memory_store.py` 為準，不重命名既有 pipeline 欄位 |
| **Earnings 數據來源** | SEC XBRL 為 actual 真值；Finnhub/FMP 為 enrichment，預設 off；禁止 LLM 捏造財報數字 |
| **Telegram HTML** | 動態文字須 escape；`parse_mode=HTML`；chunk ≤ 4096 |
| **機敏資訊** | 禁止 commit API key、token、`.env` |
| **對外介面** | 未明確要求不得改 API 契約、函式簽名、回傳格式 |

---

## 驗證矩陣

依 **變更觸及面** 跑最小集合（未全綠不得宣稱完成）：

| 觸及 | 必跑（最小） |
|------|----------------|
| **Python 核心（預設）** | `ruff check .` + `pyright` + `vulture . scripts/vulture_whitelist.py --exclude dashboard,node_modules,.venv,venv --min-confidence 80` + `pytest -q --cov=agents --cov=sources --cov=scoring --cov=pipeline --cov=delivery --cov=llm --cov=backtest --cov-fail-under=62` |
| **Dashboard** | `cd dashboard && npm run lint && npm run typecheck && npm run test` |
| **Production 設定／deploy** | `python scripts/preflight.py`（僅在動到 production 設定或 deploy 相關時） |

對齊 CI：`.github/workflows/ci.yml` 的 `test` 與 `dashboard` jobs。

---

## Protected paths / models

| 路徑／領域 | 要求 |
|------------|------|
| `pipeline/`、`agents/`、`llm/`、`scoring/`、`delivery/`、`sources/`、`main.py` | 須維護者核准後才改；Leader 或 L3；必跑完整 Python 驗證矩陣 |
| `docs/PORTAL_CONTRACT.md` 語意、`scoring/memory_store.py` 寫入 | 禁止 haiku 單獨改；必對照 Portal 整合測試／契約 |
| `.github/workflows/ci.yml` deploy 步驟 | 維護者核准；必跑 preflight |

---

## Docs sync（可見行為變更時）

| 變更類型 | 同步 |
|----------|------|
| 使用者可見行為 | `CHANGELOG.md`（`[Unreleased]` 或版本節） |
| 待辦／完成度 | `TODOS.md` |
| 指令／導航 | `README.md` / `CLAUDE.md` |

段落完成 push `main` 前，CHANGELOG 與 TODOS 須同一輪更新（見 `docs/WORKFLOW.md`）。

---

## Ship 政策

| 情境 | 行為 |
|------|------|
| 預設 | **不** commit / push |
| 使用者說「commit」 | 只 stage **本次相關檔**；禁止 `git add -A` |
| 段落完成／使用者說「ship／push main」 | scoped tests 全綠 → `git push origin main`（**pipeline 改動須已核准**） |
| branch protection | 失敗時報錯，改人類處理 |
| 完整 VERSION ship | gstack `/ship` |

**注意**：`main` push 會觸發 Cloud Run 自動 deploy（CI and Deploy workflow）。

---

## 專案反模式

| 反模式 | 為什麼 |
|--------|--------|
| 未核准就 push pipeline | 直接改 production 跑法與 Firestore 寫入 |
| 只跑 pytest 不跑 ruff/pyright | 與 CI 不一致，merge 後才爆 |
| Dashboard 變更只跑 Python 測試 | dashboard job 獨立，會漏 lint/typecheck |
| 跳過 CHANGELOG/TODOS | 違反段落完成定義 |

---

## 修訂紀錄

| 日期 | 說明 |
|------|------|
| 2026-06-19 | 初版 Domain sheet（agent-orchestration bootstrap） |
