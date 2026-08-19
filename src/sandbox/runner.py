"""
Docker SDK & Subprocess Sandbox Runner with Pytest Failure Line Parser & 5-Second Hard Kill.
"""

import os
import re
import sys
import time
import shutil
import json
import logging
import subprocess
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

try:
    import docker
    HAS_DOCKER_SDK = True
except ImportError:
    HAS_DOCKER_SDK = False

logger = logging.getLogger("SandboxRunner")

# ============================================================================
# STRUCTURED SCHEMAS
# ============================================================================

class PytestFailure(BaseModel):
    test_name: str = Field(description="Name of the failing test function")
    file_path: str = Field(description="File path where failure occurred")
    line_number: Optional[int] = Field(default=None, description="Exact line number of failure")
    error_type: str = Field(description="Exception class name (e.g. AssertionError, ValueError)")
    message: str = Field(description="Failure description message")

class PytestExecutionResult(BaseModel):
    passed: bool
    exit_code: int
    total_passed: int = 0
    total_failed: int = 0
    duration_ms: float
    stdout: str
    stderr: str
    sandbox_type: str
    failures: List[PytestFailure] = Field(default_factory=list)

# ============================================================================
# PYTEST FAILURE PARSER ENGINE
# ============================================================================

def parse_pytest_failures(stdout: str, stderr: str) -> List[PytestFailure]:
    """
    Parses raw Pytest stdout/stderr logs into structured PytestFailure objects with exact line numbers.
    """
    failures: List[PytestFailure] = []
    combined_log = stdout + "\n" + stderr

    # Match failure headers like: ________________ test_invalid_over_hundred ________________
    header_matches = list(re.finditer(r"_{3,}\s*(test_\w+|\w+)\s*_{3,}", combined_log))
    
    # Match traceback location lines like: tests/test_discount.py:16: AssertionError: DID NOT RAISE...
    line_matches = list(re.finditer(r"([a-zA-Z0-9_\-/\\]+\.py):(\d+):\s*([A-Za-z0-9_]+Error|[A-Za-z0-9_]+Exception)(:\s*(.*))?", combined_log))

    for match in line_matches:
        file_path = match.group(1)
        line_num = int(match.group(2))
        err_type = match.group(3)
        msg = match.group(5) or "Test assertion failed"

        # Locate associated test function name if available
        test_name = "unknown_test"
        for h in header_matches:
            if h.start() < match.start():
                test_name = h.group(1)

        failures.append(PytestFailure(
            test_name=test_name,
            file_path=file_path,
            line_number=line_num,
            error_type=err_type,
            message=msg.strip()
        ))

    return failures

# ============================================================================
# SANDBOX RUNNER WITH 5-SECOND HARD KILL
# ============================================================================

