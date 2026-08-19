"""
Integration tests for Sandbox Runner (src/sandbox/runner.py).
Verifies test execution, line-level Pytest failure parsing, and 5-second hard timeout kill.
"""

import sys
import time
import pytest
from sandbox.runner import SandboxRunner, parse_pytest_failures

def test_sandbox_execution_success():
    runner = SandboxRunner(workspace_dir=".")
    res = runner.execute_pytest(test_target="tests/test_ast_engine.py", timeout_seconds=10)
    assert res.passed is True
    assert res.exit_code == 0
    assert res.duration_ms > 0

def test_pytest_failure_parsing():
    mock_pytest_stdout = """
================ FAILURES ================
________________ test_invalid_discount ________________
    def test_invalid_discount():
>       calculate_discount(100.0, 150.0)
E       AssertionError: DID NOT RAISE <class 'ValueError'>
tests/test_discount.py:16: AssertionError
"""
    failures = parse_pytest_failures(mock_pytest_stdout, "")
    assert len(failures) == 1
    f = failures[0]
    assert f.test_name == "test_invalid_discount"
    assert f.file_path == "tests/test_discount.py"
    assert f.line_number == 16
    assert f.error_type == "AssertionError"

def test_timeout_hard_kill():
    runner = SandboxRunner(workspace_dir=".")
    # Run a command that sleeps longer than 2 seconds with a 2-second timeout
    command = [sys.executable, "-c", "import time; time.sleep(10)"]
    res = runner._run_subprocess_hard_kill(command, timeout_seconds=2, start_time=time.time())
    
    assert res.passed is False
    assert res.exit_code == 124
    assert "TimeoutError" in res.stderr
