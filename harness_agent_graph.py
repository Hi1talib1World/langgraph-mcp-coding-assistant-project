"""
Production Agentic Coding System (Harness Pattern + MCP + AST Guardrails)
Framework: LangGraph | Protocol: Model Context Protocol (MCP)
"""

import ast
import json
import logging
from typing import Dict, Any, List, Optional, Literal, TypedDict
from pydantic import BaseModel, Field

from langgraph.graph import StateGraph, START, END

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")
logger = logging.getLogger("HarnessCodingSystem")

# ============================================================================
# 1. STATE & SCHEMAS DECLARATION
# ============================================================================

class TestOutcome(BaseModel):
    passed: bool
    exit_code: int
    passed_count: int
    failed_count: int
    stdout: str
    stderr: str
    error_logs: List[str] = Field(default_factory=list)

class PatchRequirement(BaseModel):
    file_path: str
    issue_category: Literal["SYNTAX", "UNIT_TEST", "LINT", "SECURITY_VIOLATION", "LOGIC"]
    line_number: Optional[int] = None
    description: str
    suggested_fix: str

class ReviewCritique(BaseModel):
    approved: bool
    quality_score: float = Field(ge=0.0, le=1.0)
    summary: str
    required_patches: List[PatchRequirement] = Field(default_factory=list)

class SecurityVerdict(BaseModel):
    is_safe: bool
    violations: List[str] = Field(default_factory=list)
    blocked_calls: List[str] = Field(default_factory=list)

class TaskSpec(BaseModel):
    feature_name: str
    summary: str
    files_to_create_or_modify: List[str]
    architecture_notes: str
    acceptance_criteria: List[str]
    test_requirements: List[str]

class AgentState(TypedDict):
    feature_request: str
    task_spec: Optional[Dict[str, Any]]
    code_artifacts: Dict[str, str]  # file_path -> code content
    security_verdict: Optional[Dict[str, Any]]
    test_outcome: Optional[Dict[str, Any]]
    review_critique: Optional[Dict[str, Any]]
    attempt_count: int
    max_retries: int
    status: str
    messages: List[Dict[str, str]]

# ============================================================================
# 2. AST CODE SANITIZER GUARDRAIL ENGINE
# ============================================================================

class ASTSecurityVisitor(ast.NodeVisitor):
    FORBIDDEN_CALLS = {
        "os.system", "subprocess.Popen", "subprocess.call", "subprocess.run",
        "eval", "exec", "shutil.rmtree", "os.remove", "os.unlink", "socket.socket"
    }
    FORBIDDEN_MODULES = {"subprocess", "socket", "ctypes", "pty"}

    def __init__(self):
        self.violations = []
        self.blocked_calls = []

    def visit_Import(self, node):
        for alias in node.names:
            if alias.name in self.FORBIDDEN_MODULES:
                self.violations.append(f"Forbidden module import detected: '{alias.name}'")
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        if node.module in self.FORBIDDEN_MODULES:
            self.violations.append(f"Forbidden module import detected: '{node.module}'")
        self.generic_visit(node)

    def visit_Call(self, node):
        func_name = self._get_func_name(node.func)
        if func_name in self.FORBIDDEN_CALLS:
            self.violations.append(f"Forbidden security-sensitive call: '{func_name}'")
            self.blocked_calls.append(func_name)
        
        for arg in node.args:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                if "rm -rf" in arg.value or "mkfs" in arg.value:
                    self.violations.append(f"Destructive shell payload detected: '{arg.value}'")
        
        self.generic_visit(node)

    def _get_func_name(self, node):
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            val = self._get_func_name(node.value)
            return f"{val}.{node.attr}" if val else node.attr
        return ""

def sanitize_code_string(code_content: str) -> SecurityVerdict:
    try:
        tree = ast.parse(code_content)
        sanitizer = ASTSecurityVisitor()
        sanitizer.visit(tree)
        return SecurityVerdict(
            is_safe=len(sanitizer.violations) == 0,
            violations=sanitizer.violations,
            blocked_calls=sanitizer.blocked_calls
        )
    except SyntaxError as e:
        return SecurityVerdict(
            is_safe=False,
            violations=[f"Syntax error during AST parsing: {str(e)}"],
            blocked_calls=[]
        )

