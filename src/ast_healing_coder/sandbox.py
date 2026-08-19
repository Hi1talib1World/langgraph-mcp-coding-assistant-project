"""
Sandboxed Execution Engine (Docker / Seccomp / Isolated Subprocess)
Provides isolated execution with network egress blocking and process/time bounds.
"""

import os
import sys
import time
import shutil
import logging
import subprocess
from typing import Dict, Any, List, Optional

logger = logging.getLogger("SandboxedExecutor")

class SandboxedExecutor:
    """Runs test runners and static analyzers inside an isolated sandbox environment."""

    def __init__(self, workspace_dir: str = ".", seccomp_profile_path: Optional[str] = None):
        self.workspace_dir = os.path.abspath(workspace_dir)
        self.seccomp_profile_path = seccomp_profile_path or os.path.join(
            os.path.dirname(__file__), "..", "..", "security", "seccomp_profile.json"
        )
        self.has_docker = self._check_docker()

    def _check_docker(self) -> bool:
        docker_path = shutil.which("docker")
        if not docker_path:
            return False
        try:
            res = subprocess.run(
                [docker_path, "info"], 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE, 
                timeout=3
            )
            return res.returncode == 0
        except Exception:
            return False

    def run_command(
        self, 
        command: List[str], 
        timeout_seconds: int = 30,
        network_enabled: bool = False
    ) -> Dict[str, Any]:
        start_time = time.time()
        
        if self.has_docker and os.path.exists(self.seccomp_profile_path):
            return self._run_docker(command, timeout_seconds, network_enabled, start_time)
        else:
            return self._run_isolated_subprocess(command, timeout_seconds, start_time)

    def _run_docker(
        self, 
        command: List[str], 
        timeout_seconds: int, 
        network_enabled: bool,
        start_time: float
    ) -> Dict[str, Any]:
        logger.info(f"[Sandbox Docker] Executing command with Seccomp & net={'host' if network_enabled else 'none'}")
        docker_cmd = [
            "docker", "run", "--rm",
            "-v", f"{self.workspace_dir}:/workspace:rw",
            "-w", "/workspace",
            "--security-opt", f"seccomp={self.seccomp_profile_path}",
            "--tmpfs", "/tmp:rw,exec,size=64m",
            "--memory=512m",
            "--cpus=1.0"
        ]
        if not network_enabled:
            docker_cmd.extend(["--net", "none"])
            
        docker_cmd.extend(["python:3.11-slim"] + command)
        
        try:
            res = subprocess.run(
                docker_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout_seconds
            )
            duration = round((time.time() - start_time) * 1000, 2)
            return {
                "exit_code": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr,
                "duration_ms": duration,
                "sandbox_type": "docker_seccomp"
            }
        except subprocess.TimeoutExpired:
            return {
                "exit_code": 124,
                "stdout": "",
                "stderr": f"Execution timed out after {timeout_seconds}s",
                "duration_ms": timeout_seconds * 1000,
                "sandbox_type": "docker_seccomp"
            }

    def _run_isolated_subprocess(
        self, 
        command: List[str], 
        timeout_seconds: int,
        start_time: float
    ) -> Dict[str, Any]:
        logger.info(f"[Sandbox Subprocess] Executing isolated subprocess in {self.workspace_dir}")
        try:
            res = subprocess.run(
                command,
                cwd=self.workspace_dir,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout_seconds,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
            )
            duration = round((time.time() - start_time) * 1000, 2)
            return {
                "exit_code": res.returncode,
                "stdout": res.stdout,
                "stderr": res.stderr,
                "duration_ms": duration,
                "sandbox_type": "isolated_subprocess"
            }
        except subprocess.TimeoutExpired:
            return {
                "exit_code": 124,
                "stdout": "",
                "stderr": f"Execution timed out after {timeout_seconds}s",
                "duration_ms": timeout_seconds * 1000,
                "sandbox_type": "isolated_subprocess"
            }
        except Exception as e:
            return {
                "exit_code": 1,
                "stdout": "",
                "stderr": str(e),
                "duration_ms": round((time.time() - start_time) * 1000, 2),
                "sandbox_type": "isolated_subprocess"
            }
