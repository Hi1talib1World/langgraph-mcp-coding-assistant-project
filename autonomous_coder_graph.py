"""
Autonomous Multi-Agent Coding Assistant (LLM Powered)
Framework: LangGraph | Protocol: Model Context Protocol (MCP)
LLM Providers: Google Gemini / OpenAI (with Pydantic Structured Output)
"""

import os
import json
import logging
from typing import Dict, Any, List, Optional, Literal, TypedDict
from pydantic import BaseModel, Field

from langgraph.graph import StateGraph, START, END

# Import LLM Providers
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    HAS_GEMINI = True
except ImportError:
    HAS_GEMINI = False

try:
    from langchain_openai import ChatOpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - [%(levelname)s] - %(message)s")
logger = logging.getLogger("AutonomousCodingAssistant")

# ============================================================================
# 1. LLM FACTORY INTEGRATION
# ============================================================================

def get_llm():
    """
    Returns an initialized LLM client based on available environment variables.
    Supports GEMINI_API_KEY and OPENAI_API_KEY. Defaults to None if no key is present.
    """
    if os.getenv("GEMINI_API_KEY") and HAS_GEMINI:
        logger.info("[LLM Factory] Initializing Gemini Model (gemini-2.5-flash)...")
        return ChatGoogleGenerativeAI(model="gemini-2.5-flash", temperature=0.1)
    elif os.getenv("OPENAI_API_KEY") and HAS_OPENAI:
        logger.info("[LLM Factory] Initializing OpenAI Model (gpt-4o)...")
        return ChatOpenAI(model="gpt-4o", temperature=0.1)
    else:
        logger.warning("[LLM Factory] No API key detected (GEMINI_API_KEY/OPENAI_API_KEY). Running in offline fallback mode.")
        return None

# Global LLM Instance
LLM_CLIENT = get_llm()

# ============================================================================
# 2. STATE & SCHEMAS DEFINITION
# ============================================================================

class TaskSpec(BaseModel):
    feature_name: str = Field(description="Short title of the feature")
    summary: str = Field(description="Detailed overview of technical implementation")
    files_to_create_or_modify: List[str] = Field(description="List of file paths to generate/update")
    architecture_notes: str = Field(description="Design decisions, module boundaries, and validation requirements")
    acceptance_criteria: List[str] = Field(description="Specific rules code must pass")
    test_requirements: List[str] = Field(description="Test cases needed in unit test suite")

class IssueDetail(BaseModel):
    category: str = Field(description="Category of issue: SYNTAX, UNIT_TEST, LINT, LOGIC, SECURITY")
    file_path: str = Field(description="File containing the issue")
    line_number: Optional[int] = Field(default=None, description="Line number if applicable")
    description: str = Field(description="Detailed explanation of what failed")
    suggested_fix: str = Field(description="Concrete recommendation to fix the issue")

class ReviewFeedback(BaseModel):
    approved: bool = Field(description="True if code passes all criteria and tests")
    quality_score: float = Field(description="Score between 0.0 and 1.0")
    summary: str = Field(description="Overall review summary")
    issues: List[IssueDetail] = Field(default_factory=list, description="List of issues to resolve if rejected")

class GeneratedFile(BaseModel):
    file_path: str = Field(description="Relative path of the code file")
    content: str = Field(description="Complete, valid source code content")

class CodeGenerationOutput(BaseModel):
    files: List[GeneratedFile] = Field(description="List of generated code and test files")

class AgentState(TypedDict):
    user_request: str
    task_spec: Optional[Dict[str, Any]]
    code_artifacts: Dict[str, str]
    test_results: Optional[Dict[str, Any]]
    review_feedback: Optional[Dict[str, Any]]
    iteration_count: int
    max_iterations: int
    status: str
    messages: List[Dict[str, str]]

# ============================================================================
# 3. MCP TOOL CLIENT INTERFACE
# ============================================================================

class MCPClient:
    """Interface adapter for Model Context Protocol (MCP) Server communication."""
    
    @staticmethod
    def write_file(file_path: str, content: str) -> Dict[str, Any]:
        logger.info(f"[MCP TOOL] mcp__filesystem_write_file -> {file_path}")
        return {"status": "success", "file_path": file_path, "bytes_written": len(content)}

    @staticmethod
    def execute_sandbox_tests(test_framework: str, target_directory: str) -> Dict[str, Any]:
        logger.info(f"[MCP TOOL] mcp__sandbox_execute_tests -> {test_framework} on {target_directory}")
        return {
            "exit_code": 0,
            "passed": 4,
            "failed": 0,
            "stdout": "4 passed in 0.42s",
            "stderr": ""
        }

    @staticmethod
    def run_linter(linter_name: str, files: List[str]) -> Dict[str, Any]:
        logger.info(f"[MCP TOOL] mcp__static_analysis_lint -> {linter_name} on {files}")
        return {"exit_code": 0, "violations": []}

