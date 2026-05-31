"""
Obsidian Syntax Reference Module

This module exports structured Obsidian syntax data for LLM initialization.
It provides the agent with innate knowledge of Obsidian markdown syntax.

Author: Conway's Agent
"""

OBSIDIAN_SYNTAX = {
    "version": "1.0.0",
    "language": "zh-CN",
    "description": "Obsidian 语法参考 — 内嵌到 Agent 初始化配置",
    "categories": {
        "markdown_basics": {
            "headings": {
                "description": "标题语法",
                "syntax": {
                    "#": "一级标题",
                    "##": "二级标题",
                    "###": "三级标题",
                    "####": "四级标题",
                    "#####": "五级标题",
                    "######": "六级标题"
                }
            },
            "lists": {
                "unordered": {
                    "description": "无序列表",
                    "symbols": ["-", "*", "+"],
                    "recommended": "-"
                },
                "ordered": {
                    "description": "有序列表",
                    "example": "1. 项目一\n2. 项目二"
                },
                "tasks": {
                    "description": "任务列表",
                    "syntax": {
                        "- [ ]": "未完成",
                        "- [x]": "已完成",
                        "- [>]": "已归档",
                        "- [-]": "已取消"
                    }
                },
                "nested": {
                    "description": "嵌套列表",
                    "example": "- 一级\n  - 二级\n    - 三级"
                }
            },
            "code_blocks": {
                "fenced": {
                    "description": "代码块（ fenced code blocks ）",
                    "example": "```python\ndef hello():\n    print('Hello')\n```"
                },
                "inline": {
                    "description": "行内代码",
                    "example": "`inline code`"
                }
            },
            "blockquotes": {
                "description": "块引用",
                "syntax": "> 引用文本",
                "nested": ">> 嵌套引用"
            },
            "horizontal_rules": {
                "description": "水平分隔线",
                "syntax": ["---", "***", "___"]
            },
            "tables": {
                "description": "表格",
                "example": "| 列1 | 列2 |\n|-----|-----|\n| 内容 | 内容 |",
                "alignment": {
                    ":---": "左对齐",
                    ":---:": "居中",
                    "---:": "右对齐"
                }
            }
        },
        "bidirectional_links": {
            "description": "双向链接 — Obsidian 核心特性",
            "wikilinks": {
                "basic": {"syntax": "[[页面名]]", "description": "基础链接"},
                "alias": {"syntax": "[[页面|别名]]", "description": "带别名显示"},
                "heading": {"syntax": "[[页面#章节]]", "description": "链接到特定标题"},
                "combined": {"syntax": "[[页面#章节|别名]]", "description": "组合使用"}
            },
            "embeds": {
                "description": "嵌入 — 将目标笔记内容显示在当前位置",
                "full": {"syntax": "![[页面名]]", "description": "嵌入整篇笔记"},
                "heading": {"syntax": "![[页面#章节]]", "description": "嵌入特定标题下内容"},
                "image": {"syntax": "![[图片.png]]", "description": "嵌入图片"}
            },
            "block_references": {
                "description": "块引用",
                "syntax": "[[页面^块ID]]"
            },
            "external_links": {
                "description": "外部链接",
                "syntax": "[显示文本](https://example.com)",
                "autolink": "<https://example.com>"
            }
        },
        "tags": {
            "description": "标签系统",
            "basic": {
                "syntax": "#tag",
                "rules": ["不含空格", "可用字母/数字/下划线/连字符", "搜索不区分大小写"]
            },
            "hierarchical": {
                "syntax": "#parent/child",
                "example": "#工作/项目A/任务1",
                "description": "子标签自动包含父标签的搜索结果"
            },
            "frontmatter": {
                "syntax": "tags: [标签1, 标签2]"
            },
            "patterns": {
                "recommended": ["#area/topic", "#type/format", "#status/state"]
            }
        },
        "yaml_frontmatter": {
            "description": "YAML Frontmatter — 文件元数据",
            "delimiter": "---",
            "position": "文件顶部",
            "fields": {
                "uid": {"type": "string", "description": "唯一标识符"},
                "title": {"type": "string", "description": "笔记标题（覆盖文件名）"},
                "tags": {"type": "array", "description": "标签列表"},
                "alias/aliases": {"type": "string/array", "description": "别名"},
                "created": {"type": "date", "description": "创建时间"},
                "modified": {"type": "date", "description": "修改时间"},
                "cssclasses": {"type": "array", "description": "自定义 CSS 类"},
                "publish": {"type": "boolean", "description": "是否发布"}
            },
            "example": """---
uid: 20240115a
title: 我的笔记
tags: [标签1, 标签2]
created: 2024-01-15
---"""
        },
        "dataview_dql": {
            "description": "Dataview 查询语言",
            "commands": {
                "TABLE": {
                    "description": "表格视图",
                    "example": "TABLE file.name, tags FROM \"\" WHERE contains(tags, \"项目\")"
                },
                "LIST": {
                    "description": "列表视图",
                    "example": "LIST file.name FROM \"\" WHERE contains(tags, \"待办\")"
                },
                "TASK": {
                    "description": "任务视图",
                    "example": "TASK FROM \"\" WHERE !completed"
                }
            },
            "operations": {
                "WHERE": "过滤条件",
                "SORT": "排序 (ASC/DESC)",
                "FLATTEN": "展开数组",
                "GROUP BY": "分组",
                "LIMIT": "限制数量"
            },
            "fields": {
                "file.name": "文件名",
                "file.path": "文件路径",
                "file.ctime": "创建时间",
                "file.mtime": "修改时间",
                "file.size": "文件大小",
                "file.tags": "所有标签",
                "file.links": "所有出链",
                "file.inlinks": "所有入链"
            }
        },
        "callouts": {
            "description": "标注块 — 可折叠的信息卡片",
            "types": {
                "note": {"description": "笔记提示", "color": "blue"},
                "abstract/summary/tldr": {"description": "摘要/总结", "color": "cyan"},
                "info": {"description": "更多信息", "color": "blue"},
                "tip/hint/important": {"description": "技巧/重要", "color": "green"},
                "success/done/check": {"description": "成功/完成", "color": "green"},
                "question/help/faq": {"description": "问题/帮助", "color": "green"},
                "warning/caution/attention": {"description": "警告/注意", "color": "yellow"},
                "failure/missing/fail": {"description": "失败/缺失", "color": "red"},
                "danger/error": {"description": "危险/错误", "color": "red"},
                "bug": {"description": "Bug", "color": "red"},
                "example": {"description": "示例", "color": "purple"},
                "quote/cite": {"description": "引用", "color": "gray"}
            },
            "collapsible": {
                "+": "默认折叠，点击展开",
                "-": "默认展开，点击折叠"
            },
            "custom_title": "[!note] 自定义标题",
            "syntax": """> [!note]
> 内容"""
        },
        "obsidian_specifics": {
            "links": {
                "internal": {
                    "syntax": "[[wikilink]]",
                    "description": "内部链接指向本地笔记库"
                },
                "external": {
                    "syntax": "[text](url)",
                    "description": "外部链接指向网络资源"
                },
                "embed": {
                    "syntax": "![[embed]]",
                    "description": "嵌入显示目标笔记内容"
                }
            },
            "path_conventions": {
                "note_reference": "使用笔记名（Vault 范围内唯一）",
                "attachment": "可使用相对路径引用附件",
                "naming": {
                    "recommendations": ["有意义的名字", "避免特殊字符"],
                    "patterns": ["camelCase", "kebab-case", "日期前缀 YYYY-MM-DD"]
                }
            }
        },
        "advanced": {
            "highlight": {
                "syntax": "^^高亮文本^^",
                "alternative": "==另一种高亮=="
            },
            "footnotes": {
                "syntax": "正文[^1]\n[^1]: 脚注内容"
            },
            "comments": {
                "syntax": "%% 注释内容 %%",
                "description": "不会在阅读视图显示"
            },
            "properties": {
                "description": "Obsidian 1.0+ 属性系统",
                "example": """---
uid: my-unique-id
tags:
  - 项目
---"""
            }
        },
        "shortcuts": {
            "insert_link": "Cmd/Ctrl + K",
            "quick_switcher": "Cmd/Ctrl + O",
            "command_palette": "Cmd/Ctrl + P",
            "toggle_sidebar": "Cmd/Ctrl + B",
            "preview_edit": "Cmd/Ctrl + E",
            "bold": "Cmd/Ctrl + B",
            "italic": "Cmd/Ctrl + I",
            "code_block": "Cmd/Ctrl + Shift + C",
            "global_search": "Cmd/Ctrl + Shift + F"
        }
    }
}


