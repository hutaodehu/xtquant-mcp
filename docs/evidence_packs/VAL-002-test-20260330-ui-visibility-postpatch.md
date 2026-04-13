# EvidencePack

Task ID: VAL-002
Role: test
Date: 2026-03-30T10:49:48+08:00
Patch Under Test: TG-003
Acceptance Gate: G3
Conclusion: partial

## Env Snapshot

- Link: [VAL-002-test-20260330-ui-visibility-postpatch.md](../env_snapshots/VAL-002-test-20260330-ui-visibility-postpatch.md)
- Host: CHIYU (Windows 11)
- Shell: PowerShell 7.6.0
- TaskCard:
  - [VAL-002.md](../task_cards/VAL-002.md)
- ChangePack Under Test:
  - [TG-003.md](../change_packages/TG-003.md)
- Prior Baseline Evidence:
  - [VAL-002-test-20260330-ui-visibility.md](./VAL-002-test-20260330-ui-visibility.md)

## Test Scope

1. Run bounded local verification for the MiniQMT UI visibility follow-up patch with `py_compile` and focused unittest only.
2. Rerun the repo-supported login visibility entrypoint `python scripts\login_miniqmt.py --report-json ...` to generate a fresh live report.
3. Inspect whether the fresh report now contains non-empty host-visible evidence instead of collapsing to empty observations.
4. Capture current `XtMiniQmt` / `miniquote` process facts and listener state during the same evidence window.
5. Classify the bounded result using repo vocabulary and state explicitly whether this changes the current `VAL-002` blocked status.

## Commands

1. `2026-03-30T10:47:21.6397889+08:00 -> 2026-03-30T10:47:21.6896164+08:00`
   `python -m py_compile scripts\login_miniqmt.py xtqmt_mcp\miniqmt_login\desktop_harness.py tests\test_miniqmt_desktop_harness.py`
2. `2026-03-30T10:47:21.6561049+08:00 -> 2026-03-30T10:47:21.7531765+08:00`
   `python -m unittest -v tests.test_miniqmt_desktop_harness`
3. `2026-03-30T10:47:34.9622601+08:00 -> 2026-03-30T10:47:35.1131859+08:00`
   `python scripts\login_miniqmt.py --report-json C:\Users\Yun\AppData\Local\Temp\VAL-002-login-report-20260330-104734-postpatch.json`
4. `2026-03-30T10:49:48.5455783+08:00`
   `python -c "import json, pathlib; p=pathlib.Path(r'C:\Users\Yun\AppData\Local\Temp\VAL-002-login-report-20260330-104734-postpatch.json'); data=json.loads(p.read_text(encoding='utf-8')); obs=data.get('evidence',{}).get('final_observation') or data.get('evidence',{}).get('initial_observation') or {}; ev=obs.get('evidence',{}); shot=obs.get('screenshot_path') or data.get('evidence',{}).get('screenshot_path') or ''; print(json.dumps({'report_path':str(p), 'status':data.get('status'), 'ok':data.get('ok'), 'process_id':data.get('process_id'), 'port_ready':data.get('port_ready'), 'interactive_desktop':data.get('evidence',{}).get('run_profile',{}).get('interactive_desktop'), 'login_window_found':obs.get('login_window_found'), 'main_window_found':obs.get('main_window_found'), 'window_title':obs.get('window_title'), 'window_titles':obs.get('window_titles'), 'host_window_fallback_used':ev.get('host_window_fallback_used'), 'host_visible_windows':ev.get('host_visible_windows'), 'window_classifications':ev.get('window_classifications'), 'selected_login_title':ev.get('selected_login_title'), 'selected_main_title':ev.get('selected_main_title'), 'screenshot_path':shot, 'screenshot_capture_attempted':ev.get('screenshot_capture_attempted'), 'screenshot_capture_error':ev.get('screenshot_capture_error')}, ensure_ascii=False, indent=2))"`
5. `2026-03-30T10:49:48.5455784+08:00`
   `python -c "import json, pathlib; p=pathlib.Path(r'C:\Users\Yun\AppData\Local\Temp\VAL-002-login-report-20260330-104734-postpatch.json'); data=json.loads(p.read_text(encoding='utf-8')); obs=data.get('evidence',{}).get('final_observation') or data.get('evidence',{}).get('initial_observation') or {}; shot=obs.get('screenshot_path') or data.get('evidence',{}).get('screenshot_path') or ''; print('SCREENSHOT_PATH=' + shot); print('SCREENSHOT_EXISTS=' + str(pathlib.Path(shot).exists()) if shot else 'SCREENSHOT_EXISTS=no_path_reported')"`
