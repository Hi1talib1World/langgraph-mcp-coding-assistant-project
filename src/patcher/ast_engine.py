"""
LibCST / AST Engine: In-Place Node Transformer with Comment & Formatting Preservation.
Applies surgical node edits to Python source code without stripping comments or altering white-space.
"""

import ast
import difflib
import logging
from typing import Tuple, Optional, Dict, Any

try:
    import libcst as cst
    HAS_LIBCST = True
except ImportError:
    HAS_LIBCST = False

logger = logging.getLogger("ASTEngine")

if HAS_LIBCST:
    class LibCSTFunctionReplacer(cst.CSTTransformer):
        """
        LibCST Transformer that finds and replaces a specific FunctionDef node by name
        while preserving all surrounding comments, docstrings, and formatting.
        """
        def __init__(self, target_name: str, replacement_statement: cst.CSTNode):
            super().__init__()
            self.target_name = target_name
            self.replacement_statement = replacement_statement
            self.replaced = False

        def leave_FunctionDef(self, original_node: cst.FunctionDef, updated_node: cst.FunctionDef) -> cst.CSTNode:
            if original_node.name.value == self.target_name:
                logger.info(f"[LibCST Engine] Replacing FunctionDef node '{self.target_name}' (preserving comments & formatting)")
                self.replaced = True
                return self.replacement_statement
            return updated_node

        def leave_ClassDef(self, original_node: cst.ClassDef, updated_node: cst.ClassDef) -> cst.CSTNode:
            if original_node.name.value == self.target_name:
                logger.info(f"[LibCST Engine] Replacing ClassDef node '{self.target_name}' (preserving comments & formatting)")
                self.replaced = True
                return self.replacement_statement
            return updated_node


class FunctionNodeReplacerAST(ast.NodeTransformer):
    """Fallback AST Transformer using Python standard ast module."""
    def __init__(self, target_name: str, replacement_node: ast.AST):
        self.target_name = target_name
        self.replacement_node = replacement_node
        self.replaced = False

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.AST:
        if node.name == self.target_name:
            self.replaced = True
            return ast.copy_location(self.replacement_node, node)
        return self.generic_visit(node)


class ASTEngine:
    """Core CST/AST parsing and surgical node replacement engine."""

    @staticmethod
    def patch_function_node(
        source_code: str, 
        target_name: str, 
        replacement_code: str
    ) -> Tuple[str, str, bool, str]:
        """
        Applies in-place replacement of target_name using LibCST (or ast fallback).
        Returns (patched_source_code, unified_diff, success_flag, error_message).
        """
        # Try LibCST first to preserve comments and formatting
        if HAS_LIBCST:
            try:
                original_cst = cst.parse_module(source_code)
                replacement_cst = cst.parse_module(replacement_code.strip())
                
                # Extract first statement/function from replacement module
                replacement_node = None
                for stmt in replacement_cst.body:
                    if isinstance(stmt, (cst.FunctionDef, cst.ClassDef)):
                        replacement_node = stmt
                        break

                if not replacement_node and len(replacement_cst.body) > 0:
                    replacement_node = replacement_cst.body[0]

                if not replacement_node:
                    return source_code, "", False, "LibCST Error: Replacement code contains no valid statements."

                transformer = LibCSTFunctionReplacer(target_name, replacement_node)
                patched_cst = original_cst.visit(transformer)

                if not transformer.replaced:
                    logger.info(f"[LibCST Engine] Target '{target_name}' not found. Appending node to module.")
                    patched_cst = patched_cst.with_changes(
                        body=list(patched_cst.body) + [replacement_node]
                    )

                patched_code = patched_cst.code

                diff_lines = list(difflib.unified_diff(
                    source_code.splitlines(keepends=True),
                    patched_code.splitlines(keepends=True),
                    fromfile="a/" + target_name,
                    tofile="b/" + target_name,
                ))
                unified_diff = "".join(diff_lines)

                return patched_code, unified_diff, True, ""

            except cst.ParserSyntaxError as e:
                logger.error(f"[LibCST Engine] Syntax error in code: {e}")
                return source_code, "", False, f"SyntaxError in LibCST parser: {str(e)}"
            except Exception as e:
                logger.warning(f"[LibCST Engine] LibCST patch failed ({e}). Falling back to standard AST.")

        # Fallback to standard ast
        try:
            original_tree = ast.parse(source_code)
            replacement_tree = ast.parse(replacement_code)
        except SyntaxError as e:
            return source_code, "", False, f"SyntaxError in Python AST parser: {str(e)}"

        new_func_node = None
        for node in replacement_tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                new_func_node = node
                break

        if not new_func_node:
            return source_code, "", False, "AST Error: Replacement code contains no valid function/class definition."

        transformer = FunctionNodeReplacerAST(target_name, new_func_node)
        patched_tree = transformer.visit(original_tree)
        ast.fix_missing_locations(patched_tree)

        patched_code = ast.unparse(patched_tree)

        diff_lines = list(difflib.unified_diff(
            source_code.splitlines(keepends=True),
            patched_code.splitlines(keepends=True),
            fromfile="a/" + target_name,
            tofile="b/" + target_name,
        ))
        unified_diff = "".join(diff_lines)

        return patched_code, unified_diff, True, ""

    @staticmethod
    def patch_function_in_file(
        file_path: str, 
        target_name: str, 
        replacement_code: str
    ) -> Tuple[bool, str, str]:
        """Reads file_path, applies in-place CST/AST patch, and writes back to disk."""
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                original_code = f.read()
        except FileNotFoundError:
            original_code = ""

        patched_code, diff, success, err = ASTEngine.patch_function_node(original_code, target_name, replacement_code)
        if not success:
            return False, "", err

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(patched_code)

        return True, diff, ""

    @staticmethod
    def calculate_token_savings(full_file_code: str, target_func_code: str) -> Dict[str, Any]:
        full_tokens = len(full_file_code.split())
        target_tokens = len(target_func_code.split())
        saved_tokens = max(0, full_tokens - target_tokens)
        reduction_percentage = round((saved_tokens / max(1, full_tokens)) * 100, 2)
        return {
            "full_file_tokens": full_tokens,
            "target_node_tokens": target_tokens,
            "saved_tokens": saved_tokens,
            "reduction_percentage": reduction_percentage
        }


def patch_function_node(source_code: str, target_name: str, replacement_code: str) -> Tuple[str, str, bool, str]:
    return ASTEngine.patch_function_node(source_code, target_name, replacement_code)


def calculate_token_savings(full_file_code: str, target_func_code: str) -> Dict[str, Any]:
    return ASTEngine.calculate_token_savings(full_file_code, target_func_code)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    code_with_comments = """# Global module configuration comment
import math

# Important comment: calculate_discount handles boundary checks
def calculate_discount(total: float, discount_percent: float) -> float:
    # TODO: Add boundary checks
    return total * (1 - discount_percent / 100)

# Unaffected helper function with comments
def calculate_tax(amount: float, tax_rate: float) -> float:
    # Tax helper logic
    return round(amount * tax_rate, 2)
"""

    replacement_code = """def calculate_discount(total: float, discount_percent: float) -> float:
    if total < 0 or discount_percent < 0 or discount_percent > 100:
        raise ValueError("Invalid bounds")
    return round(total * (1 - discount_percent / 100), 2)
"""

    patched, diff, success, err = patch_function_node(code_with_comments, "calculate_discount", replacement_code)
    print("LibCST Available:", HAS_LIBCST)
    print("--- PATCHED CODE (Preserving Comments) ---")
    print(patched)
    print("--- UNIFIED DIFF ---")
    print(diff)