def get_syntax_prompt() -> str:
    """
    生成用于 LLM 初始化的提示文本。
    
    Returns:
        str: 格式化的 Obsidian 语法提示
    """
    sections = []
    
    sections.append("你具备以下 Obsidian 语法知识，可直接使用：\n")
    
    # Markdown 基础
    sections.append("## Markdown 基础")
    sections.append("- 标题: # ## ### #### ##### ######")
    sections.append("- 列表: - 项目 (无序), 1. 项目 (有序), - [ ] 任务")
    sections.append("- 代码: ```语言\\n代码\\n``` (块), `code` (行内)")
    sections.append("- 引用: > 文本")
    sections.append("- 分隔线: ---")
    sections.append("- 表格: | 列 | 列 |\\n|---|---|\\n| 内容 | 内容 |")
    sections.append("")
    
    # 双向链接
    sections.append("## 双向链接 (Obsidian 核心)")
    sections.append("- [[页面]] - 链接到页面")
    sections.append("- [[页面|别名]] - 带别名显示")
    sections.append("- [[页面#章节]] - 链接到特定标题")
    sections.append("- ![[页面]] - 嵌入页面内容")
    sections.append("- [[页面#章节|别名]] - 组合使用")
    sections.append("")
    
    # 标签
    sections.append("## 标签")
    sections.append("- #tag - 基本标签")
    sections.append("- #parent/child - 层级标签")
    sections.append("- YAML 中: tags: [标签1, 标签2]")
    sections.append("")
    
    # YAML Frontmatter
    sections.append("## YAML Frontmatter")
    sections.append("- 用 --- 包裹，位于文件顶部")
    sections.append("- 常用字段: uid, title, tags, alias, created, modified")
    sections.append("")
    
    # Callouts
    sections.append("## Callouts (标注块)")
    sections.append("- [!note], [!warning], [!tip], [!danger], [!info]")
    sections.append("- [!note]+ 可折叠（默认折叠）")
    sections.append("- [!note]- 可折叠（默认展开）")
    sections.append("")
    
    # Dataview
    sections.append("## Dataview 查询")
    sections.append("- TABLE field1, field2 FROM \"\" WHERE condition")
    sections.append("- LIST file.name FROM \"\"")
    sections.append("- TASK FROM \"\" WHERE !completed")
    sections.append("- 支持 WHERE, SORT, LIMIT, GROUP BY")
    sections.append("")
    
    return "\n".join(sections)


def get_knowledge_files() -> dict:
    """
    获取知识文件路径映射。
    
    Returns:
        dict: 文件路径 -> 描述
    """
    return {
        "agent/knowledge/obsidian-syntax.md": "内嵌知识 — Obsidian 语法参考",
        "agent/knowledge/obsidian-skills.md": "建议性知识 — PKM 最佳实践"
    }


__all__ = ["OBSIDIAN_SYNTAX", "get_syntax_prompt", "get_knowledge_files"]