# ============================================================================
# 3. MCP TOOL CLIENT INTERFACE
# ============================================================================

class MCPToolSuite:
    """Interface for Model Context Protocol (MCP) Tools."""
    
    @staticmethod
    def execute_in_sandbox(command: str, timeout_ms: int = 30000, network_enabled: bool = False) -> Dict[str, Any]:
        logger.info(f"[MCP TOOL] execute_in_sandbox -> '{command}' (network={network_enabled})")
        return {
            "exit_code": 0,
            "passed": 5,
            "failed": 0,
            "stdout": "5 passed in 0.38s",
            "stderr": "",
            "error_logs": []
        }

    @staticmethod
    def git_commit_patch(patch_diff: str, commit_message: str) -> Dict[str, Any]:
        logger.info(f"[MCP TOOL] git_commit_patch -> '{commit_message}'")
        return {
            "success": True,
            "commit_hash": "a1b2c3d4e5f67890",
            "files_changed": 2
        }

    @staticmethod
    def search_codebase_ast(language: str, query_pattern: str) -> Dict[str, Any]:
        logger.info(f"[MCP TOOL] search_codebase_ast -> '{query_pattern}' in {language}")
        return {
            "matches": [
                {"file": "src/discount.py", "start_line": 1, "end_line": 5, "snippet": "def calculate_discount(...)"}
            ]
        }

# ============================================================================
# 4. AGENT & HARNESS GRAPH NODES
# ============================================================================

def architect_agent_node(state: AgentState) -> Dict[str, Any]:
    logger.info("=== [Architect Agent] Generating Task Specs & Acceptance Criteria ===")
    spec = TaskSpec(
        feature_name="Calculate Discounted Total",
        summary=f"Implement feature: {state['feature_request']}",
        files_to_create_or_modify=["src/discount.py", "tests/test_discount.py"],
        architecture_notes="Pure functional module with input boundary validation.",
        acceptance_criteria=[
            "Applies percentage discount correctly for total > 0",
            "Raises ValueError on negative total or discount > 100%",
            "Returns float rounded to 2 decimal places"
        ],
        test_requirements=["Test valid discount", "Test edge cases (0%, 100%)", "Test invalid inputs"]
    )
    return {"task_spec": spec.model_dump(), "status": "SPECIFIED"}


def coder_agent_node(state: AgentState) -> Dict[str, Any]:
    attempt = state["attempt_count"] + 1
    logger.info(f"=== [Coder Agent] Generating Code Implementation (Attempt #{attempt}) ===")
    
    critique = state.get("review_critique")
    security = state.get("security_verdict")
    
    # Check if fixing a security violation
    if security and not security.get("is_safe"):
        logger.info("[Coder Agent] Fixing AST security violation detected by Guardrail...")
        code_content = '''def calculate_discount(total: float, discount_percent: float) -> float:
    if total < 0 or discount_percent < 0 or discount_percent > 100:
        raise ValueError("Invalid total or discount percentage")
    return round(total * (1.0 - (discount_percent / 100.0)), 2)
'''
    elif critique and not critique.get("approved"):
        logger.info("[Coder Agent] Applying review patch critique...")
        code_content = '''def calculate_discount(total: float, discount_percent: float) -> float:
    if total < 0 or discount_percent < 0 or discount_percent > 100:
        raise ValueError("Invalid total or discount percentage")
    return round(total * (1.0 - (discount_percent / 100.0)), 2)
'''
    else:
        # Initial draft (simulates missing > 100% check to trigger self-correction loop)
        code_content = '''def calculate_discount(total: float, discount_percent: float) -> float:
    if total < 0 or discount_percent < 0:
        raise ValueError("Invalid input")
    return round(total * (1 - discount_percent/100), 2)
'''

    test_content = '''import pytest
from src.discount import calculate_discount

def test_calculate_discount_valid():
    assert calculate_discount(100.0, 15.0) == 85.0

def test_calculate_discount_invalid():
    with pytest.raises(ValueError):
        calculate_discount(-10.0, 10.0)
'''

    artifacts = {
        "src/discount.py": code_content,
        "tests/test_discount.py": test_content
    }
    return {
        "code_artifacts": artifacts,
        "attempt_count": attempt,
        "status": "CODED"
    }


