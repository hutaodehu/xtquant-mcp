# private_archive_manifest_20260702

## 归档根目录

`<private_archive_root>/open-source-prep-20260702/`

## 当前状态

- 未跟踪现场工件、ignored 运行态、根目录残留和已跟踪私有证据已经移动到私有归档。
- 归档校验清单已经生成，公开仓只记录清单位置、数量和归档原因。
- 公开仓只保留 sha256、大小、仓库相对路径、归档相对路径和归档原因；不保留真实证据内容。

## 文件清单

| sha256 | bytes | repo_path | archive_path | reason |
| --- | ---: | --- | --- | --- |
| 见 `SHA256SUMS.untracked` | 见清单 | 未跟踪现场文档与证据 | `untracked/` | 真实现场工件不进入公开仓 |
| 见 `SHA256SUMS.ignored` | 见清单 | ignored 运行态、缓存、截图、临时证据 | `ignored/` | 运行态和缓存不进入公开仓 |
| 见 `SHA256SUMS.ignored-extra` | 0 | 根目录 ignored 空壳 | `ignored-extra/` | 清理公开仓根目录 |
| 见 `SHA256SUMS.tracked-private` | 见清单 | 已跟踪 EnvSnapshot、EvidencePack、ReviewPack 和内部计划/规格 | `private-evidence/tracked-public-baseline-removal/` | 公开 baseline 只保留 README stub |

## 归档分区

| 分区 | archive_path | 内容 |
| --- | --- | --- |
| private-docs | `private-docs/` | 不适合公开的现场文档 |
| private-evidence | `private-evidence/` | EnvSnapshot、EvidencePack、ReviewPack、历史执行计划 |
| runtime-ignored | `runtime-ignored/` | `.tmp/`、`instance/`、`state/`、缓存和运行输出 |
| manual-probes | `manual-probes/` | 手工 probe、临时恢复脚本和本地验证配置 |
| release-artifacts | `release-artifacts/` | 本地冻结源码包和 sha256 |

## 已生成校验清单

| 清单 | 条目数 |
| --- | ---: |
| `<private_archive_root>/open-source-prep-20260702/SHA256SUMS.untracked` | 61 |
| `<private_archive_root>/open-source-prep-20260702/SHA256SUMS.ignored` | 603 |
| `<private_archive_root>/open-source-prep-20260702/SHA256SUMS.ignored-extra` | 0 |
| `<private_archive_root>/open-source-prep-20260702/SHA256SUMS.tracked-private` | 183 |

## 校验命令

`sha256sum -c SHA256SUMS`

## 禁止公开内容

- 真实账户、真实 broker 回执、真实委托、真实成交、真实持仓和真实资金。
- 真实 MiniQMT/QMT 会话状态、端口快照和 gateway runtime artifact。
- 真实本机路径、真实 Windows 用户目录、真实 WSL 发行版上下文。
- `dotenv 文件`、令牌、密钥、授权头或任何可复用凭据。
