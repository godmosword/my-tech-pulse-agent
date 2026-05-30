# Fiscal boundary fixtures（MSFT / TSM / GOOGL）

離線測試用 SEC `companyfacts` 片段，鎖定 **非 12 月年結**（MSFT 6 月、GOOGL 9 月）與 **日曆年結 ADR**（TSM）的 XBRL `fy` / `fp` / `end` 語意。對齊 [`docs/superpowers/specs/2026-05-21-us-earnings-column-design.md`](../superpowers/specs/2026-05-21-us-earnings-column-design.md) §6 E6 與 §11 測試策略。

## 目的

1. **禁止日曆推斷**：`fiscal_year` / `fiscal_period` / `period_end` 必須來自 XBRL 列，不可用 `filed` 月份或 `reportDate` 推斷。
2. **Accession strict（D1）**：給定 filing accession 時，若無匹配 `accn` 列 → `normalize_quarter_facts` 回傳 `None`（不 fallback 最新季）。
3. **Backfill 回歸**：`build_report_from_filing` + fixture 可斷言 `quarter_label` 與 headline metrics 對應正確季度。

## Fixture 清單

| 檔案 | CIK | 年結 | 測什麼 |
|------|-----|------|--------|
| `tests/fixtures/sec_companyfacts_nvda_sample.json` | 0001045810 | 1 月 FY | 既有；latest + trend |
| `tests/fixtures/sec_companyfacts_msft_fy_boundary.json` | 0000789019 | **6 月 FY** | 日曆 Q4 ≠ MSFT Q2 |
| `tests/fixtures/sec_companyfacts_tsm_fy_boundary.json` | 0001046179 | **12 月 FY** | ADR；filed 跨年 vs fy |
| `tests/fixtures/sec_companyfacts_googl_fy_boundary.json` | 0001652044 | **9 月 FY** | 日曆 Q4 = GOOGL Q1 |

## MSFT — 6 月 fiscal year

Microsoft FY 以 **6 月** 為年結。日曆 **2024-10-01～2024-12-31** 為 **FY2025 Q2**（不是日曆 Q4）。

### 錨列（Revenues，`accn=0000789019-25-000012`）

| 欄位 | 值 | 說明 |
|------|-----|------|
| `end` | `2024-12-31` | 季度結束日 |
| `fy` | `2025` | XBRL fiscal year |
| `fp` | `Q2` | MSFT 第二 fiscal quarter |
| `filed` | `2025-01-29` | 申報日（日曆 2025，fy 仍 2025） |
| `val` | `69632000000` | 營收 USD（示意） |

### 對照列（FY2025 Q1，勿與 Q2 混淆）

| `end` | `fy` | `fp` | `accn` |
|-------|------|------|--------|
| `2024-09-30` | `2025` | `Q1` | `0000789019-24-000098` |

### 必過斷言

```python
# accession 匹配
meta, _ = fetcher.normalize_quarter_facts(data, accession="0000789019-25-000012")
assert meta["fiscal_year"] == 2025
assert meta["fiscal_period"] == "Q2"
assert str(meta["period_end"]).startswith("2024-12-31")

# 日曆陷阱：filed 在 2025-01，不得把 fy 當成「日曆 2024 Q4」
assert meta["fiscal_period"] != "Q4"

# strict：錯 accession → None
assert fetcher.normalize_quarter_facts(data, accession="0000789019-99-000000") is None
```

## TSM — 日曆 fiscal year（ADR）

台積 ADR 在 SEC 上 **fy 與日曆年一致**（12/31 年結）。重點是 **filed 日可落在下一日曆年**，但 `fy` 仍指 period_end 所在 fiscal year。

### 錨列 Q4 FY2024（`accn=0001046179-25-000004`）

| 欄位 | 值 |
|------|-----|
| `end` | `2024-12-31` |
| `fy` | `2024` |
| `fp` | `Q4` |
| `filed` | `2025-01-16` |
| `val` | `268716000000` |

### 錨列 Q1 FY2025（`accn=0001046179-25-000018`）

| 欄位 | 值 |
|------|-----|
| `end` | `2025-03-31` |
| `fy` | `2025` |
| `fp` | `Q1` |
| `filed` | `2025-04-17` |

### 必過斷言

```python
meta, _ = fetcher.normalize_quarter_facts(data, accession="0001046179-25-000004")
assert meta["fiscal_year"] == 2024  # 不是 filed 年的 2025
assert meta["fiscal_period"] == "Q4"
assert str(meta["period_end"]).startswith("2024-12-31")

meta_q1, _ = fetcher.normalize_quarter_facts(data, accession="0001046179-25-000018")
assert meta_q1["fiscal_year"] == 2025
assert meta_q1["fiscal_period"] == "Q1"
```

## GOOGL — 9 月 fiscal year

Alphabet FY 以 **9 月** 為年結。日曆 **2024-10-01～2024-12-31** 為 **FY2025 Q1**（不是日曆 Q4）。

### 錨列 Q1 FY2025（`accn=0001652044-25-000014`）

| 欄位 | 值 | 說明 |
|------|-----|------|
| `end` | `2024-12-31` | 季度結束日 |
| `fy` | `2025` | XBRL fiscal year |
| `fp` | `Q1` | GOOGL 第一 fiscal quarter |
| `filed` | `2025-02-04` | 申報日（日曆 2025，fy 仍 2025） |
| `val` | `96546000000` | 營收 USD（示意） |

### 對照列 Q2 FY2025（勿與 Q1 混淆）

| `end` | `fy` | `fp` | `accn` |
|-------|------|------|--------|
| `2025-03-31` | `2025` | `Q2` | `0001652044-25-000043` |

### 必過斷言

```python
meta, _ = fetcher.normalize_quarter_facts(data, accession="0001652044-25-000014")
assert meta["fiscal_year"] == 2025
assert meta["fiscal_period"] == "Q1"
assert str(meta["period_end"]).startswith("2024-12-31")
assert meta["fiscal_period"] != "Q4"  # 日曆陷阱

meta_q2, _ = fetcher.normalize_quarter_facts(data, accession="0001652044-25-000043")
assert meta_q2["fiscal_year"] == 2025
assert meta_q2["fiscal_period"] == "Q2"

assert fetcher.normalize_quarter_facts(data, accession="0001652044-99-000000") is None
```

## Submissions archive fixture

| 檔案 | 用途 |
|------|------|
| `tests/fixtures/sec_submissions_with_archive.json` | `filings.recent` + `filings.files[]` |
| `tests/fixtures/sec_submissions_archive_page.json` | 分頁 JSON（舊 10-Q） |

### 行為

- `since=2025-06-01`, `until=2025-06-30` 僅 recent 內一筆 → 1 filing。
- `since=2024-11-01`, `until=2024-11-30` 需拉 archive → 1 filing（2024-11-15 10-Q）。
- Archive 請求 URL：`{SEC_BASE}/submissions/{files[].name}`。

## 維護

- 數字 `val` 可為示意；**fy/fp/end/accn/filed 語意不可改** 除非 SEC taxonomy 變更。
- 測試入口：`tests/test_fiscal_boundary_fixtures.py`、`tests/test_sec_xbrl_accession_strict.py`。
