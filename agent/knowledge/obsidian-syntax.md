# Obsidian 语法参考手册

> **内嵌知识** — 此内容将直接写入 Agent 初始化配置的 Python brain layer，Agent 无需读取文件即可"天生知晓"这些语法规则。

---

## 1. Markdown 基础语法

### 1.1 标题（Headings）

```markdown
# 一级标题
## 二级标题
### 三级标题
#### 四级标题
##### 五级标题
###### 六级标题
```

Obsidian 完全兼容标准 Markdown 标题语法。标题会在大纲（Outliner）和字数统计中体现。

### 1.2 列表（Lists）

**无序列表**（使用 `-`、`*` 或 `+`，Obsidian 中推荐统一使用 `-`）：

```markdown
- 项目一
- 项目二
  - 子项目 A
  - 子项目 B
    - 深层嵌套
- 项目三
```

**有序列表**：

```markdown
1. 第一步
2. 第二步
3. 第三步
```

**任务列表（Checklist）**：

```markdown
- [ ] 未完成的任务
- [x] 已完成的任务
- [>] 已归档的任务
- [-] 已取消的任务
```

### 1.3 代码块（Fenced Code Blocks）

使用三个反引号包裹，可指定语言实现语法高亮：

````markdown
```python
def hello():
    print("Hello, Obsidian!")
```
````

常用语言标识：`python`、`javascript`、`typescript`、`java`、`bash`、`sql`、`json`、`yaml`、`markdown`、`css`、`html` 等。

**行内代码**：使用单个反引号包裹，如 `` `inline code` ``。

### 1.4 块引用（Blockquotes）

```markdown
> 这是一段引用文本
> 可以跨多行
>
> 也可以有空行分隔多个段落
```

**嵌套引用**：

```markdown
> 外层引用
>> 内层嵌套引用
>>> 更深的嵌套
```

### 1.5 水平分隔线（Horizontal Rules）

```markdown
---
```

或使用 `***`、`___`。Obsidian 会将水平线渲染为视觉分隔。

### 1.6 表格（Tables）

```markdown
| 列1 | 列2 | 列3 |
|-----|-----|-----|
| 内容1 | 内容2 | 内容3 |
| 左对齐 | 居中 | 右对齐 |
```

- 使用 `---` 定义表头与内容的分隔
- 使用 `:` 控制对齐：`---:` 右对齐，`:---:` 居中，`:---` 左对齐

---

## 2. 双向链接（Bidirectional Links）

双向链接是 Obsidian 的核心特性，实现了笔记间的自动关联。

### 2.1 维基链接（Wikilinks）

语法：`[[目标页面]]`

```markdown
[[My Note]]              # 链接到 "My Note"
[[My Note|显示文本]]     # 链接到 "My Note" 但显示为"显示文本"
[[My Note#章节]]         # 链接到 "My Note" 的 "章节" 标题
[[My Note#章节|别名]]    # 组合使用
```

### 2.2 嵌入（Embeds）

使用 `!` 前缀将另一笔记的完整内容嵌入当前位置：

```markdown
![[My Note]]             # 嵌入整篇笔记
![[My Note#Heading]]     # 只嵌入指定标题下的内容
![[My Note|截取的别名]]   # 嵌入时使用别名
![[My Note.png]]         # 嵌入图片
```

**嵌入代码块**：

````markdown
![[My Note]]
```python
# 被嵌入笔记中的代码块
```
````

### 2.3 链接到特定块（Block References）

通过复制块 ID 链接到特定段落：

```markdown
[[My Note^block-id]]
```

### 2.4 外部链接（External Links）

```markdown
[显示文本](https://example.com)
<https://example.com>    # 自动超链接
```

---

## 3. 标签（Tags）

### 3.1 基本标签

标签以 `#` 开头，不含空格，可使用字母、数字、下划线和连字符：

```markdown
#tag
#2024-01-15
#project/active
#topic/subtopic/nested
```