6. `2026-03-30T10:48:14.5465195+08:00`
   `Get-Process XtMiniQmt, miniquote | Select-Object ProcessName, Id, StartTime, Path, MainWindowHandle, MainWindowTitle, Responding | Format-List`
7. `2026-03-30T10:48:14.5500525+08:00`
   `Get-NetTCPConnection -State Listen | Where-Object { $_.LocalPort -in 58610,8765,8766 } | Sort-Object LocalPort | Select-Object LocalAddress, LocalPort, OwningProcess, State`
8. `2026-03-30T10:48:14.6269442+08:00`
   `Test-NetConnection 127.0.0.1 -Port 58610 | Select-Object ComputerName, RemotePort, TcpTestSucceeded`
9. `2026-03-30T10:49:10.9895307+08:00`
   `(Get-Command python).Source; python --version`
10. `2026-03-30T10:49:10.9967782+08:00`
    `$PSVersionTable.PSVersion.ToString(); hostname`
11. `2026-03-30T10:49:11.2052549+08:00`
    `python -c "import platform; print(platform.platform())"`

## Raw Results

- `py_compile`
  - `exit_code=0`
  - No syntax/import compilation error for the entrypoint, patched harness module, or focused unittest module.
- `tests.test_miniqmt_desktop_harness`
  - `exit_code=0`
  - `Ran 2 tests`
  - `OK`
- Fresh `login_miniqmt.py --report-json`
  - `exit_code=0`
  - `ok=true`
  - `status=already_logged_in`
  - `message=MiniQMT already logged in`
  - `process_id=25880`
  - `port_ready=true`
- Fresh report JSON key fields
  - `interactive_desktop=true`
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
- Screenshot existence check
  - `SCREENSHOT_PATH=` was empty
  - `SCREENSHOT_EXISTS=no_path_reported`
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
- Current task-card blocked baseline
  - [VAL-002.md](../task_cards/VAL-002.md) still records `Status: Blocked`
  - `Blocking Reason: env_blocked`
  - Current note still states the broader local live G3 smoke hit `miniqmt_not_logged_in` and `xttrader connect=-1`

## Patch Verification Assessment

- `partial`
  - This bounded follow-up patch verification met its narrow objective.
  - The live repo-supported probe no longer collapsed to empty observations.
  - The fresh report now surfaces host-visible evidence through `host_window_fallback_used`, `host_visible_windows`, `window_classifications`, `window_titles`, `selected_main_title`, and a non-empty `window_title`.
- Not `pass`
  - This was not a full `G3` rerun.
  - No `session.warm`, `session.status`, `probe.connection`, `account.show`, `positions.list`, `orders.list`, or `snapshot.l1` acceptance chain was rerun in this pack.
  - No screenshot artifact was produced in this run because the report recorded `screenshot_capture_error='imagegrab_unavailable'`.
- Not `fail_design`
  - In this bounded run, the follow-up patch behavior matched the ChangePack goal: host-visible window evidence was preserved instead of being collapsed away.
- Not `fail_env`
  - The live report itself completed successfully and returned usable evidence.
  - The missing screenshot path is still an environment/runtime capability note, but it did not erase the new evidence payload.

## VAL-002 Status Impact

- `no change`
  - This EvidencePack does not clear the task-level blocked posture.
  - `VAL-002` remains `Blocked` with `env_blocked` at the task-card level after this bounded follow-up verification.
- Reason
  - The scope here was only the UI visibility follow-up patch and its evidence payload.
  - The broader `G3` readonly smoke was not rerun end-to-end in this pack.
  - The task card still carries unresolved broader blockers, including the previously recorded `xttrader connect=-1` context.
  - Do not advance to `VAL-003` on the basis of this post-patch UI visibility evidence alone.

## Artifact Refs

- Fresh login visibility report:
  - `C:\Users\Yun\AppData\Local\Temp\VAL-002-login-report-20260330-104734-postpatch.json`
- EvidencePack:
  - [VAL-002-test-20260330-ui-visibility-postpatch.md](./VAL-002-test-20260330-ui-visibility-postpatch.md)
- EnvSnapshot:
  - [VAL-002-test-20260330-ui-visibility-postpatch.md](../env_snapshots/VAL-002-test-20260330-ui-visibility-postpatch.md)
