# EvidencePack

Task ID: VAL-002
Role: test
Date: 2026-03-30T10:36:06+08:00
Acceptance Gate: G3
Conclusion: fail_env

## Env Snapshot

- Link: D:\xtquant-mcp\repo\docs\env_snapshots\VAL-002-test-20260330-ui-visibility.md
- Host: CHIYU (Windows 11)
- Shell: PowerShell 7.6.0
- Config:
  - D:\xtquant-mcp\repo\docs\task_cards\VAL-002.md
  - D:\xtquant-mcp\repo\docs\change_packages\VAL-002.md

## Test Scope

1. Use the repo-supported MiniQMT login entrypoint `scripts/login_miniqmt.py --report-json` to generate a fresh UI/login visibility report.
2. Inspect the generated JSON for `interactive_desktop`, `login_window_found`, `main_window_found`, `window_titles`, `window_classifications`, `selected_login_title`, `selected_main_title`, and `screenshot_path`.
3. Confirm screenshot file existence if the JSON reports a screenshot path.
4. Capture current `XtMiniQmt` and `miniquote` process/listener facts to separate `window absent` from `window present but unrecognized`.
5. Produce an environment-only classification for the current UI/login visibility blocker without claiming that `VAL-002` is fixed or cleared.

## Commands

1. `2026-03-30T10:33:42.2313786+08:00 -> 2026-03-30T10:34:27.8186126+08:00`
   `python scripts\login_miniqmt.py --report-json C:\Users\Yun\AppData\Local\Temp\VAL-002-login-report-20260330-103342.json`
2. `2026-03-30T10:34:50+08:00`
   `python -c "import json, pathlib; p=pathlib.Path(r'C:\Users\Yun\AppData\Local\Temp\VAL-002-login-report-20260330-103342.json'); data=json.loads(p.read_text(encoding='utf-8')); obs=data.get('evidence',{}).get('final_observation',{}); rp=data.get('evidence',{}).get('run_profile',{}); shot = obs.get('screenshot_path', data.get('evidence',{}).get('screenshot_path', '')); print(json.dumps({'report_path': str(p), 'interactive_desktop': rp.get('interactive_desktop'), 'login_window_found': obs.get('login_window_found'), 'main_window_found': obs.get('main_window_found'), 'window_titles': obs.get('window_titles'), 'window_classifications': obs.get('evidence',{}).get('window_classifications'), 'selected_login_title': obs.get('evidence',{}).get('selected_login_title'), 'selected_main_title': obs.get('evidence',{}).get('selected_main_title'), 'screenshot_path': shot}, ensure_ascii=False, indent=2))"`
3. `2026-03-30T10:34:50+08:00`
   `python -c "import json, pathlib; p=pathlib.Path(r'C:\Users\Yun\AppData\Local\Temp\VAL-002-login-report-20260330-103342.json'); data=json.loads(p.read_text(encoding='utf-8')); shot = data.get('evidence',{}).get('final_observation',{}).get('screenshot_path') or data.get('evidence',{}).get('screenshot_path') or ''; print('SCREENSHOT_PATH=' + shot); print('SCREENSHOT_EXISTS=' + str(pathlib.Path(shot).exists()) if shot else 'SCREENSHOT_EXISTS=no_path_reported')"`
4. `2026-03-30T10:34:50.2682169+08:00`
   `Get-Process XtMiniQmt, miniquote | Select-Object ProcessName, Id, StartTime, MainWindowTitle, Path`
5. `2026-03-30T10:34:50.2323151+08:00`
   `Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -in 58610,8765,8766 } | Sort-Object LocalPort | Select-Object LocalAddress, LocalPort, OwningProcess, State`
6. `2026-03-30T10:35:08.8294152+08:00`
   `Get-Process XtMiniQmt, miniquote | Select-Object ProcessName, Id, MainWindowHandle, MainWindowTitle, Responding, StartTime`
7. `2026-03-30T10:35:08.9358793+08:00`
   `Test-NetConnection 127.0.0.1 -Port 58610 | Select-Object ComputerName, RemotePort, TcpTestSucceeded`
