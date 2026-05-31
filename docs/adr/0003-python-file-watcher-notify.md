# ADR-0003: Python 层文件监听 — notify

## 状态

已采纳

## 背景

Agent 需要监听 Obsidian vault 的文件变化（创建、修改、删除）来触发感知系统。Python 层需要跨平台的文件监听方案（主要平台：Linux、macOS）。

## 决策

使用 Python 的 **notify** 库（`notify` / `python-rs`）作为文件监听方案。

## 理由

- `notify` 是 Rust 实现，性能高、资源占用低
- 跨平台支持完善（Linux inotify、macOS FSEvents、Windows ReadDirectoryChangesW）
- API 简洁，事件类型丰富（CREATE、MODIFY、DELETE、MOVED_FROM、MOVED_TO）
- 相比 `watchdog`，`notify` 更轻量、无JNI依赖

## 实现方式

```python
import notify

with notify.Notifier() as n:
    n.watch(path="/path/to/vault", recursive=True)
    for event in n:
        handle(event)  # event.type, event.path
```

## 后果

### 正面

- 高性能、低延迟的文件事件捕获
- 跨平台开箱即用
- 事件粒度细（区分修改 vs 重命名等）

### 负面

- 依赖 Rust 运行时
- 递归监听大量文件时需注意 inotify 限制（Linux 可通过 `sysctl` 调整）
- 不支持 macOS 的某些高级事件
