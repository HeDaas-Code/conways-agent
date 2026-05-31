"""
Deep Terminal UI for Conway's Agent

A rich terminal/TUI interface for deep Agent interaction and behavior monitoring.
Supports Textual (if available) for full TUI, or falls back to Rich for terminal UI.

Run with:
    python -m agent.ui.deep_terminal

Commands:
    /why          - Explain why Agent gave this response
    /fragments    - Show world fragments used in response
    /think        - Show Agent's thinking process
    /status       - Show full Agent status
    /goals        - Show goals and progress
    /logs         - Open processing log panel
    /world        - Open world browser
    /quit         - Exit
"""

from __future__ import annotations

import asyncio
import signal
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

HAS_TEXTUAL = False
HAS_RICH = False

try:
    from textual.app import App
    from textual.widgets import Static, Log, Input, Button
    from textual.containers import Container, Horizontal, Vertical
    HAS_TEXTUAL = True
except ImportError:
    pass

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.layout import Layout
    from rich.text import Text
    from rich.table import Table
    from rich.live import Live
    from rich.progress import Progress, BarColumn, TextColumn
    HAS_RICH = True
except ImportError:
    pass

from agent.core.state import AgentState
from agent.core.goals import GoalSystem, Goal
from agent.core.memory import MemorySystem
from agent.core.world_fragment import WorldFragment
from agent.core.attention import AttentionWindow
from agent.core.perception import PerceptionSystem, PerceptionInput
from agent.core.curiosity import CuriositySystem, TerritoryNode
from agent.core.vitality import VaultVitalityMonitor
from agent.core.dialogue import DialogueSession
from agent.core.llm import LLMClient
from agent.log import get_recent_logs


@dataclass
class DialogueEntry:
    """A single dialogue entry."""
    role: str  # "user" | "agent" | "system" | "think"
    content: str
    timestamp: datetime = field(default_factory=datetime.now)
    fragments_used: list[str] = field(default_factory=list)
    fit_judgment: str = ""
    thinking: str = ""


@dataclass
class ProcessingLogEntry:
    """A processing log entry."""
    type: str  # "perception" | "processing" | "writing" | "goal" | "attention"
    message: str
    timestamp: datetime = field(default_factory=datetime.now)


