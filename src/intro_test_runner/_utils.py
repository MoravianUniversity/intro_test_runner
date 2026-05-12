"""
Utilities functions.
"""

import os
from pathlib import Path
from itertools import zip_longest
import ast
import traceback
from types import TracebackType

def name(path: Path|str, no_ext: bool = False) -> str:
    return Path(path).stem if no_ext else Path(path).name

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

def tb_info(tb: TracebackType|None, base: str|None = None) -> str|None:
    if tb is None:
        return None
    if base is None:
        base = os.getcwd()
    base = os.path.abspath(base)
    for frame in traceback.extract_tb(tb):
        file = frame.filename
        if isinstance(file, str) and os.path.abspath(file).startswith(base) and not file.endswith("_instructor_test.py"):
            file = os.path.relpath(file, base)
            func_name = frame.name
            if func_name:
                return f"in file `{file}` on line {frame.lineno}, in function {func_name}()"
            return f"in file `{file}` on line {frame.lineno}"
    return None
