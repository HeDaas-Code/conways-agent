# ADR-0002: LLM 接口 — LiteLLM + MiniMax CN

## 状态

已采纳

## 背景

Agent 的世界观引擎、契合度判断、对话生成都需要 LLM 推理能力。项目需要一套模型无关的接口规范，既能当前接入 MiniMax CN，又能在未来低成本切换到其他模型。

## 决策

使用 **LiteLLM** 作为 LLM 接口抽象层，当前接入 **MiniMax CN**。

## 理由

- **LiteLLM** 提供统一接口，支持 100+ LLM（OpenAI、Anthropic、Google、Azure、本地模型等），通过环境变量配置切换模型，无需修改代码
- **MiniMax CN** 作为当前接入的 LLM 服务商，满足中文语境下的世界观构建需求
- 模型无关设计确保 Agent 的认知逻辑不绑定特定 LLM

## 实现方式

```python
# Python 层通过 LiteLLM 调用 MiniMax CN
import litellm
response = litellm.completion(
    model="minimax-cn/<model-name>",
    messages=[...],
)
```

## 后果

### 正面

- 一行配置切换模型
- 支持模型降级/升级
- 支持同时使用多个模型

### 负面

- 引入 LiteLLM 依赖
- MiniMax CN 的 API 兼容性依赖 litellm 版本更新
- 需要管理 API Key（通过环境变量）
