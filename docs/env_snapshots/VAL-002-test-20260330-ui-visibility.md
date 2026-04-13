# EnvSnapshot

Task ID: VAL-002
Date: 2026-03-30T10:36:06+08:00
Role: test

## Host

- OS: Windows-11-10.0.26200-SP0
- Hostname: CHIYU
- Shell: PowerShell 7.6.0
- Working Directory: D:\xtquant-mcp\repo

## Runtime

- Python Executable: C:\Python313\python.exe
- Python Version: 3.13.12
- Repo Login Entrypoint: D:\xtquant-mcp\repo\scripts\login_miniqmt.py
- Fresh Report JSON: C:\Users\Yun\AppData\Local\Temp\VAL-002-login-report-20260330-103342.json
- TaskCard: D:\xtquant-mcp\repo\docs\task_cards\VAL-002.md
- ChangePack: D:\xtquant-mcp\repo\docs\change_packages\VAL-002.md
- EvidencePack: D:\xtquant-mcp\repo\docs\evidence_packs\VAL-002-test-20260330-ui-visibility.md

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

## Port and Permission State

- `interactive_desktop=true` in the fresh login probe
- `0.0.0.0:58610 -> pid 20604 (miniquote.exe) state=Listen`
- `127.0.0.1:58610 TcpTestSucceeded=True`
- `127.0.0.1:8765 -> pid 22620 state=Listen`
- `127.0.0.1:8766 -> pid 29436 state=Listen`
- Permission Notes: no elevation was used in this bounded evidence run; all facts came from repo-local Python and standard PowerShell inspection commands

## Time Window

- Observation Window:
  - `login_miniqmt.py` run start: `2026-03-30T10:33:42.2313786+08:00`
  - `login_miniqmt.py` run end: `2026-03-30T10:34:27.8186126+08:00`
  - process/listener corroboration: `2026-03-30T10:34:50+08:00` to `2026-03-30T10:36:06+08:00`
- Market Window: not evaluated in this subtask; this snapshot only captures UI/login visibility facts

## Notes

- The fresh JSON report recorded `status=login_window_not_found`, `login_window_found=false`, `main_window_found=false`, `window_titles=[]`, `window_classifications=[]`, `selected_login_title=''`, `selected_main_title=''`, and `screenshot_path=''`.
- Because `screenshot_path` was empty, screenshot existence could only be classified as `no_path_reported`.
- OS-level process inspection still observed a non-empty `XtMiniQmt` main window title during the same evidence window, so the bounded classification for this run is `window present but unrecognized`, not a proven `window absent`.
- This snapshot does not declare MiniQMT login success, does not clear `VAL-002`, and does not change the task's broader blocked posture by itself.
