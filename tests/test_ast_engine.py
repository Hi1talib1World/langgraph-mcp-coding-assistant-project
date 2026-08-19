"""
Unit tests for LibCST / AST Engine (src/patcher/ast_engine.py).
Verifies node replacement, comment preservation, syntax error handling, and token savings.
"""

import pytest
from patcher.ast_engine import ASTEngine, patch_function_node, calculate_token_savings

def test_patch_function_success():
    original = """def add(a: int, b: int) -> int:
    return a + b
"""
    replacement = """def add(a: int, b: int) -> int:
    return round(a + b)
"""
    patched, diff, success, err = patch_function_node(original, "add", replacement)
    assert success is True
    assert err == ""
    assert "round(a + b)" in patched
    assert "--- a/add" in diff

def test_comment_preservation():
    original_with_comments = """# Module configuration comment
import math

# Important comment: calculate_discount function
def calculate_discount(total: float, discount: float) -> float:
    # TODO: add boundary validation
    return total * (1 - discount / 100)

# Unaffected helper function with comments
def calculate_tax(amount: float) -> float:
    # Tax calculation
    return amount * 0.1
"""

    replacement = """def calculate_discount(total: float, discount: float) -> float:
    if total < 0 or discount < 0 or discount > 100:
        raise ValueError("Invalid bounds")
    return round(total * (1 - discount / 100), 2)
"""
    patched, diff, success, err = patch_function_node(original_with_comments, "calculate_discount", replacement)
    assert success is True
    
    # Verify that surrounding and module-level comments were preserved
    assert "# Module configuration comment" in patched
    assert "# Unaffected helper function with comments" in patched
    assert "def calculate_tax(amount: float) -> float:" in patched

def test_syntax_error_handling():
    invalid_code = "def broken_func(:\n    return 42"
    replacement = "def broken_func():\n    return 42"
    
    patched, diff, success, err = patch_function_node(invalid_code, "broken_func", replacement)
    assert success is False
    assert "SyntaxError" in err

def test_token_savings_calculation():
    full_file = """import sys
import os

def target_func():
    return 1

def large_unused_function_1():
    print("Lots of code here...")

def large_unused_function_2():
    print("More unused code...")
"""
    target_node = "def target_func():\n    return 1"
    
    savings = calculate_token_savings(full_file, target_node)
    assert "reduction_percentage" in savings
    assert savings["full_file_tokens"] > savings["target_node_tokens"]
    assert savings["reduction_percentage"] > 50.0
