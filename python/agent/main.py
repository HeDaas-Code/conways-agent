#!/usr/bin/env python3
"""
Agent CLI Entry Point

Run the agent with: python -m agent.main

Commands:
    python -m agent.main                    # Interactive mode (default)
    python -m agent.main --perceive <file> [file2.md ...]  # Perceive specific files
    python -m agent.main --perceive-all    # Perceive all user files in vault
"""

from __future__ import annotations

import argparse
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv()

from agent import (
    initialize_agent,
    startup_message,
    log_shutdown,
    log_cycle,
    log_event,
    PerceptionSystem,
    ProcessingPipeline,
)
from agent.core.vault import ensure_vault_dirs
from agent.core.cycle import SleepWakeCycle
from agent.core.state import AgentState
from agent.core.dialogue import DialogueSession


def run_dialogue_mode() -> None:
    """Run the Agent in dialogue mode."""
    print("正在启动对话模式...")
    ensure_vault_dirs()

    state = initialize_agent()
    print(startup_message(state))

    from agent.core.llm import LLMClient
    from agent.core.pipeline import ProcessingPipeline

    llm = LLMClient()
    pipeline = ProcessingPipeline(llm_client=llm)

    session = DialogueSession(llm_client=llm, state=state, pipeline=pipeline)

    print()
    print(session.get_welcome_message())
    print()

    run_interactive_loop(session)


def run_interactive_loop(session: DialogueSession) -> None:
    """The interactive input loop for dialogue."""
    while True:
        try:
            user_input = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n")
            break

        if not user_input:
            continue

        if user_input.lower() in ("quit", "exit", "q"):
            print("\n[图书馆再次陷入寂静...]")
            print("再见。\n")
            log_shutdown("Dialogue session ended by user")
            break

        if user_input.lower() == "clear":
            session.clear_history()
            print("[对话历史已清空]")
            continue

        if user_input.lower() == "status":
            print(f"\n[状态]")
            print(f"  对话轮次: {len(session.history) // 2}")
            print(f"  Agent: {session.state.personality.get('name', '图书馆居者')}")
            print(f"  睡眠状态: {session.state.sleep_state}")
            print(f"  总循环: {session.state.total_cycles}")
            continue

        print()
        response = session.user_speak(user_input)
        print(f"[Agent]: {response}")
        print()


def signal_handler(signum: int, frame) -> None:
    """Handle shutdown signals gracefully."""
    print("\n\n收到退出信号，正在关闭...")
    log_shutdown("Agent entering dormancy — interrupted by signal")
    sys.exit(0)


def run_perception_mode(file_paths: list[str]) -> None:
    """
    Run in perception mode - perceive specified files.
    
    Args:
        file_paths: List of file paths to perceive
    """
    print("正在启动感知模式...")
    ensure_vault_dirs()
    
    state = initialize_agent()
    print(startup_message(state))
    
    perception_system = PerceptionSystem()
    pipeline = ProcessingPipeline()
    
    print(f"\n开始感知 {len(file_paths)} 个文件...\n")
    
    for file_path in file_paths:
        print(f"感知文件: {file_path}")
        try:
            perception = perception_system.perceive_file(file_path, trigger="manual")
            result = pipeline.process(perception)
            
            if result.success:
                print(f"  ✓ 处理成功 ({result.fit_result.judgment} fit, {result.processing_time_ms:.1f}ms)")
                print(f"    路径: {result.fragment.fit_path}")
                print(f"    标题: {result.fragment.title}")
            else:
                print(f"  ✗ 处理失败: {', '.join(result.errors)}")
        except FileNotFoundError as e:
            print(f"  ✗ 文件未找到: {e}")
        except ValueError as e:
            print(f"  ✗ 错误: {e}")
        print()
    
    print("感知完成。")
    log_event("perception_mode_complete", f"Perceived {len(file_paths)} files")


def run_perceive_all_mode() -> None:
    """Run in perceive-all mode - perceive all user files."""
    print("正在启动全量感知模式...")
    ensure_vault_dirs()
    
    state = initialize_agent()
    print(startup_message(state))
    
    perception_system = PerceptionSystem()
    pipeline = ProcessingPipeline()
    
    print("\n开始感知 vault 中的所有用户文件...\n")
    
    perceptions = perception_system.perceive_all_user_files()
    
    if not perceptions:
        print("未找到任何用户文件。")
        return
    
    print(f"找到 {len(perceptions)} 个文件，开始处理...\n")
    
    success_count = 0
    for perception in perceptions:
        print(f"处理: {perception.file_path}")
        try:
            result = pipeline.process(perception)
            if result.success:
                success_count += 1
                print(f"  ✓ {result.fit_result.judgment} fit ({result.processing_time_ms:.1f}ms)")
            else:
                print(f"  ✗ 失败: {', '.join(result.errors)}")
        except Exception as e:
            print(f"  ✗ 错误: {e}")
        print()
    
    print(f"全量感知完成: {success_count}/{len(perceptions)} 成功")
    log_event("perceive_all_complete", f"Perceived {success_count}/{len(perceptions)} files")


def run_interactive_mode() -> None:
    """Run in interactive mode - agent main loop."""
    print("正在启动 Agent...")
    ensure_vault_dirs()
    
    state = initialize_agent()
    print(startup_message(state))
    
    print("Agent 运行中，按 Ctrl+C 退出...\n")
    
    cycle_count = 0
    while True:
        time.sleep(1)
        cycle_count += 1
        
        if cycle_count % 10 == 0:
            log_cycle(cycle_count)


