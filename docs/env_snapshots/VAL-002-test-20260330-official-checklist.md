# EnvSnapshot

Task ID: VAL-002
Date: 2026-03-30T11:24:08.7987780+08:00
Role: test

## Host

- OS: `Microsoft Windows 11 专业工作站版 10.0.26200 (Build 26200, 64 位)`
- Hostname: `CHIYU`
- Shell: `PowerShell 7.6.0`
- Working Directory: `D:\xtquant-mcp\repo`

## Runtime

- Trade Config Path: `D:\xtquant-mcp\instance\prod\config\trade_gateway.local.yaml`
- Repo EvidencePack: [VAL-002-test-20260330-official-checklist.md](../evidence_packs/VAL-002-test-20260330-official-checklist.md)
- TaskCard: [VAL-002.md](../task_cards/VAL-002.md)
- ChangePack: [VAL-002.md](../change_packages/VAL-002.md)
- Live userdata root: `D:\lh\国金证券QMT交易端\userdata_mini`
- Live QMT executable: `D:\lh\国金证券QMT交易端\bin.x64\XtMiniQmt.exe`

## Process and Port State

- Snapshot observation time: `2026-03-30T11:24:08.7987780+08:00`
- `XtMiniQmt`
  - `pid=25880`
  - `start_time=2026-03-30T00:32:23.4186077+08:00`
  - `path=D:\lh\国金证券QMT交易端\bin.x64\XtMiniQmt.exe`
- `miniquote`
  - `pid=20604`
  - `start_time=2026-03-30T00:32:23.6051081+08:00`
  - `path=D:\lh\国金证券QMT交易端\bin.x64\miniquote.exe`
- `127.0.0.1:58610`
  - `TcpTestSucceeded=true`

## Login and Session Baseline

- Baseline observation time: `2026-03-30T11:23:43.0315502+08:00`
- `diag_login_latest.json`
  - `ok=true`
  - `status=already_logged_in`
  - `message=MiniQMT already logged in`
  - `qmt_userdata=D:\lh\国金证券QMT交易端\userdata_mini`
  - `port_ready=true`
  - `process_id=25880`
- `trade_session_current.json`
  - `ready=false`
  - `reason=session_not_ready`
  - `owner_generation=0`
  - `session_id=""`
- `diag_probe_latest.json`
  - `account_contract=single_account_primary`
  - `account_input_mode=service_context_only`
  - `account_scope=service_context`

## Path and Permission Facts

- Path fact observation time: `2026-03-30T11:22:30.9257460+08:00`
- Matching config lines:
  - line `25`: `qmt_userdata: D:\lh\国金证券QMT交易端\userdata_mini`
  - line `52`: `qmt_userdata: D:\lh\国金证券QMT交易端\userdata_mini`
  - line `86`: `qmt_userdata: D:\lh\国金证券QMT交易端\userdata_mini`
- Filesystem path facts:
  - `resolved=D:\lh\国金证券QMT交易端\userdata_mini`
  - `exists=true`
  - `psdrive=D`
  - `root=D:\`
  - `is_on_c_drive=false`
  - `item_type=directory`
  - `last_write_time=2026-03-30T11:16:55.0455763+08:00`

## Bounded Writeability Probe

- Probe observation time: `2026-03-30T11:22:43.4289984+08:00`
- Probe path: `D:\lh\国金证券QMT交易端\userdata_mini\codex_val002_write_probe_20260330.txt`
- Create phase:
  - started `2026-03-30T11:22:43.4148872+08:00`
  - finished `2026-03-30T11:22:43.4208646+08:00`
  - `exists_after_create=true`
  - `length=82`
  - `last_write_time=2026-03-30T11:22:43.4206289+08:00`
- Delete phase:
  - started `2026-03-30T11:22:43.4208646+08:00`
  - finished `2026-03-30T11:22:43.4289984+08:00`
  - `exists_after_delete=false`
- Permission note:
  - this run performed the official FAQ-style bounded create/delete test only
  - no cleanup beyond removing the single probe file was performed

## Queue and Candidate-Session Artifact State

- Focused artifact observation time: `2026-03-30T11:23:24.4647100+08:00`
- `up_queue_xtquant` family:
  - `up_queue_xtquant`, length `75497752`, mtime `2026-03-30T00:32:24.7416471+08:00`
  - `up_queue_xtquant__mutex`, length `0`, mtime `2026-03-30T00:32:24.7624462+08:00`
  - `lock_up_queue_xtquant`, length `0`, mtime `2026-03-30T00:32:24.7624462+08:00`
  - `up_queue_win_xtquant`, length `75497752`, mtime `2026-03-30T00:32:24.7644484+08:00`
  - `up_queue_win_xtquant__mutex`, length `0`, mtime `2026-03-30T00:32:24.7879558+08:00`
  - `lock_up_queue_win_xtquant`, length `0`, mtime `2026-03-30T00:32:24.7879558+08:00`
- Candidate-session artifact observation time: `2026-03-30T11:23:43.2165990+08:00`
- `session_id=100`
  - artifact count `2`
  - `down_queue_win_100`, length `75497752`, mtime `2026-03-30T11:16:48.1548852+08:00`
  - `down_queue_win_100__mutex`, length `0`, mtime `2026-03-30T03:04:48.2607086+08:00`
- `session_id=101`
  - artifact count `2`
  - `down_queue_win_101`, length `75497752`, mtime `2026-03-30T11:16:51.1858945+08:00`
  - `down_queue_win_101__mutex`, length `0`, mtime `2026-03-30T03:05:03.6122410+08:00`
- `session_id=111`
  - artifact count `3`
  - `down_queue_win_111`, length `75497752`, mtime `2026-03-30T10:59:06.3285110+08:00`
  - `down_queue_win_111__mutex`, length `0`, mtime `2026-03-30T03:05:33.8614918+08:00`
  - `lock_down_queue_win_111`, length `0`, mtime `2026-03-30T10:58:24.0387995+08:00`

## Top-Level Userdata Context

- Top-level inventory observed in this run includes:
  - directories: `datadir`, `datas`, `dumps`, `log`, `quoter`, `users`
  - queue files: `down_queue_win_100`, `down_queue_win_101`, `down_queue_win_111`, `up_queue_xtquant`, `up_queue_win_xtquant`
  - lock/mutex files: `*_mutex`, `lock_*`
- No queue/session artifact cleanup was performed.

## Unresolved and Boundary Notes

- This snapshot evidences:
  - correct `userdata_mini` path
  - non-`C:` placement
  - successful bounded write/delete
  - presence of `up_queue_xtquant`
  - presence and mtimes of candidate-session queue artifacts for `100/101/111`
- This snapshot does not evidence:
  - a successful owner-managed trade session
  - a successful live rerun with alternate `session_id`
  - whether `极简模式登录` is enabled or relevant
- Therefore this snapshot supports continued environment classification rather than design clearance.