class SandboxRunner:
    """Executes test suites in Docker SDK containers or isolated subprocesses with a 5s hard kill."""

    def __init__(self, workspace_dir: str = ".", seccomp_profile_path: Optional[str] = None):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.seccomp_profile_path = seccomp_profile_path or os.path.join(
            os.path.dirname(__file__), "..", "..", "security", "seccomp_profile.json"
        )
        self.docker_client = self._init_docker_client()

    def _init_docker_client(self):
        if not HAS_DOCKER_SDK:
            return None
        try:
            client = docker.from_env()
            client.ping()
            return client
        except Exception:
            return None

    def execute_pytest(
        self, 
        test_target: str = "tests/", 
        timeout_seconds: int = 5,
        network_enabled: bool = False
    ) -> PytestExecutionResult:
        """
        Executes pytest inside container or isolated subprocess with a strict timeout.
        Hard kills execution if duration exceeds timeout_seconds.
        """
        start_time = time.time()
        command = [sys.executable, "-m", "pytest", test_target, "-v", "--tb=short"]

        if self.docker_client and os.path.exists(self.seccomp_profile_path):
            return self._run_docker_sdk(command, timeout_seconds, network_enabled, start_time)
        else:
            return self._run_subprocess_hard_kill(command, timeout_seconds, start_time)

    def _run_docker_sdk(
        self, 
        command: List[str], 
        timeout_seconds: int, 
        network_enabled: bool,
        start_time: float
    ) -> PytestExecutionResult:
        logger.info(f"[Docker SDK] Running pytest in container (timeout={timeout_seconds}s, net={'host' if network_enabled else 'none'})")
        try:
            container = self.docker_client.containers.run(
                image="python:3.11-slim",
                command=command,
                volumes={self.workspace_dir: {"bind": "/workspace", "mode": "rw"}},
                working_dir="/workspace",
                network_mode="host" if network_enabled else "none",
                security_opt=[f"seccomp={self.seccomp_profile_path}"],
                tmpfs={"/tmp": "rw,exec,size=64m"},
                mem_limit="512m",
                detach=True
            )

            try:
                result = container.wait(timeout=timeout_seconds)
                exit_code = result.get("StatusCode", 1)
                logs = container.logs(stdout=True, stderr=True).decode("utf-8", errors="replace")
                container.remove(force=True)
                
                duration = round((time.time() - start_time) * 1000, 2)
                failures = parse_pytest_failures(logs, "")
                
                return PytestExecutionResult(
                    passed=(exit_code == 0),
                    exit_code=exit_code,
                    total_passed=logs.count("PASSED"),
                    total_failed=logs.count("FAILED"),
                    duration_ms=duration,
                    stdout=logs,
                    stderr="",
                    sandbox_type="docker_sdk_seccomp",
                    failures=failures
                )

            except Exception:
                # 5-second hard kill
                logger.warning(f"[Docker SDK] Hard killing container after hitting {timeout_seconds}s timeout.")
                container.remove(force=True)
                duration = round((time.time() - start_time) * 1000, 2)
                return PytestExecutionResult(
                    passed=False,
                    exit_code=124,
                    duration_ms=duration,
                    stdout="",
                    stderr=f"TimeoutError: Hard killed execution after {timeout_seconds}s",
                    sandbox_type="docker_sdk_seccomp",
                    failures=[]
                )

        except Exception as e:
            logger.warning(f"[Docker SDK] Failed to launch container ({e}). Falling back to subprocess.")
            return self._run_subprocess_hard_kill(command, timeout_seconds, start_time)

    def _run_subprocess_hard_kill(
        self, 
        command: List[str], 
        timeout_seconds: int,
        start_time: float
    ) -> PytestExecutionResult:
        logger.info(f"[Subprocess Sandbox] Executing process (hard timeout={timeout_seconds}s)")
        try:
            process = subprocess.Popen(
                command,
                cwd=self.workspace_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
            )

            try:
                stdout, stderr = process.communicate(timeout=timeout_seconds)
                exit_code = process.returncode
                duration = round((time.time() - start_time) * 1000, 2)
                failures = parse_pytest_failures(stdout, stderr)

                return PytestExecutionResult(
                    passed=(exit_code == 0),
                    exit_code=exit_code,
                    total_passed=stdout.count("PASSED"),
                    total_failed=stdout.count("FAILED"),
                    duration_ms=duration,
                    stdout=stdout,
                    stderr=stderr,
                    sandbox_type="isolated_subprocess",
                    failures=failures
                )

            except subprocess.TimeoutExpired:
                # 5-second hard kill process
                logger.warning(f"[Subprocess Sandbox] Hard killing process pid={process.pid} after {timeout_seconds}s timeout.")
                process.kill()
                stdout, stderr = process.communicate()
                duration = round((time.time() - start_time) * 1000, 2)

                return PytestExecutionResult(
                    passed=False,
                    exit_code=124,
                    duration_ms=duration,
                    stdout=stdout,
                    stderr=f"TimeoutError: Execution killed after hard limit of {timeout_seconds}s",
                    sandbox_type="isolated_subprocess",
                    failures=[]
                )

        except Exception as e:
            duration = round((time.time() - start_time) * 1000, 2)
            return PytestExecutionResult(
                passed=False,
                exit_code=1,
                duration_ms=duration,
                stdout="",
                stderr=str(e),
                sandbox_type="isolated_subprocess",
                failures=[]
            )

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    runner = SandboxRunner()
    print("Docker SDK Available:", HAS_DOCKER_SDK and runner.docker_client is not None)
    
    # Test failure output parsing
    sample_stdout = """
================ FAILURES ================
________________ test_invalid_over_hundred ________________
    def test_invalid_over_hundred():
>       calculate_discount(100.0, 150.0)
E       AssertionError: DID NOT RAISE <class 'ValueError'>
tests/test_discount.py:16: AssertionError
"""
    res = parse_pytest_failures(sample_stdout, "")
    print("Parsed Structured Failures JSON:")
    print(json.dumps([f.model_dump() for f in res], indent=2))
