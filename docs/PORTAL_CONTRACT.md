# Portal Integration Contract

**`schema_version`**: `v1`

本文件定義 Portal（例如 investment-ai-agent 的 `api_routers/news.py`）可讀取的 Firestore collection 語意欄位與實體對照。tech-pulse 維持 headless pipeline；**實際寫入欄位**以 [`scoring/memory_store.py`](../scoring/memory_store.py) 為準。

**預設 collection 名稱**：`tech_pulse_memory_items`（由 `FIRESTORE_COLLECTION_PREFIX` + `_memory_items` 組成；預設前綴為 `tech_pulse`）。若部署變更前綴，實際 collection 名會變，請與 `TECH_PULSE_FIRESTORE_COLLECTION` 對齊。

## Collection: `tech_pulse_memory_items`

以下為 Portal **對外語意**欄位。實體欄位名稱或語意若與 pipeline 不一致，見下方「實體欄位對照（alias）」；**不重命名 pipeline 既有欄位**。

| 欄位 | 型別 | 必填 | 說明 |
|------|------|------|------|
| `id` | string | ✅ | Firestore document ID |
| `title` | string | ✅ | 文章標題 |
| `summary` | string | ✅ | Gemini 生成的 1–3 句摘要（或 deep brief 合併正文，見 alias） |
| `source_url` | string | ✅ | 原文 URL（Portal 強制顯示；earnings 列可能為空字串） |
| `source_name` | string | ✅ | 來源域名（如 `techcrunch.com`） |
| `published_at` | timestamp | ✅ | 文章發佈時間（UTC）；deep brief／earnings 列可能為 null，Portal 應容錯 |
| `themes` | string[] | ✅ | 主題標籤（如 `["AI", "Semis"]`）；見 alias — pipeline 目前未寫入陣列 |
| `confidence` | float | ✅ | 信心相關數值語意；見 alias — 實體為 `score` 等，非 0.0–1.0 機率欄 |
| `pillar` | string | ✅ | 如 `AI` / `Semis` / `Crypto` / `Macro` 語意；見 alias — 實體為 `category`，枚舉與此表非一對一 |
| `deep_brief` | string | ❌ | 長篇深度分析；見 alias — 無獨立欄位，`kind == deep_brief` 時內容在 `summary` |
| `embedding` | vector | ❌ | Gemini 向量（Portal 不讀，supply chain 用） |
| `delivered_at` | timestamp | ❌ | Telegram 送出／歸檔時間 |

## 實體欄位對照（alias）

tech-pulse 寫入的 document **body** 鍵（見 `FirestoreMemoryService.archive_*`）：

| 實體欄位 | 說明 |
|----------|------|
| `item_id` | 與 **document id** 相同（SHA256）；Portal 的 `id` 請讀 `doc.id` 或 `item_id` |
| `title` | 對應合約 `title` |
| `summary` | 對應合約 `summary`；`kind == "deep_brief"` 時為 insight + tech_rationale + implication 合併字串（長度受 InsightBrief 約束，非獨立「≥800 字」長欄） |
| `source_url` | 對應合約 `source_url` |
| `source_name` | 對應合約 `source_name` |
| `published_at` | 對應合約 `published_at`；`instant_summary` 通常有值，`deep_brief`／`earnings` 常為 null |
| `delivered_at` | 對應合約 `delivered_at` |
| `category` | **對應合約 `pillar` 的實體載體**，語意依 `kind` 而變：`instant_summary` 為 extractor 類別（如 `product_launch`、`funding`、`research`、`other` 等）；`deep_brief` 為 `ai` / `semiconductor` / `crypto` / `other`；`earnings` 為字串 `earnings`。與合約表列 `AI`/`Semis`/`Macro` 等 **非一對一**，由 Portal 自行映射或顯示 raw 值 |
| `entity` | 額外欄位；instant 為實體名，deep 常為 title |
| `score` | **對應合約 `confidence` 的數值載體之一**：Flash 文章分數（約 0–10 量級，見 scorer），**不是** 0.0–1.0 的 Gemini 機率 |
| `score_status` | 字串（如 `ok`、`fallback`）；deep／earnings 上可承載 `high`/`medium`/`low` 類語意，與數值 `score` 並存 |
| `kind` | `instant_summary` \| `deep_brief` \| `earnings`；Portal 可依此區分深度稿與快訊 |
| `embedding` | 向量；Portal 可不讀 |
| `expires_at` | TTL 用；Portal 可忽略 |

**`themes`（string[]）**：pipeline **目前未寫入**此鍵。Portal 可暫以 `category` 單值包成單元素陣列、或回傳 `[]`，直到未來以 **additive** 方式新增欄位。

**`deep_brief`**：無獨立 Firestore 鍵；當 `kind == "deep_brief"` 時視 `summary` 為深度內文。

## 穩定性保證

- **breaking change 禁止**：不重命名以上 pipeline 已寫入、且本合約列為對外語意對應的實體鍵（如 `title`、`summary`、`source_url`、`source_name`、`published_at`、`delivered_at`、`category`、`score`、`embedding`、`kind` 等），除非同步發布新 `schema_version` 與 Portal 遷移計畫。
- **新增欄位**：additive only；Portal 應忽略未知欄位。
- **版本號**：本文件頂部 `schema_version`；目前為 **`v1`**。

## Portal 讀取權限

Portal API（`api_routers/news.py`）使用 **read-only service account**：

- `roles/datastore.viewer` 即可
- 不需要 write 權限
- SA email 由 investment-ai-agent 維護方提供

## Preflight：確認實際鍵名

在具 GCP Application Default Credentials 的環境執行：

```bash
python -c "
from google.cloud import firestore
db = firestore.Client()
docs = db.collection('tech_pulse_memory_items').limit(1).get()
for d in docs:
    print(d.to_dict().keys())
"
```

若無文件或無憑證會得到空輸出或錯誤；與本節「實體欄位對照」不一致時，**只更新本合約文件**，不改 tech-pulse pipeline。

**單筆樣本觀測（preflight）**：`category`, `delivered_at`, `embedding`, `entity`, `expires_at`, `item_id`, `kind`, `published_at`, `score`, `score_status`, `source_name`, `source_url`, `summary`, `title`（與 `memory_store` 寫入一致；`themes` 等欄位未出現）。
