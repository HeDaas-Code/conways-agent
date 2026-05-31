#!/usr/bin/env python3
"""
Agent CLI Entry Point

Run the agent with: python -m agent.main
"""

from __future__ import annotations

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
)
from agent.core.vault import ensure_vault_dirs


def signal_handler(signum: int, frame) -> None:
    """Handle shutdown signals gracefully."""
    print("\n\n收到退出信号，正在关闭...")
    log_shutdown("Agent entering dormancy — interrupted by signal")
    sys.exit(0)


def main() -> None:
    """
    Main entry point for the agent.
    
    1. Initialize the agent (startup)
    2. Print startup message in agent's voice
    3. Run main loop until interrupted
    4. Log shutdown on exit
    """
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
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