8. `2026-03-30T10:35:09+08:00`
   `cmd /c tasklist /v /fi "IMAGENAME eq XtMiniQmt.exe" /fi "IMAGENAME eq miniquote.exe"`
   Result note: returned `INFO: No tasks are running which match the specified criteria.` because the combined `/fi` clauses were ANDed; this command was not used for the verdict.
9. `2026-03-30T10:35:57.4043574+08:00`
   `(Get-Command python).Source; python --version`
10. `2026-03-30T10:35:57.5334807+08:00`
    `$PSVersionTable.PSVersion.ToString(); hostname`
11. `2026-03-30T10:36:06.1360140+08:00`
    `python -c "import platform; print(platform.platform())"`

## Raw Results

- `login_miniqmt.py --report-json`
  - `exit_code=1`
  - `ok=false`
  - `status=login_window_not_found`
  - `message=MiniQMT login window not found`
  - `process_id=25880`
  - `port_ready=true`
  - `launch.ok=true`
  - `launch.already_running=true`
  - `launch.started=false`
- Report JSON key fields from `final_observation` and `run_profile`
  - `interactive_desktop=true`
  - `login_window_found=false`
  - `main_window_found=false`
  - `window_titles=[]`
  - `window_classifications=[]`
  - `selected_login_title=''`
  - `selected_main_title=''`
  - `screenshot_path=''`
- Screenshot existence check
  - `SCREENSHOT_PATH=` was empty
  - `SCREENSHOT_EXISTS=no_path_reported`
  - No screenshot artifact was available to confirm on disk in this run
- `XtMiniQmt` process facts
  - `ProcessName=XtMiniQmt`
  - `Id=25880`
  - `StartTime=2026-03-30 00:32:23`
  - `Path=D:\lh\国金证券QMT交易端\bin.x64\XtMiniQmt.exe`
  - `MainWindowHandle=199142`
  - `MainWindowTitle=8883884325 - 国金证券QMT交易端 2.0.8.300`
  - `Responding=True`
- `miniquote` process facts
  - `ProcessName=miniquote`
  - `Id=20604`
  - `StartTime=2026-03-30 00:32:23`
  - `Path=D:\lh\国金证券QMT交易端\bin.x64\miniquote.exe`
  - `MainWindowHandle=0`
  - `MainWindowTitle=''`
  - `Responding=True`
- Listener facts
  - `0.0.0.0:58610 -> pid 20604 (miniquote.exe) state=Listen`
  - `127.0.0.1:58610 TcpTestSucceeded=True`
  - `127.0.0.1:8765 -> pid 22620 state=Listen`
  - `127.0.0.1:8766 -> pid 29436 state=Listen`

## Artifact Refs

- Fresh login visibility report:
  - C:\Users\Yun\AppData\Local\Temp\VAL-002-login-report-20260330-103342.json
- EvidencePack:
  - D:\xtquant-mcp\repo\docs\evidence_packs\VAL-002-test-20260330-ui-visibility.md
- EnvSnapshot:
  - D:\xtquant-mcp\repo\docs\env_snapshots\VAL-002-test-20260330-ui-visibility.md

## Failure Classification

- `fail_env`: confirmed for this bounded investigation. The repo-supported login probe remained unable to recognize a usable MiniQMT login or main window in its own observation payload, so this run did not establish a login-ready UI state.
- `fail_design`: not proven by this subtask. This run only collected environment evidence and did not validate or invalidate unrelated code-path changes.

## UI Visibility Classification

- Classification: `window present but unrecognized`
- Reason:
  - The supported probe reported `interactive_desktop=true` yet returned `login_window_found=false`, `main_window_found=false`, `window_titles=[]`, `window_classifications=[]`, and no screenshot path.
  - Independent OS-level process inspection at the same time showed `XtMiniQmt` still had a non-zero `MainWindowHandle` and a non-empty `MainWindowTitle`.
  - Therefore the evidence does not support a clean `window absent` claim. It more strongly supports that a MiniQMT top-level window existed on the host but was not recognized by the current login visibility probe in this run.

## Verdict

`fail_env`. This is an environment evidence subtask only. The current hard evidence shows that MiniQMT had a host-visible top-level window while the repo-supported login probe still recognized no login/main window and produced no screenshot artifact. Do not treat this run as `pass`, do not claim `VAL-002` is cleared, and do not advance to `VAL-003` on the basis of this EvidencePack alone.