def run_daemon_mode() -> None:
    """
    Run in daemon mode - sleep/wake cycle loop with file watching.
    
    This mode:
    1. Wakes up the agent
    2. Processes file events from the watcher
    3. Goes to sleep
    4. Repeats
    """
    from agent.core.watcher import VaultWatcher
    
    print("正在启动 Daemon 模式 — 睡眠/唤醒循环 + 文件监听...")
    ensure_vault_dirs()
    
    state = initialize_agent()
    print(startup_message(state))
    
    cycle = SleepWakeCycle(state)
    watcher = VaultWatcher()
    
    wake_duration = state.wake_duration_seconds
    sleep_duration = state.sleep_duration_seconds
    
    print(f"\n循环配置:")
    print(f"  唤醒时长: {wake_duration} 秒 ({wake_duration // 60} 分钟)")
    print(f"  休眠时长: {sleep_duration} 秒 ({sleep_duration // 60} 分钟)")
    print(f"  监听目录: {watcher.vault_path}")
    print()
    print("Daemon 运行中，按 Ctrl+C 退出...\n")
    
    perception_system = PerceptionSystem()
    pipeline = ProcessingPipeline()
    
    try:
        while True:
            if not cycle.is_awake:
                if cycle.is_time_to_wake():
                    print("\n[唤醒] Agent 正在苏醒...")
                    cycle.wake()
                    perception_system.set_awareness_mode(True)
                    print("[唤醒] 进入主动处理模式")
                else:
                    events = watcher.watch_once()
                    for event in events:
                        perception_system.process_passive_event({
                            "type": event.type,
                            "path": event.path,
                            "timestamp": event.timestamp.isoformat(),
                        })
                    time.sleep(watcher._poll_interval)
                    cycle.tick()
                continue
            
            print(f"[活跃] Agent 正在处理 (剩余 {cycle.get_cycle_status()['time_remaining_seconds']:.0f} 秒)")
            
            events = watcher.watch_once()
            for event in events:
                try:
                    perception = perception_system.perceive_file(event.path, trigger="event")
                    result = pipeline.process(perception)
                    if result.success:
                        log_event(
                            "event_processed",
                            f"Processed file event: {event.type}",
                            {"path": event.path, "type": event.type, "fit": result.fit_result.judgment}
                        )
                except (FileNotFoundError, ValueError) as e:
                    log_event(
                        "event_processing_error",
                        f"Failed to process file event: {e}",
                        {"path": event.path, "error": str(e)}
                    )
            
            time.sleep(min(10, cycle.get_cycle_status()['time_remaining_seconds']))
            
            if cycle.is_time_to_sleep():
                print("\n[休眠] Agent 正在进入休眠状态...")
                cycle.sleep()
                perception_system.set_awareness_mode(False)
                print("[休眠] 进入被动感知模式")
                log_event(
                    "daemon_sleep",
                    f"Daemon sleeping for {sleep_duration} seconds",
                    {"sleep_duration": sleep_duration}
                )
            else:
                cycle.tick()
                
    except KeyboardInterrupt:
        watcher.stop()
        print("\n\n正在关闭 Daemon...")
        log_shutdown("Daemon interrupted by user")
        print("Daemon 已停止。")
        sys.exit(0)


def main() -> None:
    """
    Main entry point for the agent.
    
    Supports multiple command modes:
    1. Interactive mode (default): Agent runs in continuous loop
    2. Perception mode: Perceive specific files
    3. Perceive-all mode: Perceive all user files in vault
    4. Daemon mode: Sleep/wake cycle loop
    """
    parser = argparse.ArgumentParser(
        description="Conway's Agent - Obsidian Cognitive Agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m agent.main                                    # Interactive mode
  python -m agent.main --perceive notes/ideas.md          # Perceive single file
  python -m agent.main --perceive notes/1.md notes/2.md  # Perceive multiple files
  python -m agent.main --perceive-all                     # Perceive all vault files
  python -m agent.main --daemon                           # Daemon mode with sleep/wake cycle
        """
    )
    
    parser.add_argument(
        "--perceive",
        nargs="+",
        metavar="FILE",
        help="Perceive specific files (relative to vault root)"
    )
    
    parser.add_argument(
        "--perceive-all",
        action="store_true",
        help="Perceive all user files in the vault (excludes agent/ directory)"
    )
    
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="Run in daemon mode with sleep/wake cycle"
    )

    parser.add_argument(
        "--dialogue",
        action="store_true",
        help="Run in dialogue mode (default interactive mode)"
    )

    args = parser.parse_args()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        if args.dialogue:
            run_dialogue_mode()
        elif args.daemon:
            run_daemon_mode()
        elif args.perceive_all:
            run_perceive_all_mode()
        elif args.perceive:
            run_perception_mode(args.perceive)
        else:
            run_interactive_mode()
            
    except KeyboardInterrupt:
        print("\n\n正在关闭 Agent...")
        log_shutdown("Agent entering dormancy — user interrupt")
        print("Agent 已进入休眠。")
        sys.exit(0)
        
    except FileNotFoundError as e:
        print(f"错误: {e}")
        print("请确保 agent/seed.md 文件存在。")
        sys.exit(1)
        
    except ValueError as e:
        print(f"配置错误: {e}")
        print("请检查 OBSIDIAN_VAULT_PATH 环境变量是否设置。")
        sys.exit(1)
        
    except Exception as e:
        print(f"启动失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
