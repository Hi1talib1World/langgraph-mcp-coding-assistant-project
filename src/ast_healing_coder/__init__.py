"""
AST-Healing-Coder: Autonomous Self-Healing Coding Agent Powered by LangGraph, MCP, & AST Patching.
"""

__version__ = "0.1.0"
__author__ = "Antigravity Open Source Team"
__license__ = "MIT"

from .ast_patcher import patch_function_in_code, patch_function_in_file
from .sandbox import SandboxedExecutor
from .graph import build_self_healing_graph, SelfHealingState
from .llm_factory import get_llm_provider

__all__ = [
    "__version__",
    "patch_function_in_code",
    "patch_function_in_file",
    "SandboxedExecutor",
    "build_self_healing_graph",
    "SelfHealingState",
    "get_llm_provider",
]
