# Codex Superpowers 实用指南

## 一句话结论

`superpowers` 不是一个单独的软件功能，也不是只有 3 个命令。

它本质上是一套给 coding agent 使用的工作流技能库。你对 Codex 说的不是“执行某个程序”，而是“这次任务按某个方法做”。

例如：

- `use systematic-debugging to investigate this failure`
- `use writing-plans for this task`
- `use test-driven-development for this feature`

这些话的意思分别是：

- 按系统化排障流程调查故障
- 先写实施计划再动手
- 先写测试、看失败、再写实现

## 本机安装状态

当前本机已安装的 `superpowers` 路径：

- 仓库：`C:\Users\Yun\.codex\superpowers`
- skills 入口：`C:\Users\Yun\.agents\skills\superpowers`

## 最实用的记法

日常不用把所有 skill 都记住。优先记下面 6 个就够了。

### 1. `brainstorming`

适用场景：

- 需求还不清楚
- 方案有多个候选
- 你想先把边界、风险、拆分讲清楚

一句话理解：

先把问题想明白，再开始设计或编码。

可直接复制：

```text
use brainstorming to refine this feature before implementation
```

### 2. `writing-plans`

适用场景：

- 任务明显不是一步完成
- 你要 agent 先拆步骤、拆文件、拆测试
- 你希望先看到实施计划，再决定是否执行

一句话理解：

先把实现方案写成可执行计划，再按计划推进。

可直接复制：

```text
use writing-plans for this task
```

更完整一点：

```text
use brainstorming and writing-plans for this task
```

### 3. `systematic-debugging`

适用场景：

- 测试失败
- 程序行为异常
- 某个 bug 看起来“像是这里有问题”，但你不想让 agent 直接拍脑袋改

一句话理解：

先找根因，再修；禁止直接猜修复。

可直接复制：

```text
use systematic-debugging to investigate this failure
```

### 4. `test-driven-development`

适用场景：

- 新功能
- bugfix
- 行为变更

一句话理解：

先写测试并确认失败，再写最小实现让它通过。

可直接复制：

```text
use test-driven-development for this feature
```

### 5. `verification-before-completion`

适用场景：

- agent 说“改好了”
- 你想让它收尾前认真核对
- 你不想看到“理论上应该可以”这种结论

一句话理解：

完成前必须验证，不靠主观判断宣布成功。

可直接复制：

```text
use verification-before-completion before you mark this done
```

### 6. `requesting-code-review`

适用场景：

- 代码已经写完
- 你想让 agent 从 review 角度挑风险、回归点、缺测试项

一句话理解：

不要只看“能不能跑”，还要看“有没有坑”。

可直接复制：

```text
use requesting-code-review on these changes
```

## 最常用的组合

### 场景 1：需求还不清楚

```text
use brainstorming for this task
```

### 场景 2：需求清楚，但任务比较大

```text
use writing-plans for this task
```

### 场景 3：既要先想清楚，又要形成实施计划

```text
use brainstorming and writing-plans for this task
```

### 场景 4：定位故障，不许乱改

```text
use systematic-debugging to investigate this failure
```

### 场景 5：写功能时要求先测后写

```text
use test-driven-development for this feature
```

### 场景 6：做完以后再严谨验收

```text
use verification-before-completion before you mark this done
```

### 场景 7：做完以后再从 review 视角挑问题

```text
use requesting-code-review on these changes
```

## 你真正需要的简单决策法

如果你只想记一个最短版本，可以按下面选：

- 不清楚怎么做：`brainstorming`
- 清楚要做什么，但任务复杂：`writing-plans`
- 出 bug / 测试挂了：`systematic-debugging`
- 要写功能或修 bug：`test-driven-development`
- 觉得做完了，准备收口：`verification-before-completion`

## 常见误解

### 误解 1：这是终端命令

不是。

它更像是你对 agent 下达的“工作方式要求”。

### 误解 2：这个项目只有三个技能

不是。

你之前提到的 3 句，只是最常用的 3 个示例。

### 误解 3：每次都要把 skill 名字说得很复杂

也不是。

大多数情况下，你只要说清楚这次想让 agent 按哪种方式工作即可。

例如：

- “先做排障，不要直接修”
- “先给我写计划”
- “按 TDD 做”

这些都可以再翻译成对应的 skill 说法。

## 当前已安装的 skills

当前本机可见的 `superpowers` skills 包括：

- `brainstorming`
- `dispatching-parallel-agents`
- `executing-plans`
- `finishing-a-development-branch`
- `receiving-code-review`
- `requesting-code-review`
- `subagent-driven-development`
- `systematic-debugging`
- `test-driven-development`
- `using-git-worktrees`
- `using-superpowers`
- `verification-before-completion`
- `writing-plans`
- `writing-skills`

## 推荐用法

如果你平时只想保留一套最省心的说法，建议直接用下面这 4 句：

```text
use brainstorming and writing-plans for this task
use systematic-debugging to investigate this failure
use test-driven-development for this feature
use verification-before-completion before you mark this done
```

这 4 句已经覆盖了大部分实际场景：

- 开始前先想清楚
- 出错时先查根因
- 实现时先写测试
- 收尾时先做验证
