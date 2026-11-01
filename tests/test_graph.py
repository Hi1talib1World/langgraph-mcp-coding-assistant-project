"""
Integration tests for Self-Healing State Graph (src/ast_healing_coder/graph.py).
Verifies state machine compilation, node execution, retry loops, and HITL interrupts.
"""

import pytest
from ast_healing_coder.graph import build_self_healing_graph, self_healing_router, SelfHealingState

def test_graph_compilation():
    graph = build_self_healing_graph()
    assert graph is not None

def test_autonomous_self_healing_success():
    graph = build_self_healing_graph()
    initial_state = {
        "feature_request": "Fix discount calculation boundaries",
        "task_spec": None,
        "code_artifacts": {},
        "ast_diff": None,
        "test_result": None,
        "stack_trace_context": None,
        "attempt_count": 0,
        "max_retries": 3,
        "status": "INITIALIZED",
        "messages": []
    }
    config = {"configurable": {"thread_id": "test-session-success"}}
    final_state = graph.invoke(initial_state, config)
    
    assert final_state["status"] == "APPROVED"
    assert final_state["attempt_count"] == 2
    assert final_state["test_result"]["passed"] is True

def test_hitl_circuit_breaker_escalation():
    # If attempt_count >= max_retries and test failed, router must trigger hitl_interrupt
    state: SelfHealingState = {
        "feature_request": "Impossible bug",
        "task_spec": None,
        "code_artifacts": {},
        "ast_diff": None,
        "test_result": {"passed": False},
        "stack_trace_context": "Critical assertion failed",
        "attempt_count": 3,
        "max_retries": 3,
        "status": "EVALUATING",
        "messages": []
    }
    decision = self_healing_router(state)
    assert decision == "hitl_interrupt"

def test_self_heal_retry_decision():
    # If test failed and attempts < max_retries, router must return self_heal_retry
    state: SelfHealingState = {
        "feature_request": "Syntax error repair",
        "task_spec": None,
        "code_artifacts": {},
        "ast_diff": None,
        "test_result": {"passed": False},
        "stack_trace_context": "SyntaxError on line 12",
        "attempt_count": 1,
        "max_retries": 3,
        "status": "EVALUATING",
        "messages": []
    }
    decision = self_healing_router(state)
    assert decision == "self_heal_retry"
