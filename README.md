# Obsidian Agent

基于 Obsidian vault 的拟人化自发展认知体。

## 架构

```
conways-agent/
├── python/                    # Agent 核心引擎（Brain）
│   ├── agent/                 # Agent Python 模块
│   │   ├── core/              # 核心模块
│   │   │   ├── llm.py         # LLM 推理接口（LiteLLM）
│   │   │   ├── vault.py       # Vault 路径管理
│   │   │   ├── cycle.py       # 睡眠/唤醒循环
│   │   │   ├── perception.py  # 感知系统
│   │   │   ├── pipeline.py    # 处理管道
│   │   │   ├── state.py       # Agent 状态
│   │   │   ├── goals.py       # 目标系统
│   │   │   ├── evolution.py   # 演化系统
│   │   │   ├── memory.py      # 记忆系统
│   │   │   ├── dialogue.py    # 对话模块
│   │   │   ├── watcher.py     # 文件监听器
│   │   │   ├── vitality.py    # 生命周期监控
│   │   │   ├── scheduler.py   # 三驱动调度器
│   │   │   ├── curiosity.py   # 好奇心系统
│   │   │   ├── decay.py       # 记忆衰减
│   │   │   ├── trace.py       # 行为追踪
│   │   │   ├── attention.py   # 注意力机制
│   │   │   ├── resolution.py  # 冲突消解
│   │   │   ├── consistency.py # 一致性检查
│   │   │   ├── personality_review.py  # 人格回顾
│   │   │   ├── autonomous.py  # 自主行为
│   │   │   ├── activity.py    # 活动系统
│   │   │   └── startup.py     # 启动逻辑
│   │   ├── ui/                # 用户界面
│   │   │   └── deep_terminal.py  # 深度终端 TUI
│   │   ├── tests/             # 单元测试
│   │   ├── knowledge/         # 知识库
│   │   ├── world/             # 世界观文件
│   │   ├── main.py            # CLI 入口
│   │   └── log.py             # 日志模块
│   ├── requirements.txt       # Python 依赖
│   └── .env.example           # 环境变量示例
├── node/                      # Agent 感知与交互层（Body）
│   └── src/                  # Obsidian 插件源码
├── agent/                    # Agent 的 vault 空间
│   ├── seed.md               # 人格种子
│   ├── goals/                # 目标目录
│   ├── world/                # 世界观目录
│   └── knowledge/            # 知识库
└── docs/                     # 文档
    ├── adr/                  # 架构决策记录
    └── SKILLS_GUIDE_ZH.md    # Skills 使用指南
```

## 核心能力

- **感知** — 监听 Obsidian vault 文件变化，在 Agent 清醒时处理新内容
- **世界观构建** — 契合度判断（翻译/碰撞），将感知内容整合为世界观碎片
- **记忆系统** — 世界观持久化、双向链接、时间衰减、鲜活度追踪
- **目标系统** — 自主创建目标、层次分解、三驱动协同调度（目标/好奇心/时间）
- **演化系统** — 人格回顾、漂移检测、参数自修改（保护核心身份）
- **生命周期** — 睡眠/唤醒循环、死亡检测、污染检测、分支分身

## 快速启动

详见 [QUICKSTART.md](QUICKSTART.md)

## 项目结构

- `/python/` — Agent 核心引擎（Brain）：LLM 推理、世界观处理、目标系统、演化系统
- `/node/` — Agent 感知与交互层（Body）：Obsidian 插件、文件监听
- `/agent/` — Agent 的 vault 空间：人格、记忆、目标、世界观、知识库

## 相关文档

- [PRD Issue #1](https://github.com/HeDaas-Code/conways-agent/issues/1)
- [docs/adr/](docs/adr/) — 架构决策记录
- [docs/SKILLS_GUIDE_ZH.md](docs/SKILLS_GUIDE_ZH.md) — Skills 使用指南