### 3.2 标签层级（Hierarchical Tags）

```markdown
#工作
#工作/项目A
#工作/项目A/任务1
```

父标签会自动包含子标签的含义，搜索 `#工作` 会包含所有 `#工作/项目A` 等子标签。

### 3.3 YAML Frontmatter 中的标签

```yaml
---
tags:
  - 标签1
  - 标签2
  - 父标签/子标签
---
```

### 3.4 标签命名规范

- 推荐使用小写（Obsidian 搜索不区分大小写）
- 避免在标签中使用空格，使用 `/` 分层
- 常见模式：`#area/topic`、`#type/format`、`#status/state`

---

## 4. YAML Frontmatter（元数据）

Frontmatter 必须位于笔记顶部，用三横线 `---` 包裹：

```yaml
---
uid: 20240115a
title: 我的笔记标题
tags: [标签1, 标签2]
alias: 别名
created: 2024-01-15
modified: 2024-01-16
cssclasses:
  - table-flat
publish: true
---

正文内容从这里开始...
```

### 4.1 常用字段

| 字段 | 说明 | 示例 |
|------|------|------|
| `uid` | 唯一标识符 | `uid: 20240115a` |
| `title` | 笔记标题（覆盖文件名） | `title: 自定义标题` |
| `tags` | 标签数组 | `tags: [工作, 项目]` |
| `alias` / `aliases` | 别名（可用于搜索） | `aliases: [别名1, 别名2]` |
| `created` | 创建时间 | `created: 2024-01-15` |
| `modified` | 修改时间 | `modified: 2024-01-16` |
| `cssclasses` | 自定义 CSS 类 | `cssclasses: [table-flat]` |
| `publish` | 是否发布 | `publish: true` |
| `permalink` | 自定义永久链接 | `permalink: /custom-path/` |

---

## 5. Dataview 查询语言（DQL）

Dataview 插件提供强大的查询能力。

### 5.1 基本查询命令

**TABLE** — 表格视图：

````markdown
```dataview
TABLE file.name, file.ctime, tags
FROM ""
WHERE contains(tags, "项目")
SORT file.ctime DESC
```
````

**LIST** — 列表视图：

````markdown
```dataview
LIST file.name
FROM ""
WHERE contains(tags, "待办")
```
````

**TASK** — 任务视图：

````markdown
```dataview
TASK
FROM ""
WHERE !completed
```
````

### 5.2 常用操作符

| 操作 | 说明 | 示例 |
|------|------|------|
| `WHERE` | 过滤条件 | `WHERE file.size > 1000` |
| `SORT` | 排序 | `SORT file.mtime DESC` |
| `FLATTEN` | 展开数组 | `FLATTEN file.tags AS tag` |
| `GROUP BY` | 分组 | `GROUP BY file.folder` |
| `LIMIT` | 限制数量 | `LIMIT 10` |

### 5.3 常用字段

- `file.name` — 文件名
- `file.path` — 文件路径
- `file.ctime` — 创建时间
- `file.mtime` — 修改时间
- `file.size` — 文件大小
- `file.tags` — 所有标签
- `file.links` — 所有出链
- `file.outlinks` — 外部链接
- `file.inlinks` — 指向此文件的所有链接
- `tags` — frontmatter 中的 tags 字段

### 5.4 常用表达式

```dataview
WHERE contains(file.tags, "重要")
WHERE file.ctime >= date(2024-01-01)
WHERE length(file.links) > 5
WHERE !contains(file.path, "模板")
```

---

## 6. Callouts（标注块）

Callouts 提供视觉化的信息分类和强调。

### 6.1 基本语法

````markdown
> [!note]
> 这是笔记类型的标注

> [!warning]
> 这是警告类型的标注
````

### 6.2 支持的类型

