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
    """Get the name of a file (without the extension)."""
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
    """
    Extracts the file and line number of the first frame in the traceback that
    is within the given base directory (or the current working directory if no
    base is given) and does not end with "_instructor_test.py". Returns a
    string in the format:

    "in file `relative/path/to/file.py` on line 42, in function func_name()"
    """
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


ORD_0 = ord('0')
ORD_9 = ord('9')
ORD_A = ord('A')
ORD_Z = ord('Z')
ORD_a = ord('a')
ORD_z = ord('z')

ORD_0_BOLD = ord('𝟎')
ORD_9_BOLD = ord('𝟗')
ORD_A_BOLD = ord('𝐀')
ORD_Z_BOLD = ord('𝐙')
ORD_a_BOLD = ord('𝒂')
ORD_z_BOLD = ord('𝒛')

def __unicode_bold(ch: str) -> str:
    x = ord(ch)
    if ORD_0 <= x <= ORD_9: # numbers
        return chr(x+ORD_0_BOLD-ORD_0)
    elif ORD_A <= x <= ORD_Z: # uppercase
        return chr(x+ORD_A_BOLD-ORD_A)
    elif ORD_a <= x <= ORD_z: # lowercase
        return chr(x+ORD_a_BOLD-ORD_a)
    else:
        return ch

def unicode_bold(string: str) -> str:
    """
    Bolds a string using unicode. Only letters and digits are supported. All
    other characters are passed through unchanged.
    """
    return ''.join(__unicode_bold(ch) for ch in string)

def __unicode_unbold(ch: str) -> str:
    x = ord(ch)
    if ORD_0_BOLD <= x <= ORD_9_BOLD: # numbers
        return chr(x-ORD_0_BOLD+ORD_0)
    elif ORD_A_BOLD <= x <= ORD_Z_BOLD: # uppercase
        return chr(x-ORD_A_BOLD+ORD_A)
    elif ORD_a_BOLD <= x <= ORD_z_BOLD: # lowercase
        return chr(x-ORD_a_BOLD+ORD_a)
    else:
        return ch

def unicode_unbold(string: str) -> str:
    """
    Unbolds a string that was bolded using unicode_bold. Only letters and
    digits are supported. All other characters are passed through unchanged.
    """
    return ''.join(__unicode_unbold(ch) for ch in string)

ITALIC_CHARS = {
    'a': '𝑎', 'b': '𝑏', 'c': '𝑐', 'd': '𝑑', 'e': '𝑒', 'f': '𝑓', 'g': '𝑔', 'h': 'ℎ', 'i': '𝑖', # noqa: RUF001
    'j': '𝑗', 'k': '𝑘', 'l': '𝑙', 'm': '𝑚', 'n': '𝑛', 'o': '𝑜', 'p': '𝑝', 'q': '𝑞', 'r': '𝑟', # noqa: RUF001
    's': '𝑠', 't': '𝑡', 'u': '𝑢', 'v': '𝑣', 'w': '𝑤', 'x': '𝑥', 'y': '𝑦', 'z': '𝑧', # noqa: RUF001
    'A': '𝐴', 'B': '𝐵', 'C': '𝐶', 'D': '𝐷', 'E': '𝐸', 'F': '𝐹', 'G': '𝐺', 'H': '𝐻', 'I': '𝐼', # noqa: RUF001
    'J': '𝐽', 'K': '𝐾', 'L': '𝐿', 'M': '𝑀', 'N': '𝑁', 'O': '𝑂', 'P': '𝑃', 'Q': '𝑄', 'R': '𝑅', # noqa: RUF001
    'S': '𝑆', 'T': '𝑇', 'U': '𝑈', 'V': '𝑉', 'W': '𝑊', 'X': '𝑋', 'Y': '𝑌', 'Z': '𝑍', # noqa: RUF001
    '(': '〈', ')': '〉',
}

UNITALIC_CHARS = {v: k for k, v in ITALIC_CHARS.items()}

def unicode_italics(string: str) -> str:
    """
    Italicizes a string using unicode. Only letters and parentheses are
    supported. All other characters are passed through unchanged.
    """
    return ''.join(ITALIC_CHARS.get(ch, ch) for ch in string)

def unicode_unitalics(string: str) -> str:
    """
    Unitalicizes a string that was italicized using unicode_italics. Only
    letters and parentheses are supported. All other characters are passed
    through unchanged.
    """
    return ''.join(UNITALIC_CHARS.get(ch, ch) for ch in string)
