"""
Utilities functions.
"""

from pathlib import Path
from itertools import zip_longest
import ast


def name(path: Path|str) -> str:
    return Path(path).name


def ast_eq(node1: ast.AST | list[ast.AST], node2: ast.AST | list[ast.AST]) -> bool:
    """Compare two AST nodes for equality, ignoring line numbers and context."""
    if type(node1) is not type(node2):
        return False
    elif isinstance(node1, ast.AST):
        for k, v in vars(node1).items():
            if k in {"lineno", "end_lineno", "col_offset", "end_col_offset", "ctx"}:
                continue
            if not ast_eq(v, getattr(node2, k)):
                return False
        return True
    elif isinstance(node1, list) and isinstance(node2, list):
        return all(ast_eq(n1, n2) for n1, n2 in zip_longest(node1, node2))
    else:
        return node1 == node2