class DeepTerminalInterface:
    """
    Deep Terminal Interface for Conway's Agent.
    
    Provides:
    - Status Panel (top): Agent state, curiosity level, active goals, memory freshness
    - Behavior Monitor (left): Recent perceptions, goals, attention window, curiosity map
    - Deep Dialogue (center): Full conversation history with thinking process visible
    - Processing Log (bottom): Real-time log of Agent activities
    - World Browser (right, collapsible): Browse world corpus, view fragments, link graph
    """
    
    def __init__(self, state: AgentState, vault_path: Path):
        self.state = state
        self.vault_path = vault_path
        
        self.console = Console() if HAS_RICH else None
        
        self.memory = MemorySystem()
        self.goals = GoalSystem(vault_path)
        self.curiosity = CuriositySystem(self.memory)
        self.perception = PerceptionSystem()
        self.attention = AttentionWindow(max_slots=state.attention_window_size)
        self.vitality = VaultVitalityMonitor(vault_path)
        
        self.dialogue_history: list[DialogueEntry] = []
        self.processing_logs: list[ProcessingLogEntry] = []
        self.current_thinking: str = ""
        self.last_response_fragments: list[str] = []
        self.last_fit_judgment: str = ""
        
        self.world_browser_visible = False
        self.logs_panel_visible = False
        self.selected_fragment_index = 0
        
        self._running = False
    
    def add_processing_log(self, log_type: str, message: str) -> None:
        """Add a log entry."""
        entry = ProcessingLogEntry(type=log_type, message=message)
        self.processing_logs.append(entry)
        if len(self.processing_logs) > 500:
            self.processing_logs = self.processing_logs[-500:]
    
    def add_dialogue(self, role: str, content: str, **kwargs) -> None:
        """Add a dialogue entry."""
        entry = DialogueEntry(
            role=role,
            content=content,
            fragments_used=kwargs.get("fragments_used", []),
            fit_judgment=kwargs.get("fit_judgment", ""),
            thinking=kwargs.get("thinking", "")
        )
        self.dialogue_history.append(entry)
        self.last_response_fragments = entry.fragments_used
        self.last_fit_judgment = entry.fit_judgment
    
    def get_curiosity_bar(self) -> str:
        """Get a visual curiosity level bar."""
        level = self.state.curiosity_level
        filled = int(level * 20)
        return "█" * filled + "░" * (20 - filled)
    
    def get_memory_freshness_avg(self) -> float:
        """Calculate average memory freshness."""
        try:
            fragments = self.memory.read_all_fragments()
            if not fragments:
                return 0.0
            
            from agent.core.decay import get_decay_system
            decay = get_decay_system()
            total_freshness = 0.0
            
            for fragment in fragments:
                freshness = decay.get_freshness(fragment.title)
                total_freshness += freshness
            
            return total_freshness / len(fragments)
        except Exception:
            return 0.0
    
    def format_status_panel(self) -> Table:
        """Format the status panel."""
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column(style="bold")
        table.add_column()
        
        state_icon = "☀" if self.state.sleep_state == "awake" else "☾"
        curiosity_bar = self.get_curiosity_bar()
        freshness = self.get_memory_freshness_avg()
        active_goals = self.goals.get_active_goals()
        
        table.add_row(f"{state_icon} 状态:", self.state.sleep_state)
        table.add_row("✧ 好奇心:", f"{curiosity_bar} {self.state.curiosity_level:.1%}")
        table.add_row("◎ 活跃目标:", str(len(active_goals)))
        table.add_row("◇ 记忆新鲜度:", f"{freshness:.1%}")
        table.add_row("↻ 总循环:", str(self.state.total_cycles))
        
        return table
    
    def format_behavior_monitor(self) -> Table:
        """Format the behavior monitor panel."""
        table = Table(show_header=True, box=None, padding=(0, 1))
        table.add_column("项目", style="bold cyan")
        table.add_column("内容")
        
        recent_perceptions = self.perception.get_recent_perceptions(5)
        if recent_perceptions:
            perc_str = ", ".join(p.file_path.split("/")[-1] for p in recent_perceptions[:3])
            table.add_row("最近感知", perc_str)
        else:
            table.add_row("最近感知", "无")
        
        active_goals = self.goals.get_active_goals()
        if active_goals:
            goals_str = "\n".join(f"• {g.title[:30]}" for g in active_goals[:3])
            table.add_row("活跃目标", goals_str)
        else:
            table.add_row("活跃目标", "无")
        
        attention_status = self.attention.get_status()
        table.add_row("注意力窗口", f"{attention_status['active_count']}/{attention_status['max_slots']}")
        
        curiosity_map = self.curiosity.get_map_summary()
        table.add_row("探索地图", f"{curiosity_map['explored']}/{curiosity_map['total_nodes']} 已探索")
        
        return table
    
    def format_deep_dialogue(self, limit: int = 20) -> list[str]:
        """Format deep dialogue history."""
        lines = []
        for entry in self.dialogue_history[-limit:]:
            timestamp = entry.timestamp.strftime("%H:%M")
            
            if entry.role == "user":
                lines.append(f"[{timestamp}] 你: {entry.content}")
            elif entry.role == "agent":
                lines.append(f"[{timestamp}] Agent: {entry.content}")
                if entry.thinking:
                    lines.append(f"       💭 {entry.thinking[:100]}...")
            elif entry.role == "think":
                lines.append(f"[{timestamp}] 💭 {entry.content}")
        
        return lines
    
    def format_processing_log(self, filter_type: Optional[str] = None, limit: int = 30) -> list[str]:
        """Format processing log entries."""
        logs = self.processing_logs[-limit:]
        if filter_type:
            logs = [l for l in logs if l.type == filter_type]
        
        lines = []
        for log in logs:
            timestamp = log.timestamp.strftime("%H:%M:%S")
            icon = {
                "perception": "👁",
                "processing": "⚙",
                "writing": "✎",
                "goal": "◎",
                "attention": "◉"
            }.get(log.type, "•")
            
            lines.append(f"[{timestamp}] {icon} {log.message}")
        
        return lines
    
    def format_world_browser(self) -> Table:
        """Format world corpus browser."""
        table = Table(show_header=True, box=None, title="世界碎片浏览器")
        table.add_column("标题", style="cyan")
        table.add_column("路径", style="dim")
        table.add_column("创建时间")
        
        fragments = self.memory.read_all_fragments()
        for fragment in fragments[-10:]:
            table.add_row(
                fragment.title[:30],
                fragment.fit_path,
                fragment.created_at.strftime("%Y-%m-%d")
            )
        
        return table
    
    def render_rich_ui(self) -> None:
        """Render the full UI using Rich."""
        if not HAS_RICH or not self.console:
            return
        
        layout = Layout()
        
        header = Panel(
            self.format_status_panel(),
            title=" Agent 状态 ",
            border_style="cyan"
        )
        
        behavior = Panel(
            self.format_behavior_monitor(),
            title=" 行为监控 ",
            border_style="green"
        )
        
        dialogue_content = "\n".join(self.format_deep_dialogue())
        dialogue = Panel(
            dialogue_content or "对话历史为空",
            title=" 深度对话 ",
            border_style="yellow"
        )
        
        log_content = "\n".join(self.format_processing_log())
        log_panel = Panel(
            log_content or "日志为空",
            title=" 处理日志 ",
            border_style="magenta"
        )
        
        if self.world_browser_visible:
            world = Panel(
                str(self.format_world_browser()),
                title=" 世界浏览器 ",
                border_style="blue"
            )
            layout.split_column(
                Layout(header, name="header", size=8),
                Layout(behavior, name="behavior", size=15),
                Layout(dialogue, name="dialogue"),
                Layout(log_panel, name="logs"),
                Layout(world, name="world", size=12)
            )
        else:
            layout.split_column(
                Layout(header, name="header", size=8),
                Layout(behavior, name="behavior", size=15),
                Layout(dialogue, name="dialogue"),
                Layout(log_panel, name="logs")
            )
        
        self.console.clear()
        self.console.print(layout)
    
    def handle_command(self, cmd: str) -> Optional[str]:
        """Handle a UI command."""
        cmd = cmd.strip()
        
        if cmd in ("/quit", "/q", "quit", "exit"):
            self._running = False
            return None
        
        if cmd in ("/why",):
            if self.dialogue_history:
                last_agent = None
                for entry in reversed(self.dialogue_history):
                    if entry.role == "agent":
                        last_agent = entry
                        break
                if last_agent:
                    response = f"【为什么这么回应】\n"
                    response += f"判断类型: {last_agent.fit_judgment or 'translation'}\n"
                    response += f"使用的碎片: {', '.join(last_agent.fragments_used) or '无'}\n"
                    if last_agent.thinking:
                        response += f"思考过程: {last_agent.thinking}"
                    return response
            return "【解释】暂无对话历史"
        
        if cmd in ("/fragments",):
            if self.last_response_fragments:
                response = "【响应中使用的世界碎片】\n"
                for frag_title in self.last_response_fragments:
                    frag = self.memory.get_fragment_by_title(frag_title)
                    if frag:
                        response += f"\n• {frag.title}\n"
                        response += f"  {frag.content[:100]}...\n"
                        response += f"  路径: {frag.fit_path}\n"
                return response
            return "【碎片】暂无使用的碎片记录"
        
        if cmd in ("/think",):
            if self.current_thinking:
                return f"【当前思考】\n{self.current_thinking}"
            if self.dialogue_history:
                for entry in reversed(self.dialogue_history):
                    if entry.thinking:
                        return f"【最近思考】\n{entry.thinking}"
            return "【思考】暂无思考过程记录"
        
        if cmd in ("/status",):
            return self.format_full_status()
        
        if cmd in ("/goals",):
            return self.format_goals()
        
        if cmd in ("/logs",):
            self.logs_panel_visible = not self.logs_panel_visible
            return f"【日志面板】{'已打开' if self.logs_panel_visible else '已关闭'}"
        
        if cmd in ("/world",):
            self.world_browser_visible = not self.world_browser_visible
            return f"【世界浏览器】{'已打开' if self.world_browser_visible else '已关闭'}"
        
        if cmd.startswith("/log "):
            log_type = cmd[5:].strip()
            logs = self.format_processing_log(filter_type=log_type)
            return f"【日志 {log_type}】\n" + "\n".join(logs) if logs else f"无 {log_type} 类型日志"
        
        return None
    
    def format_full_status(self) -> str:
        """Format full agent status."""
        active_goals = self.goals.get_active_goals()
        curiosity_map = self.curiosity.get_map_summary()
        freshness = self.get_memory_freshness_avg()
        
        status = "【Agent 完整状态】\n\n"
        
        status += "基础信息:\n"
        status += f"  名称: {self.state.personality.get('name', '未知')}\n"
        status += f"  状态: {self.state.sleep_state}\n"
        status += f"  总循环: {self.state.total_cycles}\n\n"
        
        status += "认知指标:\n"
        status += f"  好奇心: {self.state.curiosity_level:.1%} {self.get_curiosity_bar()}\n"
        status += f"  记忆新鲜度: {freshness:.1%}\n"
        status += f"  注意力窗口: {self.attention.get_status()['active_count']}/{self.state.attention_window_size}\n\n"
        
        status += "目标系统:\n"
        status += f"  活跃目标: {len(active_goals)}\n"
        for goal in active_goals[:5]:
            status += f"    • {goal.title} ({goal.status})\n"
        
        status += "\n探索地图:\n"
        status += f"  总节点: {curiosity_map['total_nodes']}\n"
        status += f"  已探索: {curiosity_map['explored']}\n"
        status += f"  孤儿节点: {curiosity_map['orphans']}\n"
        status += f"  好奇心强度: {curiosity_map['curiosity_intensity']:.1%}\n"
        
        status += "\n个性特征:\n"
        traits = self.state.personality.get("traits", {})
        for trait, value in traits.items():
            status += f"  {trait}: {value:.1%}\n"
        
        return status
    
    def format_goals(self) -> str:
        """Format goals and progress."""
        all_goals = self.goals.get_all_goals()
        active_goals = self.goals.get_active_goals()
        
        status = "【目标与进度】\n\n"
        status += f"总计: {len(all_goals)} 个目标\n"
        status += f"活跃: {len(active_goals)} 个\n\n"
        
        if active_goals:
            status += "活跃目标:\n"
            for goal in active_goals:
                status += f"\n📌 {goal.title}\n"
                status += f"   状态: {goal.status}\n"
                status += f"   创建: {goal.created.strftime('%Y-%m-%d %H:%M')}\n"
                if goal.children:
                    status += f"   子目标: {len(goal.children)} 个\n"
                if goal.execution_log:
                    last_log = goal.execution_log[-1] if goal.execution_log else ""
                    status += f"   最近日志: {last_log[:50]}...\n"
        
        return status
    
    async def run_async(self) -> None:
        """Run the interface asynchronously (for Textual)."""
        if HAS_TEXTUAL:
            await self.run_textual()
        else:
            self.run_rich()
    
    def run_rich(self) -> None:
        """Run the Rich-based interface."""
        if not HAS_RICH:
            print("错误: 需要 rich 库。运行: pip install rich")
            return
        
        self._running = True
        self.add_processing_log("system", "深度终端界面已启动")
        
        print("\n" + "=" * 60)
        print("  Conway's Agent — 深度终端界面")
        print("  输入 /help 查看可用命令")
        print("=" * 60 + "\n")
        
        self.render_rich_ui()
        
        while self._running:
            try:
                user_input = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n\n退出中...")
                break
            
            if not user_input:
                continue
            
            if user_input.startswith("/"):
                response = self.handle_command(user_input)
                if response:
                    print(f"\n{response}")
                self.render_rich_ui()
                continue
            
            self.add_processing_log("perception", f"用户输入: {user_input[:50]}...")
            self.add_dialogue("user", user_input)
            
            self.current_thinking = "正在思考响应..."
            print("\n[正在生成响应...]")
            
            try:
                llm = LLMClient()
                dialogue = DialogueSession(
                    llm_client=llm,
                    state=self.state,
                    pipeline=None
                )
                
                response = dialogue.user_speak(user_input)
                self.current_thinking = dialogue.last_thinking if hasattr(dialogue, 'last_thinking') else ""
                
                self.add_dialogue(
                    "agent",
                    response,
                    fit_judgment="translation",
                    thinking=self.current_thinking
                )
                
                self.add_processing_log("processing", f"生成响应完成")
                
            except Exception as e:
                response = f"生成响应时出错: {e}"
                self.add_processing_log("error", str(e))
            
            print(f"\nAgent: {response}\n")
            self.render_rich_ui()
        
        print("\n深度终端界面已退出。")

    async def run_textual(self) -> None:
        """Run the Textual-based TUI."""
        from textual.app import App, ComposeResult
        from textual.widgets import Static, Log, Input, Button, Header, Footer
        from textual.containers import Container, Horizontal, Vertical, ScrollableContainer
        from textual import events
        
        class DeepTerminalApp(App):
            """Textual App for Deep Terminal."""
            
            CSS = """
            Screen {
                background: $surface;
            }
            
            #header {
                height: 3;
                background: $primary;
                color: $text;
                dock: top;
            }
            
            #main {
                layout: horizontal;
                height: 1fr;
            }
            
            #left-panel {
                width: 30;
                border: solid $primary;
            }
            
            #center-panel {
                width: 1fr;
                border: solid $accent;
            }
            
            #right-panel {
                width: 35;
                border: solid $info;
                display: none;
            }
            
            #right-panel.visible {
                display: block;
            }
            
            #bottom-panel {
                height: 12;
                border: solid $warning;
            }
            
            #input-area {
                height: 3;
                dock: bottom;
                background: $surface;
            }
            
            .panel-title {
                background: $primary;
                color: $text;
                padding: 0 1;
            }
            
            ScrollableContainer {
                height: 1fr;
            }
            """
            
            BINDINGS = [
                ("q", "quit", "退出"),
                ("w", "toggle_world", "世界浏览器"),
                ("l", "toggle_logs", "日志面板"),
                ("s", "show_status", "完整状态"),
                ("g", "show_goals", "目标"),
                ("h", "show_help", "帮助"),
            ]
            
            def __init__(self, interface: DeepTerminalInterface):
                super().__init__()
                self.interface = interface
            
            def compose(self) -> ComposeResult:
                yield Header(id="header")
                
                with Container(id="main"):
                    with Vertical(id="left-panel"):
                        yield Static("【行为监控】", classes="panel-title")
                        yield ScrollableContainer(Static(""))
                    
                    with Vertical(id="center-panel"):
                        yield Static("【深度对话】", classes="panel-title")
                        yield ScrollableContainer(Log(auto_scroll=True))
                    
                    with Vertical(id="right-panel"):
                        yield Static("【世界碎片】", classes="panel-title")
                        yield ScrollableContainer(Log(auto_scroll=True))
                
                with Container(id="bottom-panel"):
                    yield Static("【处理日志】", classes="panel-title")
                    yield ScrollableContainer(Log(auto_scroll=True))
                
                yield Input(placeholder="输入消息或命令 (以 / 开头)...", id="input")
            
            def on_mount(self) -> None:
                self.title = "Conway's Agent — 深度终端"
                self.update_panels()
            
            def update_panels(self) -> None:
                left = self.query_one("#left-panel ScrollableContainer", ScrollableContainer)
                left_mount = left.query_one(Static)
                left_mount.update(self.interface.format_behavior_monitor())
                
                center = self.query_one("#center-panel ScrollableContainer", ScrollableContainer)
                center_log = center.query_one(Log)
                for line in self.interface.format_deep_dialogue():
                    center_log.write_line(line)
                
                if self.interface.world_browser_visible:
                    right = self.query_one("#right-panel", Vertical)
                    right.add_class("visible")
                    right_scroll = self.query_one("#right-panel ScrollableContainer", ScrollableContainer)
                    right_log = right_scroll.query_one(Log)
                    right_log.clear()
                    fragments = self.interface.memory.read_all_fragments()
                    for f in fragments[-20:]:
                        right_log.write_line(f"• {f.title} [{f.fit_path}]")
                else:
                    right = self.query_one("#right-panel", Vertical)
                    right.remove_class("visible")
                
                bottom = self.query_one("#bottom-panel ScrollableContainer", ScrollableContainer)
                bottom_log = bottom.query_one(Log)
                bottom_log.clear()
                for line in self.interface.format_processing_log():
                    bottom_log.write_line(line)
            
            def on_input_submitted(self, event: Input.Submitted) -> None:
                self.interface.add_processing_log("perception", f"用户: {event.value[:50]}...")
                
                if event.value.startswith("/"):
                    response = self.interface.handle_command(event.value)
                    if response:
                        center = self.query_one("#center-panel ScrollableContainer", ScrollableContainer)
                        center_log = center.query_one(Log)
                        for line in response.split("\n"):
                            center_log.write_line(f"[dim]{line}[/dim]")
                else:
                    self.interface.add_dialogue("user", event.value)
                    center = self.query_one("#center-panel ScrollableContainer", ScrollableContainer)
                    center_log = center.query_one(Log)
                    center_log.write_line(f"[yellow]你:[/yellow] {event.value}")
                
                self.update_panels()
                self.query_one("#input", Input).value = ""
            
            def action_toggle_world(self) -> None:
                self.interface.world_browser_visible = not self.interface.world_browser_visible
                self.update_panels()
            
            def action_toggle_logs(self) -> None:
                self.interface.logs_panel_visible = not self.interface.logs_panel_visible
                self.update_panels()
            
            def action_show_status(self) -> None:
                status = self.interface.format_full_status()
                center = self.query_one("#center-panel ScrollableContainer", ScrollableContainer)
                center_log = center.query_one(Log)
                for line in status.split("\n"):
                    center_log.write_line(f"[cyan]{line}[/cyan]")
            
            def action_show_goals(self) -> None:
                goals = self.interface.format_goals()
                center = self.query_one("#center-panel ScrollableContainer", ScrollableContainer)
                center_log = center.query_one(Log)
                for line in goals.split("\n"):
                    center_log.write_line(f"[green]{line}[/green]")
            
            def action_show_help(self) -> None:
                help_text = """
【可用命令】
/why        — 解释为什么 Agent 给出了这个回应
/fragments   — 显示响应中使用的世界碎片
/think       — 显示 Agent 的思考过程
/status      — 显示完整 Agent 状态
/goals       — 显示目标和进度
/logs        — 打开/关闭处理日志面板
/world       — 打开/关闭世界浏览器
/quit        — 退出

【快捷键】
q — 退出
w — 切换世界浏览器
l — 切换日志面板
s — 显示完整状态
g — 显示目标
h — 显示帮助
""".strip()
                center = self.query_one("#center-panel ScrollableContainer", ScrollableContainer)
                center_log = center.query_one(Log)
                for line in help_text.split("\n"):
                    center_log.write_line(f"[dim]{line}[/dim]")
        
        app = DeepTerminalApp(self)
        await app.run_async()


class DeepTerminalCLI:
    """CLI wrapper for running the deep terminal interface."""
    
    def __init__(self, vault_path: Optional[Path] = None):
        if vault_path is None:
            from agent.core.vault import get_vault_path
            vault_path = get_vault_path()
        
        self.vault_path = vault_path
        
        try:
            self.state = AgentState.load()
        except FileNotFoundError:
            self.state = AgentState.from_seed("Initial seed")
            self.state.save()
    
    def run(self) -> None:
        """Run the deep terminal interface."""
        interface = DeepTerminalInterface(self.state, self.vault_path)
        
        if HAS_TEXTUAL:
            asyncio.run(interface.run_async())
        else:
            interface.run_rich()


def main() -> None:
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Conway's Agent — 深度终端界面",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python -m agent.ui.deep_terminal
  python -m agent.ui.deep_terminal --vault /path/to/vault
        """
    )
    
    parser.add_argument(
        "--vault",
        type=Path,
        default=None,
        help="Obsidian vault 路径 (默认: 从环境变量读取)"
    )
    
    args = parser.parse_args()
    
    cli = DeepTerminalCLI(vault_path=args.vault)
    cli.run()


if __name__ == "__main__":
    main()
