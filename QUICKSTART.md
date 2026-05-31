# 快速启动指南

本指南将帮助你快速搭建并运行 Obsidian Agent。

## 前置要求

- **Python 3.10+**
- **Node.js 18+**（用于 Obsidian 插件）
- **Obsidian**（可选，用于完整功能）
- **MiniMax API Key** 或其他 LiteLLM 支持的 API Key

## 环境配置

### 1. 克隆项目

```bash
git clone https://github.com/HeDaas-Code/conways-agent.git
cd conways-agent
```

### 2. 安装 Python 依赖

```bash
cd python
pip install -r requirements.txt
```

### 3. 配置环境变量

复制 `.env.example` 为 `.env` 并配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```bash
# MiniMax CN API（必须）
MINIMAX_API_KEY=your_api_key_here

# LLM Model（可选，默认 minimax-cn/gemini-2.5-flash）
LITELLM_MODEL=minimax-cn/your-model

# Obsidian Vault Path（必须）
OBSIDIAN_VAULT_PATH=/path/to/your/vault

# Python API Server（可选，默认 http://localhost:8000）
PYTHON_API_URL=http://localhost:8000
```

### 4. 配置 Vault 路径

确保 `OBSIDIAN_VAULT_PATH` 指向你的 Obsidian vault 目录，并且 vault 中包含 `agent/` 目录：

```
your-vault/
├── agent/
│   ├── seed.md       # 人格种子文件
│   ├── goals/        # 目标目录
│   ├── world/        # 世界观目录
│   └── knowledge/    # 知识库目录
└── ...               # 你的笔记
```

## 运行模式

### 对话模式（交互式）

与 Agent 进行实时对话：

```bash
cd python
python -m agent.main --dialogue
# 或简写
python -m agent.main
```

交互命令：
- `quit` / `exit` / `q` — 退出
- `clear` — 清空对话历史
- `status` — 查看 Agent 状态

### 深度终端界面（TUI）

启动带有行为监控的深度终端界面：

```bash
cd python
python -m agent.main --deep
# 或
python -m agent.ui.deep_terminal
```

### 守护进程模式

以睡眠/唤醒循环 + 文件监听模式运行：

```bash
cd python
python -m agent.main --daemon
```

守护进程模式特点：
- Agent 在唤醒期间处理文件变化
- 休眠期间仅被动监听
- 支持死亡/污染检测
- 支持分身诞生检测

### 感知特定文件

让 Agent 感知指定文件：

```bash
python -m agent.main --perceive notes/ideas.md
# 感知多个文件
python -m agent.main --perceive notes/1.md notes/2.md
```

### 全量感知

感知 vault 中的所有用户文件：

```bash
python -m agent.main --perceive-all
```

## 运行测试

```bash
cd python
python -m pytest agent/tests/ -v
```

运行特定测试：

```bash
# 测试目标系统
python -m pytest agent/tests/test_goals.py -v

# 测试记忆系统
python -m pytest agent/tests/test_memory.py -v

# 测试演化系统
python -m pytest agent/tests/test_evolution.py -v
```

## 常见问题

### 1. 启动失败：`请确保 OBSIDIAN_VAULT_PATH 环境变量已设置`

**原因**：未设置 `OBSIDIAN_VAULT_PATH` 环境变量。

**解决**：
```bash
export OBSIDIAN_VAULT_PATH=/path/to/your/vault
```

或确保 `.env` 文件中已配置。

### 2. LLM API 调用失败

**原因**：API Key 错误或额度不足。

**解决**：
- 检查 `.env` 中的 `MINIMAX_API_KEY` 是否正确
- 检查 API Key 是否有足够的调用额度
- 确认 `LITELLM_MODEL` 设置正确

### 3. Vault 目录结构错误

**原因**：`agent/` 目录缺失或结构不正确。

**解决**：确保 vault 中存在以下目录结构：
```
your-vault/agent/
├── seed.md
├── goals/
├── world/
└── knowledge/
```

### 4. 文件监听不工作

**原因**：`notify` 库未正确安装或平台不支持。

**解决**：
```bash
pip install notify>=0.1.0
```

在 Linux 上可能需要安装额外依赖：
```bash
sudo apt install libnotify-dev  # Debian/Ubuntu
sudo dnf install libnotify-devel  # Fedora
```

### 5. 测试失败

运行单测获取详细信息：
```bash
python -m pytest agent/tests/test_xxx.py -v -s
```

## 项目结构

```
python/agent/
├── core/              # 核心模块
│   ├── llm.py         # LLM 推理
│   ├── vault.py       # Vault 管理
│   ├── cycle.py       # 睡眠/唤醒
│   ├── perception.py  # 感知系统
│   ├── pipeline.py    # 处理管道
│   ├── goals.py       # 目标系统
│   ├── evolution.py   # 演化系统
│   ├── memory.py      # 记忆系统
│   └── ...
├── ui/                # 界面模块
│   └── deep_terminal.py
├── tests/             # 测试
└── main.py            # CLI 入口
```

## 下一步

- 阅读 [docs/SKILLS_GUIDE_ZH.md](docs/SKILLS_GUIDE_ZH.md) 了解 Skills 使用
- 查看 [docs/adr/](docs/adr/) 了解架构决策
- 参考 [PRD Issue #1](https://github.com/HeDaas-Code/conways-agent/issues/1) 了解项目规划
