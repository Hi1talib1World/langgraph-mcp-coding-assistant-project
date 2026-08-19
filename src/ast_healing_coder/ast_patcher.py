"""
AST-Guided Code Patching Engine
Surgically modifies specific function or class nodes in Python ASTs without full-file rewrites.
"""

import ast
import difflib
import logging
from typing import Tuple, Optional

logger = logging.getLogger("ASTPatcher")

class FunctionNodeReplacer(ast.NodeTransformer):
    """AST Transformer that finds and replaces a target FunctionDef or AsyncFunctionDef node by name."""
    def __init__(self, target_name: str, replacement_node: ast.AST):
        self.target_name = target_name
        self.replacement_node = replacement_node
        self.replaced = False

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        if node.name == self.target_name:
            logger.info(f"[AST Patcher] Matched FunctionDef node: '{self.target_name}'")
            self.replaced = True
            return ast.copy_location(self.replacement_node, node)
        return self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> ast.AST:
        if node.name == self.target_name:
            logger.info(f"[AST Patcher] Matched AsyncFunctionDef node: '{self.target_name}'")
            self.replaced = True
            return ast.copy_location(self.replacement_node, node)
        return self.generic_visit(node)


def extract_node_source(code: str, target_name: str) -> Optional[str]:
    """Extracts raw source code of a target function node from Python code string."""
    try:
        tree = ast.parse(code)
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == target_name:
                return ast.unparse(node)
    except Exception:
        pass
    return None


def patch_function_in_code(
    source_code: str, 
    target_name: str, 
    replacement_code: str
) -> Tuple[str, str, bool]:
    """
    Parses source_code and replacement_code into ASTs, replaces target_name node,
    and returns (patched_source_code, unified_diff, success_flag).
    """
    try:
        original_tree = ast.parse(source_code)
        replacement_tree = ast.parse(replacement_code)
    except SyntaxError as e:
        logger.error(f"[AST Patcher] Syntax error parsing input code: {e}")
        return source_code, f"SyntaxError: {str(e)}", False

    new_func_node = None
    for node in replacement_tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            new_func_node = node
            break

    if not new_func_node:
        logger.error("[AST Patcher] Replacement code does not contain a valid FunctionDef node.")
        return source_code, "Error: Replacement code must contain a valid function definition.", False

    transformer = FunctionNodeReplacer(target_name, new_func_node)
    patched_tree = transformer.visit(original_tree)
    ast.fix_missing_locations(patched_tree)

    if not transformer.replaced:
        logger.info(f"[AST Patcher] Target function '{target_name}' not found. Appending node to module.")
        patched_tree.body.append(new_func_node)

    patched_code = ast.unparse(patched_tree)

    diff_lines = list(difflib.unified_diff(
        source_code.splitlines(keepends=True),
        patched_code.splitlines(keepends=True),
        fromfile="a/" + target_name,
        tofile="b/" + target_name,
    ))
    unified_diff = "".join(diff_lines)

    return patched_code, unified_diff, True


def patch_function_in_file(
    file_path: str, 
    target_name: str, 
    replacement_code: str
) -> Tuple[bool, str, str]:
    """Reads target file, performs AST replacement, verifies syntax, and updates disk file."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            original_code = f.read()
    except FileNotFoundError:
        original_code = ""

    patched_code, diff, success = patch_function_in_code(original_code, target_name, replacement_code)
    if not success:
        return False, "", diff

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(patched_code)

    logger.info(f"[AST Patcher] Successfully patched '{target_name}' in {file_path}")
    return True, diff, ""
