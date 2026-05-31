# ADR-0001: 混合运行时架构

## 状态

已采纳

## 背景

Obsidian Agent 项目需要同时满足两个核心需求：强大的 LLM 推理能力（Agent 的认知引擎）和可靠的文件系统感知（Agent 的感知系统）。同时，Obsidian 插件需要使用 TypeScript 开发。

## 决策

采用**混合架构**：

- **Python 层**：Agent 核心引擎、LLM 推理、世界观处理、目标系统、演化系统
- **Node.js / TypeScript 层**：文件监听、Obsidian 插件、独立终端 UI
- **进程间通信**：通过 HTTP REST API 或 Unix Socket 连接两个层

## 理由

- Python 的 LLM 生态（LiteLLM、transformers 等）远优于 Node.js，Agent 认知逻辑用 Python 实现可获得最佳模型支持
- Node.js 的 chokidar 是文件监听的事实标准，Obsidian 插件必须用 TypeScript，文件感知层统一用 Node.js 避免重复建设
- 两层通过 API 解耦，任何一层均可独立替换或升级
- 避免引入重量级 RPC 框架（如 gRPC），保持简单性

## 结果

- Python 层作为 "Brain"，负责思考
- Node.js 层作为 "Body"，负责感知和交互
- 通信协议：HTTP REST API（Python 提供服务，Node.js 调用）

## 后果

### 正面

- 各层选最优工具
- 两层可独立开发和测试
- Obsidian 插件开发不受 Python 生态限制

### 负面

- 部署复杂度增加（两个进程）
- 进程间通信有延迟开销
- 需要维护 API 接口契约
