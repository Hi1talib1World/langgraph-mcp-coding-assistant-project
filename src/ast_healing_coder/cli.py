"""
CLI Entry Point for ast-coder command
"""

import sys
import argparse
import logging
from rich.console import Console

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from . import __version__
from .graph import build_self_healing_graph
from .tui import RichTUIRunner

console = Console(force_terminal=True)

def main():
    parser = argparse.ArgumentParser(
        prog="ast-coder",
        description="AST-Healing-Coder: Self-healing autonomous coding agent powered by LangGraph, MCP, & AST Patching."
    )
    parser.add_argument(
        "--request", "-r", 
        type=str, 
        default="Implement discount calculator with boundary input validation.",
        help="Natural language feature request to execute."
    )
    parser.add_argument(
        "--provider", "-p",
        type=str,
        default="auto",
        choices=["auto", "ollama", "vllm", "gemini", "openai", "anthropic"],
        help="LLM provider: 'ollama', 'vllm', 'gemini', 'openai', or 'auto'."
    )
    parser.add_argument(
        "--model", "-m",
        type=str,
        default="codellama:7b",
        help="Target model name (e.g., 'codellama:7b', 'Qwen/Qwen2.5-Coder-7B-Instruct', 'gemini-2.5-flash')."
    )
    parser.add_argument(
        "--api-base",
        type=str,
        default=None,
        help="Custom base URL for local engines (e.g. 'http://localhost:11434' or 'http://localhost:8000/v1')."
    )
    parser.add_argument(
        "--max-retries", 
        type=int, 
        default=3, 
        help="Maximum self-correction retries before HITL circuit breaker escalation."
    )
    parser.add_argument(
        "--demo", 
        action="store_true", 
        help="Run interactive Rich Terminal UI demo mode."
    )
    parser.add_argument(
        "--version", "-v", 
        action="version", 
        version=f"%(prog)s {__version__}"
    )

    args = parser.parse_args()

    app = build_self_healing_graph()

    initial_state = {
        "feature_request": args.request,
        "task_spec": None,
        "code_artifacts": {},
        "ast_diff": None,
        "static_analysis": None,
        "test_result": None,
        "stack_trace_context": None,
        "attempt_count": 0,
        "max_retries": args.max_retries,
        "status": "INITIALIZED",
        "messages": []
    }

    if args.demo or sys.stdout.isatty():
        tui = RichTUIRunner(provider=args.provider, model=args.model)
        tui.render_demo(app, initial_state)
    else:
        config = {"configurable": {"thread_id": "cli-session-001"}}
        final_state = app.invoke(initial_state, config)
        console.print(f"[bold green]Execution Finished. Status: {final_state['status']}[/bold green]")

if __name__ == "__main__":
    main()