def guardrail_node(state: AgentState) -> Dict[str, Any]:
    """
    Harness Guardrail Node:
    Runs AST static analysis sanitization on all code artifacts BEFORE sandbox execution.
    """
    logger.info("=== [Harness Guardrail Node] Running AST Code Sanitization Check ===")
    all_violations = []
    all_blocked = []
    
    for file_path, code in state["code_artifacts"].items():
        verdict = sanitize_code_string(code)
        if not verdict.is_safe:
            all_violations.extend([f"{file_path}: {v}" for v in verdict.violations])
            all_blocked.extend(verdict.blocked_calls)
            
    is_safe = len(all_violations) == 0
    if is_safe:
        logger.info("[Guardrail Node] ✅ Code passed AST security audit.")
    else:
        logger.warning(f"[Guardrail Node] ❌ AST Security Violation Detected: {all_violations}")
        
    return {
        "security_verdict": {
            "is_safe": is_safe,
            "violations": all_violations,
            "blocked_calls": all_blocked
        },
        "status": "GUARDRAIL_PASSED" if is_safe else "GUARDRAIL_FAILED"
    }


def sandbox_execution_node(state: AgentState) -> Dict[str, Any]:
    """
    Executes unit test suite via MCP execute_in_sandbox tool.
    """
    logger.info("=== [Sandbox Execution Node] Invoking MCP execute_in_sandbox ===")
    res = MCPToolSuite.execute_in_sandbox(command="pytest tests/", timeout_ms=30000, network_enabled=False)
    
    outcome = TestOutcome(
        passed=(res["exit_code"] == 0),
        exit_code=res["exit_code"],
        passed_count=res["passed"],
        failed_count=res["failed"],
        stdout=res["stdout"],
        stderr=res["stderr"],
        error_logs=res.get("error_logs", [])
    )
    return {"test_outcome": outcome.model_dump(), "status": "TESTED"}


def reviewer_agent_node(state: AgentState) -> Dict[str, Any]:
    """
    Reviewer Agent Node:
    Evaluates test results, code artifacts, and task specifications to output a structured JSON critique.
    """
    logger.info("=== [Reviewer Agent] Evaluating Implementation & Generating JSON Critique ===")
    attempt = state["attempt_count"]
    
    if attempt == 1:
        critique = ReviewCritique(
            approved=False,
            quality_score=0.78,
            summary="Unit tests passed, but validation check for discount > 100% is omitted.",
            required_patches=[
                PatchRequirement(
                    file_path="src/discount.py",
                    issue_category="LOGIC",
                    line_number=2,
                    description="discount_percent values over 100% are allowed, producing negative totals.",
                    suggested_fix="Add `or discount_percent > 100` condition to raise ValueError."
                )
            ]
        )
    else:
        critique = ReviewCritique(
            approved=True,
            quality_score=0.99,
            summary="All tests passed, edge cases validated, AST audit clean.",
            required_patches=[]
        )
        
    return {
        "review_critique": critique.model_dump(),
        "status": "APPROVED" if critique.approved else "REJECTED"
    }


def git_commit_node(state: AgentState) -> Dict[str, Any]:
    """Commits validated code patch via MCP git_commit_patch tool."""
    logger.info("=== [Git Commit Node] Executing MCP git_commit_patch ===")
    res = MCPToolSuite.git_commit_patch(
        patch_diff="--- src/discount.py\n+++ src/discount.py\n@@ -2,2 +2,2 @@\n- if total < 0 or discount_percent < 0:\n+ if total < 0 or discount_percent < 0 or discount_percent > 100:",
        commit_message=f"feat: {state['task_spec']['feature_name']}"
    )
    return {"status": "COMMITTED"}


