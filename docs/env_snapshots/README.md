# EnvSnapshot 目录

本目录存放高风险或跨宿主任务的环境快照。

命名约定：

- `docs/env_snapshots/<TaskID>-<YYYYMMDDHHMM>.md`

以下任务应优先补环境快照：

1. 涉及外部端口、桌面交互或券商登录状态的 smoke。
2. 涉及真实写路径或撤单验证的任务。
3. 需要区分 `fail_env` 与 `fail_design` 的争议性问题。