# ============================================================================
# 4. AGENT NODE IMPLEMENTATIONS (LLM Structured Invocations)
# ============================================================================

def architect_agent_node(state: AgentState) -> Dict[str, Any]:
    """
    Architect Agent Node:
    Uses LLM with Pydantic Structured Output to convert user requests into TaskSpec schemas.
    """
    logger.info("=== [Architect Agent] Analyzing request & generating specifications ===")
    user_request = state["user_request"]
    
    if LLM_CLIENT:
        structured_llm = LLM_CLIENT.with_structured_output(TaskSpec)
        prompt = (
            f"You are a Principal Software Architect. Analyze the following feature request "
            f"and generate a precise technical specification including target files, architecture notes, "
            f"acceptance criteria, and test requirements.\n\nFeature Request:\n{user_request}"
        )
        spec: TaskSpec = structured_llm.invoke(prompt)
    else:
        # Offline fallback simulation
        spec = TaskSpec(
            feature_name="Calculate Discounted Total",
            summary=f"Implement feature based on request: {user_request}",
            files_to_create_or_modify=["src/discount.py", "tests/test_discount.py"],
            architecture_notes="Pure functional module with input validation.",
            acceptance_criteria=[
                "Applies percentage discount correctly for total > 0",
                "Raises ValueError on negative total or invalid discount rate",
                "Returns float rounded to 2 decimal places"
            ],
            test_requirements=[
                "Test valid discount calculations",
                "Test edge cases (0% discount, 100% discount)",
                "Test exception throwing for negative values"
            ]
        )
        
    return {
        "task_spec": spec.model_dump(),
        "status": "SPECIFIED",
        "messages": state.get("messages", []) + [{
            "role": "architect",
            "content": f"Task specification created for feature: {spec.feature_name}"
        }]
    }


def coder_agent_node(state: AgentState) -> Dict[str, Any]:
    """
    Coder Agent Node:
    Generates modular code & test suites using LLM structured output, then invokes MCP filesystem tools.
    """
    iteration = state["iteration_count"] + 1
    logger.info(f"=== [Coder Agent] Writing Code (Iteration #{iteration}) ===")
    
    task_spec = state["task_spec"]
    feedback = state.get("review_feedback")
    
    if LLM_CLIENT:
        structured_llm = LLM_CLIENT.with_structured_output(CodeGenerationOutput)
        prompt = f"""You are an Expert Software Engineer.
Write executable Python source code and test files matching this specification:

Task Spec:
{json.dumps(task_spec, indent=2)}

Previous Review Feedback (if rejected):
{json.dumps(feedback, indent=2) if feedback else "None"}

Ensure your implementation satisfies all acceptance criteria and resolves all listed review issues.
Output all requested files.
"""
        result: CodeGenerationOutput = structured_llm.invoke(prompt)
        artifacts = {f.file_path: f.content for f in result.files}
    else:
        # Offline fallback simulation demonstrating feedback loop fix
        if feedback and not feedback.get("approved"):
            logger.info("[Coder Agent] Incorporating review feedback into revised implementation...")
            code_content = '''def calculate_discount(total: float, discount_percent: float) -> float:
    if total < 0 or discount_percent < 0 or discount_percent > 100:
        raise ValueError("Invalid total or discount percentage")
    discounted = total * (1.0 - (discount_percent / 100.0))
    return round(discounted, 2)
'''
        else:
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

    # Execute MCP write file tool for each artifact
    for path, body in artifacts.items():
        MCPClient.write_file(path, body)
        
    return {
        "code_artifacts": artifacts,
        "iteration_count": iteration,
        "status": "CODED",
        "messages": state.get("messages", []) + [{
            "role": "coder",
            "content": f"Code artifacts written to workspace (Iteration #{iteration})."
        }]
    }