def fallback_human_node(state: AgentState) -> Dict[str, Any]:
    """Circuit Breaker: Escalates state to human developer when max retries are exceeded."""
    logger.warning(f"=== [Fallback Human Node] Max retry limit ({state['max_retries']}) hit. Escalating to human. ===")
    return {"status": "FALLBACK_HUMAN"}

# ============================================================================
# 5. CONDITIONAL ROUTING DECISION ENGINE
# ============================================================================

def guardrail_router(state: AgentState) -> Literal["safe", "unsafe"]:
    sec = state.get("security_verdict", {})
    if sec.get("is_safe", False):
        return "safe"
    else:
        return "unsafe"

def self_correction_router(state: AgentState) -> Literal["approved", "retry_coder", "fallback_human"]:
    critique = state.get("review_critique", {})
    is_approved = critique.get("approved", False)
    attempts = state.get("attempt_count", 0)
    max_retries = state.get("max_retries", 3)
    
    if is_approved:
        logger.info("--> Self-Correction Router: APPROVED. Proceeding to git commit.")
        return "approved"
    elif attempts < max_retries:
        logger.info(f"--> Self-Correction Router: REJECTED. Looping back to Coder (Attempt {attempts}/{max_retries}).")
        return "retry_coder"
    else:
        logger.warning(f"--> Self-Correction Router: MAX RETRIES EXCEEDED ({attempts}/{max_retries}). Escalating to Human.")
        return "fallback_human"

# ============================================================================
# 6. GRAPH ASSEMBLY & COMPILATION
# ============================================================================

def build_harness_coding_graph() -> StateGraph:
    workflow = StateGraph(AgentState)
    
    workflow.add_node("architect_agent", architect_agent_node)
    workflow.add_node("coder_agent", coder_agent_node)
    workflow.add_node("guardrail_node", guardrail_node)
    workflow.add_node("sandbox_execution_node", sandbox_execution_node)
    workflow.add_node("reviewer_agent", reviewer_agent_node)
    workflow.add_node("git_commit_node", git_commit_node)
    workflow.add_node("fallback_human_node", fallback_human_node)
    
    # Linear Edges
    workflow.add_edge(START, "architect_agent")
    workflow.add_edge("architect_agent", "coder_agent")
    workflow.add_edge("coder_agent", "guardrail_node")
    
    # Guardrail Router Edge
    workflow.add_conditional_edges(
        "guardrail_node",
        guardrail_router,
        {
            "safe": "sandbox_execution_node",
            "unsafe": "coder_agent"
        }
    )
    
    workflow.add_edge("sandbox_execution_node", "reviewer_agent")
    
    # Self-Correction Feedback Loop Router Edge
    workflow.add_conditional_edges(
        "reviewer_agent",
        self_correction_router,
        {
            "approved": "git_commit_node",
            "retry_coder": "coder_agent",
            "fallback_human": "fallback_human_node"
        }
    )
    
    workflow.add_edge("git_commit_node", END)
    workflow.add_edge("fallback_human_node", END)
    
    return workflow.compile()

# ============================================================================
# 7. EXECUTION RUNNER
# ============================================================================

if __name__ == "__main__":
    app = build_harness_coding_graph()
    
    initial_state: AgentState = {
        "feature_request": "Create a function to calculate discounted totals with boundary checks.",
        "task_spec": None,
        "code_artifacts": {},
        "security_verdict": None,
        "test_outcome": None,
        "review_critique": None,
        "attempt_count": 0,
        "max_retries": 3,
        "status": "INITIALIZED",
        "messages": []
    }
    
    logger.info("Starting Harness Agent Coding Graph Execution...\n")
    final_state = app.invoke(initial_state)
    
    print("\n================ FINAL HARNESS GRAPH RESULT ================")
    print(f"Final Status:     {final_state['status']}")
    print(f"Total Attempts:   {final_state['attempt_count']}")
    print(f"Code Artifacts:   {list(final_state['code_artifacts'].keys())}")
    print(f"Review Summary:   {final_state['review_critique'].get('summary')}")
    print("============================================================")
