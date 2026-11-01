"""
Unit tests for CLI Entry Point (src/ast_healing_coder/cli.py).
Verifies argument parsing and execution paths.
"""

import sys
import pytest
from unittest.mock import patch, MagicMock
from ast_healing_coder.cli import main

def test_cli_help(capsys):
    with patch.object(sys, "argv", ["ast-coder", "--help"]):
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

def test_cli_version(capsys):
    with patch.object(sys, "argv", ["ast-coder", "--version"]):
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 0

def test_cli_batch_run_invokes_graph():
    mock_app = MagicMock()
    mock_app.invoke.return_value = {"status": "APPROVED"}
    
    with patch("ast_healing_coder.cli.build_self_healing_graph", return_value=mock_app):
        with patch.object(sys, "argv", ["ast-coder", "--request", "Test feature"]):
            with patch("sys.stdout.isatty", return_value=False):
                main()
                mock_app.invoke.assert_called_once()
