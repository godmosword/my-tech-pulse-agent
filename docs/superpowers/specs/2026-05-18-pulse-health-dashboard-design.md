# 營運摘要頁（Pulse Health）設計規格

**狀態**：已定稿（brainstorming 第 1～3 段已獲同意）  
**日期**：2026-05-18  
**範圍**：MVP — 僅讀、非工程向、資料以 Firestore 已交付內容為準；不修改 pipeline 產物格式。

---

## 1. 背景與目標

### 1.1 問題

編輯／營運同事需要快速了解「讀者端已上線內容」是否健康、數量與品質分佈，而不必閱讀 Cloud Run log、原始 JSON 或後台環境變數。

### 1.2 目標（MVP）

- 在既有 **Next.js dashboard** 內新增一頁 **「營運摘要」**，與 digest 使用 **同一資料契約**（Firestore `memory_items`，見 `docs/PORTAL_CONTRACT.md` 與 `dashboard/lib/types.ts`）。
- **純瀏覽**：無觸發 pipeline、無改設定、無寫入。
- **閱聽人**：非工程；用語避免 pipeline／GCP 專有名詞為主標。
- **進站方式**：與現站相同 — **同一網域、同一套 Basic Auth**（`dashboard/middleware.ts` 行為不變；本頁不屬 `api/revalidate` 例外）。

### 1.3 非目標（MVP 明確排除）

- 不顯示 Cloud Run job 步驟、Apify timeout 原文、stack trace。
- 不依賴 `output/*.json` 或 `scoring/cache`（本 repo 亦無後者作為儀表板契約）。
- 不新增「手動重跑」「改 `MAX_*`」等變更系統行為的 UI。

---

## 2. 架構與資料流

### 2.1 路由與權限

| 項目 | 決策 |
|------|------|
| URL path | `/health`（程式與連結用）；頁面 **`<title>` 與主標** 使用 **「營運摘要」**。 |
| 動態渲染 | 與首頁類似，使用 **`dynamic = "force-dynamic"`**（或等價策略），避免無憑證 build 階段存取 Firestore 失敗。 |
| 權限 | 沿用全站 **Basic Auth**（`DASHBOARD_PUBLIC_READ` 關閉時）；不為本頁新增公開 API。 |

### 2.2 資料來源與聚合

- **唯一來源**：Firestore collection（與 `listLatestItems` / `TECH_PULSE_FIRESTORE_COLLECTION` 一致）。
- **伺服端聚合**：在 **Server Component**（或僅伺服端呼叫的 helper）內，於一次（或有限次）查詢取得最近 **N 筆**（建議 **80～200**，與首頁數量級一致或可設定常數），於記憶體計算：
  - 最近一筆 **`delivered_at`**（作為「內容最近一次上線」）。
  - 近 **24 小時**、近 **7 天** 內 `delivered_at` 落在區間內的筆數。
  - 依 **`kind`** 分組筆數，映射為對外標籤：**快訊**（`instant_summary`）、**深度**（`deep_brief`）、**財報**（`earnings`）。
  - 依 **`score`** 分三檔筆數：**偏高**（≥8）、**中等**（5～7）、**偏低**（&lt;5）；邊界含端點與首頁 digest 討論一致。
- **不暴露**：`score_status` 原始字串（除非未來映射成固定繁中短語；MVP 以分數檔位為主）。

### 2.3 與既有程式邊界

- **重用**：`dashboard/lib/firestore.ts` 的 app 初始化與 `RenderableItem`／`MemoryItemSchema` 解析路徑；可新增 **`summarizeHealth(items: Renderable[]): HealthSummary`** 置於 `dashboard/lib/` 或鄰近模組，僅純函式、可單元測試。
- **不新增** MVP 用的 **`/api/health/*`**（採納 brainstorming 建議路線 1，降低暴露面）。

---

## 3. 使用者介面與用語

### 3.1 頁首

- 主標：**營運摘要**。
- 副標（一句）：說明本頁為「已上線讀者內容」之整理，**非**後台設定頁。

### 3.2 指標列（3～4 張卡片）

- **內容最近一次上線**：顯示最近 `delivered_at`（人類可讀時區；與 `dashboard/lib/digest.ts` 相同，使用 **`DIGEST_HEADER_TIMEZONE`**，預設 `Asia/Taipei`）。
- **近 24 小時／近 7 天上線則數**。
- **類型分佈**：快訊／深度／財報筆數（可加簡短視覺比例）。
- **品質分佈**：三檔（偏高／中等／偏低）筆數 + 綠／橙／紅；小字註：**分數由編輯流程自動標記，僅供內部參考**。
- 若樣本極少：卡片區可加灰色提示「樣本較少，僅供參考」（門檻可由實作訂為例如總筆數 &lt; 5）。

### 3.3 列表區

- 欄位：**標題**、**來源名稱**、**品質**（檔位色 + 分數數字）、**上線時間**。
- **連結至 `/item/[id]`**：**可選**；MVP 若實作則與全站 auth 規則一致。規格預設 **允許** 實作連結以利核對呈現；若產品希望更保守可於實作 PR 改為純文字。

### 3.4 導覽

- 在 **`NavRail`** 與 **`MobileMasthead`** 新增連結 **`/health`**，文案 **「營運摘要」**（與 Today、Archive 並列）。

### 3.5 視覺

- 沿用既有 **Tailwind** 與版型（`Hairline`、`Kicker` 等可選用，不強制新設計系統）。

---

## 4. 錯誤、空狀態與無障礙

| 情境 | 行為 |
|------|------|
| 無任何已交付項目 | 整頁說明「尚無上線紀錄」，不猜測技術原因。 |
| Firestore 讀取失敗 | 短句「暫時無法載入」+ 引導使用者以瀏覽器重新整理；不顯示 stack。 |
| 色塊傳達品質 | 除顏色外需有 **文字檔位**（符合對色弱友善的最低要求）。 |

---

## 5. 測試

| 層級 | 內容 |
|------|------|
| 手動 | 有資料、無資料、憑證缺失（若與首頁相同則對齊預期）下版面與文案。 |
| 自動（可選） | 若有 E2E：新增「`/health` 回傳 200」；**不**列為 MVP 阻擋條件。 |
| 單元（建議） | `summarizeHealth` 對固定輸入的聚合與分檔正確性。 |

---

## 6. 後續擴充（非 MVP）

- **系統執行視角**：Cloud Run 最後一輪、各 stage 狀態 — 需 pipeline 寫入摘要或接 Logging；與本頁「讀者內容」**分區**展示，避免非工程混淆。
- **自動更新**：長開分頁時輪詢 — 可引入 `GET /api/health/summary` + 前端 fetch；屆時需重審 middleware 與快取。

---

## 7. 自我檢查紀錄（spec review）

- **占位符**：無 TBD。列表連結為「可選」已寫明預設允許實作。
- **一致性**：資料來源僅 Firestore；與第 1 段架構及排除項目一致。
- **範圍**：單一功能（一頁 + 導覽 + 可選小 helper）；未捆綁 pipeline 改動。
- **歧義**：`delivered_at` 可能為 null 的項目 — 實作時應排除在「上線」統計外或列入說明；規格要求實作於 helper 內 **明確定義**（建議：**無 `delivered_at` 者不計入「已上線」筆數與列表預設列**）。

---

## 8. 核准紀錄

- 第 1 段（架構與資料流）：已同意。
- 第 2～3 段（畫面／用語／錯誤／測試／後續）：已同意。

下一步：實作前請另以 **writing-plans** 產出實作計畫；**本檔不取代** `docs/PORTAL_CONTRACT.md`，若欄位語意變更需同步該契約。