| 类型 | 含义 | 颜色倾向 |
|------|------|----------|
| `note` | 信息提示 | 蓝 |
| `abstract`, `summary`, `tldr` | 摘要/总结 | 青 |
| `info` | 更多信息 | 蓝 |
| `todo` | 待办事项 | 蓝 |
| `tip`, `hint`, `important` | 技巧/重要 | 绿 |
| `success`, `done`, `check` | 成功/完成 | 绿 |
| `question`, `help`, `faq` | 问题/帮助 | 绿 |
| `warning`, `caution`, `attention` | 警告/注意 | 黄 |
| `failure`, `missing`, `fail` | 失败/缺失 | 红 |
| `danger`, `error` | 危险/错误 | 红 |
| `bug` | Bug | 红 |
| `example` | 示例 | 紫 |
| `quote`, `cite` | 引用 | 灰 |

### 6.3 可折叠 Callouts

````markdown
> [!note]+
> 点击可展开（默认折叠）

> [!note]-
> 点击可折叠（默认展开）
````

### 6.4 自定义标题

````markdown
> [!note] 自定义标题
> 这里的内容会使用自定义标题
````

### 6.5 嵌套使用

Callouts 可以嵌套到任意深度：

````markdown
> [!note]
> 外层
>> [!warning]
>> 内层警告
````

---

## 7. Obsidian 特性与规范

### 7.1 内部链接 vs 外部链接

| 类型 | 语法 | 说明 |
|------|------|------|
| 内部链接 | `[[笔记名]]` | 指向本地笔记库 |
| 嵌入 | `![[笔记名]]` | 在当前位置显示完整内容 |
| 外部链接 | `[文本](URL)` | 指向网络资源 |

### 7.2 路径规范

**绝对路径 vs 相对路径**：

- Obsidian 内部链接使用笔记名（Vault 范围内唯一）
- 相对路径可用于引用附件：`![[附件图片.png]]`
- 建议使用简短文件名，便于链接和维护

**附件文件夹**：
- 默认附件放在 Vault 根目录或 `attachments` 文件夹
- 可在设置中自定义附件存放位置

### 7.3 文件命名建议

- 使用有意义的名字，便于搜索和链接
- 避免特殊字符（`#`、`|`、`\`、`/`、`?` 等）
- 推荐格式：`驼峰命名` 或 `中划线分隔`
- 使用日期前缀：`2024-01-15 笔记标题`

### 7.4 搜索与跳转

- `Cmd/Ctrl + O` — 快速切换器（Quick Switcher）
- `Cmd/Ctrl + K` — 插入内部链接
- `Cmd/Ctrl + Shift + F` — 全局搜索
- `[[链接]]` — 输入 `[[` 触发自动补全

---

## 8. 高级特性

### 8.1 高亮文本

```markdown
这是 ^^高亮文本^^
这是 ==另一种高亮==
```

### 8.2 脚注（Footnotes）

```markdown
这是正文内容[^1]

[^1]: 这是脚注内容
```

### 8.3 注释

```markdown
%% 这是注释，不会显示在阅读视图 %%
```

### 8.4 属性（Properties）

Obsidian 1.0+ 引入了新的属性系统：

```yaml
---
uid: my-unique-id
tags:
  - 项目
  - 重要
---

# 我的笔记
```

---

## 9. 快捷操作汇总

| 操作 | 快捷键 |
|------|--------|
| 插入链接 | `Cmd/Ctrl + K` |
| 快速切换 | `Cmd/Ctrl + O` |
| 命令面板 | `Cmd/Ctrl + P` |
| 切换侧边栏 | `Cmd/Ctrl + B` |
| 预览/编辑 | `Cmd/Ctrl + E` |
| 加粗 | `Cmd/Ctrl + B` |
| 斜体 | `Cmd/Ctrl + I` |
| 代码块 | `Cmd/Ctrl + Shift + C` |
| 搜索 | `Cmd/Ctrl + Shift + F` |
| 标签面板 | `Cmd/Ctrl + Shift + #` |

---

> 本文档为 Obsidian 语法参考，Agent 初始化时自动加载，无需显式读取。
