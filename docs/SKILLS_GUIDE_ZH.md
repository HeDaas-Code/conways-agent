# Matt Pocock Skills 使用指南

本文档为 `Conway's Agent` 仓库中的 AI Agent 工程技能提供中文说明，涵盖每个技能的用途、适用阶段和使用方法。

---

## 概览：技能清单

| 技能 | 用途 |
|------|------|
| `to-issues` | 将计划 / PRD 拆解为可独立领取的实现任务 |
| `to-prd` | 将当前对话上下文发布为一份正式的需求文档 |
| `triage` | 对 Issue 进行分类状态机流转 |
| `diagnose` | 系统性诊断 Bug 或性能问题 |
| `tdd` | 红-绿-重构测试驱动开发 |
| `improve-codebase-architecture` | 寻找架构深化 / 重构机会 |
| `grill-me` | 压力测试计划或设计方案 |
| `handoff` | 将会话压缩为交接文档 |
| `prototype` | 快速原型验证设计 |
| `babysit` | 保持 PR 处于可合并状态 |

---

## 一、项目启动阶段

### 场景：从零开始，想把想法变成可执行的任务

**推荐技能：`/to-prd` 或 `/to-issues`**

当你有一个模糊的想法时：

1. **先用 `/grill-me`** — 反复追问你的计划，逼迫你把每个细节想清楚。这适合设计阶段。
2. **想法清晰后用 `/to-prd`** — 把对话上下文发布为一份正式的 PRD（产品需求文档），发布到 GitHub Issue。
3. **PRD 就绪后用 `/to-issues`** — 将 PRD 拆解为具体的、可被 AI agent 独立执行的任务 Issue。

**典型流程**：

```
有一个新功能的想法
  → /grill-me 追问细节
  → /to-prd 生成 PRD，发到 GitHub
  → /to-issues 拆解为实现任务
  → 每个 Issue 打上 triage 标签
```

---

## 二、任务分配阶段

### 场景：有 Issue 了，需要确定谁来处理

**推荐技能：`/triage`**

`triage` 技能会按照状态机推进每个 Issue：

```
needs-triage（需评估）
  → needs-info（等待提交者补充信息）
  → ready-for-agent（可交给 AI agent 执行）
  → ready-for-human（需人工实现）
  → wontfix（不处理）
```

**使用方法**：告诉 agent "用 `/triage` 处理这个 Issue"，它会帮你评估、更新标签、添加评论。

---

## 三、代码开发阶段

### 场景：开始写代码了

**推荐技能：`/tdd` 或 `/prototype`**

#### 如果你要实现一个功能或修复一个 Bug

使用 **`/tdd`**（测试驱动开发）：

1. Agent 先写一个**失败的测试**（红）
2. Agent 写最少量代码让测试通过（绿）
3. Agent 重构代码（重构）
4. 循环直到功能完成

#### 如果你要验证一个设计方向是否可行

使用 **`/prototype`** — 快速构建一个可运行的原型，用于：
- 验证数据模型 / 状态机
- 尝试不同的 UI 方案
- 快速验证 API 设计

#### 如果你要提升代码质量

使用 **`/improve-codebase-architecture`** — 它会：
- 寻找紧耦合的模块
- 发现可测试性改进点
- 提出架构深化建议

---

## 四、Bug 处理阶段

### 场景：线上或测试中发现了一个 Bug

**推荐技能：`/diagnose`**

`diagnose` 遵循严格的问题诊断循环：

```
复现（Reproduce）
  → 最小化（Minimise）
  → 假设（Hypothesise）
  → 仪器化（Instrument）
  → 修复（Fix）
  → 回归测试（Regression-test）
```

**使用方法**：告诉 agent "用 `/diagnose` 诊断这个问题"，它会引导你一步步找出根本原因并修复。

---

## 五、代码评审阶段

### 场景：有一个 PR 需要保持可合并状态

**推荐技能：`/babysit`**

`babysit` 技能会循环执行：
- 分类 PR 上的评论
- 解决明显的冲突
- 修复 CI 失败的检查

**使用方法**：告诉 agent "用 `/babysit` 照看这个 PR"。

---

## 六、交接阶段

### 场景：需要把当前工作交接给另一个 Agent 或其他人

**推荐技能：`/handoff`**

`handoff` 会将当前对话压缩为一份结构化的交接文档，包含：
- 当前状态
- 上下文
- 下一步行动

---

## 七、决策验证阶段

### 场景：有一个技术决策想确认是否正确

**推荐技能：`/grill-me`**

`grill-me` 会像一个苛刻的评审者一样反复追问你的决策，直到：
- 你确信这个决策是正确的
- 所有潜在问题都被暴露出来

---

## 快速参考表

| 你想做什么 | 用哪个技能 |
|-----------|-----------|
| 把想法变成正式文档 | `/to-prd` |
| 把文档拆成任务 | `/to-issues` |
| 追问设计细节 | `/grill-me` |
| 修复 Bug | `/diagnose` |
| 写代码（TDD） | `/tdd` |
| 验证设计方向 | `/prototype` |
| 改善架构 | `/improve-codebase-architecture` |
| 管理 Issue 状态 | `/triage` |
| 保持 PR 可合并 | `/babysit` |
| 交接工作 | `/handoff` |

---

## 配置文件参考

- `docs/agents/issue-tracker.md` — Issue 操作规范（GitHub Issues via `gh` CLI）
- `docs/agents/triage-labels.md` — 五个分类角色对应的标签名称
- `docs/agents/domain.md` — 领域文档消费规则（`CONTEXT.md` + `docs/adr/` 布局）

如需修改任何配置，可直接编辑上述文件。重新运行 `/setup-matt-pocock-skills` 仅在需要切换 Issue Tracker 时才有必要。
