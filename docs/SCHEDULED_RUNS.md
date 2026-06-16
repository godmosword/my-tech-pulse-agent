# Pipeline 自動排程 Runbook（C1）

pipeline 部署為 Cloud Run **Job**，本身不會自動執行。本文件提供兩條觸發路徑。
**只啟用其中一條**（避免雙倍執行）。

| 路徑 | 可靠度 | 設定成本 | 何時用 |
|------|--------|----------|--------|
| **Cloud Scheduler → Cloud Run Job**（建議 production） | 高（GCP 原生、可精準時區） | 需一次性 IAM/SA 設定 | 正式環境 |
| **GitHub Actions schedule** | best-effort（可能延遲 5–15 分；repo 連續 60 天無活動會停用） | 零新祕密（重用既有 WIF） | 低摩擦、非關鍵時段 |

> 監控：兩條路徑的 `:run`/execute 都只負責「啟動執行」。pipeline 成敗請看
> `pipeline_run_summary` 日誌與失敗告警（`delivery/pipeline_alert.py`）。

---

## 路徑 A：Cloud Scheduler（建議）

> **⚠️ Production 已啟用此路徑，請勿重建。**
> 既有排程：`tech-pulse-daily`（每天 07:20 Asia/Taipei，觸發 `tech-pulse-job:run`，
> OAuth SA `…-compute@developer.gserviceaccount.com`，已驗證成功觸發）。
> **不要**再執行下方 `scripts/setup_cloud_scheduler.sh`——它會另建 `tech-pulse-job-schedule`，
> 造成一天跑兩次。下方指令僅供「從零建立新環境」時參考。
> 檢視既有排程：`gcloud scheduler jobs describe tech-pulse-daily --location asia-east1`。

一次性前置 IAM（不在 GitHub WIF 範圍內）：
- 建一個 service account `SCHEDULER_SA`，授予 Cloud Run Job 的 `roles/run.invoker`。
- 執行者需 `roles/cloudscheduler.admin`；啟用 Cloud Scheduler + Cloud Run API。

建立/更新（idempotent，可先 `DRY_RUN=1` 看指令）：
```bash
GCP_PROJECT_ID=<project> GCP_REGION=<region> CLOUD_RUN_SERVICE=<job-name> \
SCHEDULER_SA=sched@<project>.iam.gserviceaccount.com \
SCHEDULE="0 9 * * 1-5" TIME_ZONE="Asia/Taipei" DRY_RUN=1 \
bash scripts/setup_cloud_scheduler.sh
```
確認指令無誤後拿掉 `DRY_RUN=1` 實際建立。

> Auth：目標是 `run.googleapis.com`（`*.googleapis.com`），Cloud Scheduler 用
> **OAuth**（`--oauth-service-account-email`），不是 OIDC。Cloud Scheduler 支援
> `--time-zone`，故可直接用 Asia/Taipei，無 UTC 換日問題。

停用：`gcloud scheduler jobs pause <job>-schedule --location <region>`。

---

## 路徑 B：GitHub Actions schedule

Workflow：`.github/workflows/schedule.yml`（重用既有 `WIF_PROVIDER`/`WIF_SERVICE_ACCOUNT`
與 `GCP_*`/`CLOUD_RUN_SERVICE` vars，零新祕密）。

啟用步驟：
1. 設 repo variable `PIPELINE_SCHEDULE_ENABLED=true`（未設或非 `true` → 不執行；合進 main 不會意外自動跑）。
2. 視交付時段調整 `schedule.yml` 的 cron。

> Cron 為 **UTC**，且 day-of-week 依 UTC 判斷。對照表：

| 期望（Asia/Taipei，UTC+8） | UTC cron |
|---|---|
| 平日 17:00 | `0 9 * * 1-5` |
| 平日 08:00 | `0 0 * * 1-5` |
| 平日 22:00 | `0 14 * * 1-5` |
| 每日 07:00 | `0 23 * * *`（注意：台北「週一 07:00」對應 UTC「週日 23:00」，day-of-week 會跨日） |

手動觸發（不受 `PIPELINE_SCHEDULE_ENABLED` 限制）：Actions 頁 **Run workflow**（`workflow_dispatch`）。

注意：GitHub `concurrency` 只防 GitHub 內重疊，不防 Cloud Scheduler / 手動 `gcloud` 同時觸發；
排程與 `main` deploy 若同時發生，可能以舊 image 執行（窗口短，可接受或避開 deploy 時段）。

---

## 首次啟用驗證清單

- [ ] 只啟用 A 或 B 之一（互斥）。
- [ ] 手動觸發一次（B：workflow_dispatch；A：`gcloud scheduler jobs run <job>-schedule`）。
- [ ] 確認 Cloud Run execution 狀態 `Succeeded`：`gcloud run jobs executions list --job <job> --region <region>`。
- [ ] 確認 `pipeline_run_summary` 日誌與交付（Telegram/Dashboard）正常。
- [ ] 確認下一次排程時間符合預期時段。

---

## Dashboard 投資 artifacts 刷新（`refresh-invest-artifacts.yml`）

Vercel 不跑 Python pipeline，因此 `/calibration` 戰績與 `/invest` 決策簡報所讀的
`backtest/results/track_record.json`、`invest_brief.json` 需由排程**重算後 commit 回 repo**，
Vercel 才會在下次部署看到新資料。

- **觸發**：每日 `00:00 UTC`（= 08:00 Asia/Taipei，約在 pipeline 之後 40 分）＋手動 `workflow_dispatch`。
- **預設停用**：排程僅在 repo variable `INVEST_ARTIFACTS_ENABLED == 'true'` 時執行；手動觸發不受限。
- **流程**：`grade_decisions.py`（best-effort，需 secret `FINNHUB_API_KEY`；缺則略過戰績）→ `build_invest_brief.py`（讀 Firestore，用既有 WIF）→ 僅在 JSON 有變更時 commit + push `main`。
- **避免重複部署**：`ci.yml` 已 `paths-ignore: backtest/results/**`，純資料 commit 不觸發 Cloud Run 重建；Vercel 仍會部署以刷新 dashboard。
- **注意**：若 `main` 有分支保護擋住 Actions bot 直接 push，需允許該 bot 或改用具寫入權的 PAT。