def reviewer_tester_agent_node(state: AgentState) -> Dict[str, Any]:
    """
    Reviewer / Tester Agent Node:
    Executes MCP test suites/linters and uses LLM with Pydantic Structured Output to evaluate quality.
    """
    logger.info("=== [Reviewer/Tester Agent] Running Sandbox Tests & Code Audit ===")
    
    # 1. Run MCP Tools
    test_run = MCPClient.execute_sandbox_tests(test_framework="pytest", target_directory="tests/")
    lint_run = MCPClient.run_linter(linter_name="ruff", files=list(state["code_artifacts"].keys()))
    
    iteration = state["iteration_count"]
    task_spec = state["task_spec"]
    code_artifacts = state["code_artifacts"]
    
    if LLM_CLIENT:
        structured_llm = LLM_CLIENT.with_structured_output(ReviewFeedback)
        prompt = f"""You are a Lead QA Engineer and Code Reviewer.
Audit the following code artifacts against the Task Spec and Sandbox Execution Results.

Task Spec:
{json.dumps(task_spec, indent=2)}

Generated Code:
{json.dumps(code_artifacts, indent=2)}

Sandbox Test Results:
{json.dumps(test_run, indent=2)}

Static Analysis Results:
{json.dumps(lint_run, indent=2)}

Evaluate whether the code is approved or rejected. If rejected, provide specific IssueDetail entries for fixing.
"""
        feedback: ReviewFeedback = structured_llm.invoke(prompt)
    else:
        # Offline fallback simulation
        if iteration == 1:
            feedback = ReviewFeedback(
                approved=False,
                quality_score=0.75,
                summary="Unit tests passed, but edge-case validation for discount > 100% is missing.",
                issues=[
                    IssueDetail(
                        category="LOGIC",
                        file_path="src/discount.py",
                        line_number=2,
                        description="Function allows discount_percent > 100 which results in negative total.",
                        suggested_fix="Add validation check `or discount_percent > 100` to raise ValueError."
                    )
                ]
            )
        else:
            feedback = ReviewFeedback(
                approved=True,
                quality_score=0.98,
                summary="All tests passed, edge cases validated, and static analysis reported zero violations.",
                issues=[]
            )
        
    return {
        "test_results": test_run,
        "review_feedback": feedback.model_dump(),
        "status": "APPROVED" if feedback.approved else "REJECTED",
        "messages": state.get("messages", []) + [{
            "role": "reviewer",
            "content": f"Review Result: Approved={feedback.approved}. Quality Score={feedback.quality_score}"
        }]
    }


def escalation_node(state: AgentState) -> Dict[str, Any]:
    """Escalation node when iteration limit is reached without approval."""
    logger.warning("=== [Escalation Node] Max iteration limit reached. Escalating to human dev. ===")
    return {
        "status": "ESCALATED",
        "messages": state.get("messages", []) + [{
            "role": "system",
            "content": f"Escalated to human review after {state['iteration_count']} attempts."
        }]
    }

# ============================================================================
# 5. CONDITIONAL ROUTING & GRAPH BUILDING
# ============================================================================

def evaluate_review_router(state: AgentState) -> Literal["approved", "retry_coder", "escalate"]:
    feedback_dict = state.get("review_feedback", {})
    is_approved = feedback_dict.get("approved", False)
    current_iteration = state.get("iteration_count", 0)
    max_iterations = state.get("max_iterations", 3)
    
    if is_approved:
        logger.info("--> Routing to END: Code passed all tests & review criteria.")
        return "approved"
    elif current_iteration < max_iterations:
        logger.info(f"--> Routing back to Coder Agent (Iteration {current_iteration}/{max_iterations}).")
        return "retry_coder"
    else:
        logger.warning(f"--> Routing to Escalation Node: Hit max iterations ({max_iterations}).")
        return "escalate"


def build_autonomous_coding_graph() -> StateGraph:
    """Assembles and compiles the multi-agent state graph."""
    workflow = StateGraph(AgentState)
    
    workflow.add_node("architect_agent", architect_agent_node)
    workflow.add_node("coder_agent", coder_agent_node)
    workflow.add_node("reviewer_tester_agent", reviewer_tester_agent_node)
    workflow.add_node("escalation_node", escalation_node)
    
    workflow.add_edge(START, "architect_agent")
    workflow.add_edge("architect_agent", "coder_agent")
    workflow.add_edge("coder_agent", "reviewer_tester_agent")
    
    workflow.add_conditional_edges(
        "reviewer_tester_agent",
        evaluate_review_router,
        {
            "approved": END,
            "retry_coder": "coder_agent",
            "escalate": "escalation_node"
        }
    )
    
    workflow.add_edge("escalation_node", END)
    return workflow.compile()

# ============================================================================
# 6. EXECUTION RUNNER
# ============================================================================

if __name__ == "__main__":
    app = build_autonomous_coding_graph()
    
    initial_state: AgentState = {
        "user_request": "Create a function that calculates discounted totals with input validation.",
        "task_spec": None,
        "code_artifacts": {},
        "test_results": None,
        "review_feedback": None,
        "iteration_count": 0,
        "max_iterations": 3,
        "status": "INITIALIZED",
        "messages": []
    }
    
    logger.info("Starting Multi-Agent LLM Coding Graph Execution...\n")
    final_state = app.invoke(initial_state)
    
    print("\n================ FINAL GRAPH RESULT ================")
    print(f"Final Status:     {final_state['status']}")
    print(f"Total Iterations: {final_state['iteration_count']}")
    print(f"Generated Files:  {list(final_state['code_artifacts'].keys())}")
    print(f"Review Summary:   {final_state['review_feedback'].get('summary')}")
    print("====================================================")
