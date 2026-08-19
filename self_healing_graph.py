"""
Self-Healing Autonomous Coding Agent State Machine
Framework: LangGraph | Protocol: MCP | Engine: AST Patcher + Seccomp Sandbox
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional, Literal, TypedDict
from pydantic import BaseModel, Field

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from ast_patcher import patch_function_in_code, extract_node_source
from security.docker_sandbox import SandboxedExecutor

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")
logger = logging.getLogger("SelfHealingCodingAgent")

# ============================================================================
# 1. STATE CHANNEL SCHEMAS
# ============================================================================

class TaskSpec(BaseModel):
    feature_name: str
    target_file: str
    target_function: str
    summary: str
    acceptance_criteria: List[str]

class StaticAnalysisResult(BaseModel):
    passed: bool
    ruff_violations: List[str] = Field(default_factory=list)
    mypy_violations: List[str] = Field(default_factory=list)

class TestExecutionResult(BaseModel):
    passed: bool
    exit_code: int
    stdout: str
    stderr: str
    stack_trace: str
    duration_ms: float

class SelfHealingState(TypedDict):
    feature_request: str
    task_spec: Optional[Dict[str, Any]]
    code_artifacts: Dict[str, str]  # file_path -> code
    ast_diff: Optional[str]
    static_analysis: Optional[Dict[str, Any]]
    test_result: Optional[Dict[str, Any]]
    stack_trace_context: Optional[str]
    attempt_count: int
    max_retries: int
    status: Literal[
        "INITIALIZED", 
        "PLANNING", 
        "CODING", 
        "STATIC_ANALYSIS", 
        "SANDBOX_TESTING", 
        "EVALUATING", 
        "APPROVED", 
        "HITL_INTERRUPT"
    ]
    messages: List[Dict[str, str]]

# ============================================================================
# 2. STATE GRAPH NODE IMPLEMENTATIONS
# ============================================================================

def plan_node(state: SelfHealingState) -> Dict[str, Any]:
    """
    Plan Node:
    Generates structured specification and identifies target AST function node.
    """
    logger.info("=== [Node 1: Plan] Generating Feature Specs & AST Targets ===")
    
    spec = TaskSpec(
        feature_name="Calculate Discounted Total",
        target_file="src/discount.py",
        target_function="calculate_discount",
        summary=f"Implement feature for request: {state['feature_request']}",
        acceptance_criteria=[
            "Applies discount rate correctly for total > 0",
            "Raises ValueError if total < 0 or discount < 0 or discount > 100",
            "Returns float rounded to 2 decimal places"
        ]
    )
    return {"task_spec": spec.model_dump(), "status": "PLANNING"}


def gencode_node(state: SelfHealingState) -> Dict[str, Any]:
    """
    GenCode Node:
    Uses AST-guided patching (ast_patcher) to modify only the target function node,
    injecting previous stack traces and AST diffs if in a self-correction retry loop.
    """
    attempt = state["attempt_count"] + 1
    logger.info(f"=== [Node 2: GenCode] Applying AST Patch (Attempt #{attempt}) ===")
    
    task_spec = state["task_spec"]
    target_file = task_spec["target_file"]
    target_func = task_spec["target_function"]
    stack_context = state.get("stack_trace_context")
    
    # Original module base code
    existing_module_code = state["code_artifacts"].get(target_file, '''import math

def calculate_discount(total: float, discount_percent: float) -> float:
    # Initial placeholder
    pass

def calculate_tax(amount: float, tax_rate: float) -> float:
    """Unaffected helper function in module."""
    return round(amount * tax_rate, 2)
''')

    # Self-Correction logic: Check if responding to stack trace failure
    if stack_context and attempt > 1:
        logger.info("[GenCode] Injecting stack trace context into self-healing AST patch...")
        # Self-healed AST replacement function
        replacement_func_code = '''def calculate_discount(total: float, discount_percent: float) -> float:
    if total < 0 or discount_percent < 0 or discount_percent > 100:
        raise ValueError("Invalid total or discount percentage")
    discounted = total * (1.0 - (discount_percent / 100.0))
    return round(discounted, 2)
'''
    else:
        # Initial draft with minor bug (missing > 100% check to trigger self-healing loop)
        replacement_func_code = '''def calculate_discount(total: float, discount_percent: float) -> float:
    if total < 0 or discount_percent < 0:
        raise ValueError("Invalid input")
    return round(total * (1 - discount_percent/100), 2)
'''

    test_file_code = '''import pytest
from src.discount import calculate_discount

def test_valid_discount():
    assert calculate_discount(100.0, 20.0) == 80.0

def test_zero_discount():
    assert calculate_discount(50.0, 0.0) == 50.0

def test_invalid_negative():
    with pytest.raises(ValueError):
        calculate_discount(-10.0, 10.0)

def test_invalid_over_hundred():
    with pytest.raises(ValueError):
        calculate_discount(100.0, 150.0)
'''

    # Apply surgical AST patch to module without touching helper functions
    patched_code, ast_diff, success = patch_function_in_code(
        existing_module_code, 
        target_func, 
        replacement_func_code
    )
    
    artifacts = dict(state["code_artifacts"])
    artifacts[target_file] = patched_code
    artifacts["tests/test_discount.py"] = test_file_code

    logger.info(f"[GenCode] AST Patch Generated for '{target_func}'. Lines Diff:\n{ast_diff.strip()}")

    return {
        "code_artifacts": artifacts,
        "ast_diff": ast_diff,
        "attempt_count": attempt,
        "status": "CODING"
    }


def static_analysis_node(state: SelfHealingState) -> Dict[str, Any]:
    """
    Node 3: Static Analysis (Ruff & Mypy)
    Performs static linting and type checking in sandbox.
    """
    logger.info("=== [Node 3: Static Analysis] Running Ruff Linter & Mypy Type Checker ===")
    
    # In production, invokes sandbox executor; simulated here with clean status
    result = StaticAnalysisResult(
        passed=True,
        ruff_violations=[],
        mypy_violations=[]
    )
    return {"static_analysis": result.model_dump(), "status": "STATIC_ANALYSIS"}


def sandbox_execute_node(state: SelfHealingState) -> Dict[str, Any]:
    """
    Node 4: Sandbox Execute (Docker / Pytest with Seccomp Profile)
    Runs Pytest inside containerized sandbox environment with network isolation.
    """
    attempt = state["attempt_count"]
    logger.info(f"=== [Node 4: Sandbox Execute] Running Pytest in Container Sandbox (Attempt #{attempt}) ===")
    
    # Simulate test outcomes based on attempt
    if attempt == 1:
        # Initial attempt fails test_invalid_over_hundred
        stdout = "================ FAILURES ================\n________________ test_invalid_over_hundred ________________\n> calculate_discount(100.0, 150.0)\nE AssertionError: DID NOT RAISE <class 'ValueError'>"
        stderr = "AssertionError: DID NOT RAISE <class 'ValueError'>"
        res = TestExecutionResult(
            passed=False,
            exit_code=1,
            stdout=stdout,
            stderr=stderr,
            stack_trace="Traceback (most recent call last):\n  File 'tests/test_discount.py', line 16, in test_invalid_over_hundred\n    calculate_discount(100.0, 150.0)\nAssertionError: DID NOT RAISE <class 'ValueError'>",
            duration_ms=420.0
        )
    else:
        # Self-healed attempt passes all tests
        res = TestExecutionResult(
            passed=True,
            exit_code=0,
            stdout="4 passed in 0.35s",
            stderr="",
            stack_trace="",
            duration_ms=350.0
        )

    return {"test_result": res.model_dump(), "status": "SANDBOX_TESTING"}


def evaluate_result_node(state: SelfHealingState) -> Dict[str, Any]:
    """
    Node 5: Evaluate Result Node
    Parses test results. If failed, extracts stack traces and triggers self-correction loop.
    """
    logger.info("=== [Node 5: Evaluate Result] Analyzing Execution Outcome ===")
    test_res = state["test_result"]
    
    if test_res["passed"]:
        logger.info("[Evaluate Result] ✅ All tests passed successfully!")
        return {"status": "APPROVED", "stack_trace_context": None}
    else:
        logger.warning(f"[Evaluate Result] ❌ Test execution failed. Extracting stack trace...")
        stack_context = f"FAILURE STACK TRACE:\n{test_res['stack_trace']}\n\nSTDOUT:\n{test_res['stdout']}"
        return {"status": "EVALUATING", "stack_trace_context": stack_context}


def hitl_approval_node(state: SelfHealingState) -> Dict[str, Any]:
    """
    Circuit Breaker Node: Human-in-the-Loop Interrupt
    Triggered when retries exceed max_retries (3). Graph pauses execution via checkpoint interrupt.
    """
    logger.warning(f"=== [HITL Circuit Breaker Node] Retries exceeded {state['max_retries']}. Escalating for human review. ===")
    return {"status": "HITL_INTERRUPT"}

# ============================================================================
# 3. CONDITIONAL EDGE ROUTER
# ============================================================================

def self_healing_router(state: SelfHealingState) -> Literal["approved", "self_heal_retry", "hitl_interrupt"]:
    test_res = state.get("test_result", {})
    passed = test_res.get("passed", False)
    attempt = state.get("attempt_count", 0)
    max_retries = state.get("max_retries", 3)
    
    if passed:
        return "approved"
    elif attempt < max_retries:
        logger.info(f"--> [Self-Healing Router] Retrying AST patch with stack trace context ({attempt}/{max_retries}).")
        return "self_heal_retry"
    else:
        logger.warning(f"--> [Self-Healing Router] Circuit Breaker Tripped! Retries hit limit ({attempt}/{max_retries}). Routing to HITL Interrupt.")
        return "hitl_interrupt"

# ============================================================================
# 4. STATE GRAPH COMPILATION WITH HITL INTERRUPTS
# ============================================================================

def build_self_healing_graph():
    memory = MemorySaver()
    workflow = StateGraph(SelfHealingState)
    
    workflow.add_node("plan_node", plan_node)
    workflow.add_node("gencode_node", gencode_node)
    workflow.add_node("static_analysis_node", static_analysis_node)
    workflow.add_node("sandbox_execute_node", sandbox_execute_node)
    workflow.add_node("evaluate_result_node", evaluate_result_node)
    workflow.add_node("hitl_approval_node", hitl_approval_node)
    
    # Linear Edges
    workflow.add_edge(START, "plan_node")
    workflow.add_edge("plan_node", "gencode_node")
    workflow.add_edge("gencode_node", "static_analysis_node")
    workflow.add_edge("static_analysis_node", "sandbox_execute_node")
    workflow.add_edge("sandbox_execute_node", "evaluate_result_node")
    
    # Conditional Self-Healing Edge
    workflow.add_conditional_edges(
        "evaluate_result_node",
        self_healing_router,
        {
            "approved": END,
            "self_heal_retry": "gencode_node",
            "hitl_interrupt": "hitl_approval_node"
        }
    )
    
    workflow.add_edge("hitl_approval_node", END)
    
    # Compile with MemorySaver Checkpointer and Interrupt Before HITL Node
    return workflow.compile(
        checkpointer=memory,
        interrupt_before=["hitl_approval_node"]
    )

# ============================================================================
# 5. EXECUTION RUNNER
# ============================================================================

if __name__ == "__main__":
    app = build_self_healing_graph()
    
    config = {"configurable": {"thread_id": "session-self-healing-001"}}
    
    initial_state: SelfHealingState = {
        "feature_request": "Implement discount calculator with boundary input validation.",
        "task_spec": None,
        "code_artifacts": {},
        "ast_diff": None,
        "static_analysis": None,
        "test_result": None,
        "stack_trace_context": None,
        "attempt_count": 0,
        "max_retries": 3,
        "status": "INITIALIZED",
        "messages": []
    }
    
    logger.info("Starting Self-Healing Autonomous Coding Graph...\n")
    final_state = app.invoke(initial_state, config)
    
    print("\n================ FINAL SELF-HEALING GRAPH RESULT ================")
    print(f"Final Status:     {final_state['status']}")
    print(f"Total Attempts:   {final_state['attempt_count']}")
    print(f"Patched Artifacts:{list(final_state['code_artifacts'].keys())}")
    print(f"AST Diff Summary:\n{final_state.get('ast_diff', '').strip()}")
    print("=================================================================")
