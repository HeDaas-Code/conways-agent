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


def main() -> None:
    """
    Main entry point for the agent.
    
    Supports multiple command modes:
    1. Interactive mode (default): Agent runs in continuous loop
    2. Perception mode: Perceive specific files
    3. Perceive-all mode: Perceive all user files in vault
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
    
    args = parser.parse_args()
    
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        if args.perceive_all:
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
