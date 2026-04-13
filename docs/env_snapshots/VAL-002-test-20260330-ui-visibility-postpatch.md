# EnvSnapshot

Task ID: VAL-002
Date: 2026-03-30T10:49:48+08:00
Role: test
Patch Under Test: TG-003

## Host

- OS: Windows-11-10.0.26200-SP0
- Hostname: CHIYU
- Shell: PowerShell 7.6.0
- Working Directory: D:\xtquant-mcp\repo

## Runtime

- Python Executable: C:\Python313\python.exe
- Python Version: 3.13.12
- Repo Login Entrypoint: D:\xtquant-mcp\repo\scripts\login_miniqmt.py
- Fresh Report JSON: C:\Users\Yun\AppData\Local\Temp\VAL-002-login-report-20260330-104734-postpatch.json
- TaskCard: D:\xtquant-mcp\repo\docs\task_cards\VAL-002.md
- ChangePack Under Test: D:\xtquant-mcp\repo\docs\change_packages\TG-003.md
- EvidencePack: D:\xtquant-mcp\repo\docs\evidence_packs\VAL-002-test-20260330-ui-visibility-postpatch.md

## MiniQMT Process State

- XtMiniQmt:
  - `pid=25880`
  - `path=D:\lh\国金证券QMT交易端\bin.x64\XtMiniQmt.exe`
  - `start_time=2026-03-30 00:32:23`
  - `main_window_handle=199142`
  - `main_window_title=8883884325 - 国金证券QMT交易端 2.0.8.300`
  - `responding=True`
- miniquote:
  - `pid=20604`
  - `path=D:\lh\国金证券QMT交易端\bin.x64\miniquote.exe`
  - `start_time=2026-03-30 00:32:23`
  - `main_window_handle=0`
  - `main_window_title=''`
  - `responding=True`

## Port and Desktop State

- `interactive_desktop=true` in the fresh login probe
- `0.0.0.0:58610 -> pid 20604 (miniquote.exe) state=Listen`
- `127.0.0.1:58610 TcpTestSucceeded=True`
- `127.0.0.1:8765 -> pid 22620 state=Listen`
- `127.0.0.1:8766 -> pid 29436 state=Listen`
- Permission Notes: no elevation was used in this bounded post-patch verification; evidence came from repo-local Python and standard PowerShell inspection commands

## Report Observation Snapshot

- `status=already_logged_in`
- `ok=true`
- `process_id=25880`
- `port_ready=true`
- `login_window_found=false`
- `main_window_found=true`
- `window_title='8883884325 - 国金证券QMT交易端 2.0.8.300'`
- `window_titles=['8883884325 - 国金证券QMT交易端 2.0.8.300']`
- `host_window_fallback_used=true`
- `host_visible_windows=[{'handle': 199142, 'process_id': 25880, 'title': '8883884325 - 国金证券QMT交易端 2.0.8.300', 'class_name': 'Qt5QWindowIcon', 'visible': true, 'enabled': true}]`
- `window_classifications=['title=8883884325 - 国金证券QMT交易端 2.0.8.300; class=Qt5QWindowIcon; edits=0; buttons=0']`
- `selected_login_title=''`
- `selected_main_title='8883884325 - 国金证券QMT交易端 2.0.8.300'`
- `screenshot_path=''`
- `screenshot_capture_attempted=false`
- `screenshot_capture_error='imagegrab_unavailable'`

## Time Window

- Observation Window:
  - `py_compile`: `2026-03-30T10:47:21.6397889+08:00 -> 2026-03-30T10:47:21.6896164+08:00`
  - `focused unittest`: `2026-03-30T10:47:21.6561049+08:00 -> 2026-03-30T10:47:21.7531765+08:00`
  - `login_miniqmt.py` run: `2026-03-30T10:47:34.9622601+08:00 -> 2026-03-30T10:47:35.1131859+08:00`
  - report inspection: `2026-03-30T10:49:48.5455783+08:00 -> 2026-03-30T10:49:48.5455784+08:00`
  - process/listener corroboration: `2026-03-30T10:48:14.5465195+08:00 -> 2026-03-30T10:49:11.2052549+08:00`
- Market Window: not evaluated in this bounded post-patch check; this snapshot only covers UI visibility and evidence surfacing behavior

## Notes

- Compared with the earlier baseline evidence pack, the live report no longer collapsed to `window_titles=[]`, `window_classifications=[]`, and empty selection fields.
- The fresh report now preserves host-visible window evidence from the fallback path and identifies a host-visible main-window title.
- No screenshot file was available to confirm on disk in this run because the report recorded `screenshot_capture_error='imagegrab_unavailable'` and `screenshot_path=''`.
- This snapshot supports a bounded `partial` result for the patch verification itself, not a task-level `pass`.
- The broader `VAL-002` task remains blocked at the task-card level because this snapshot does not re-run the full `G3` readonly chain and does not clear the previously recorded broader environment blockers.
