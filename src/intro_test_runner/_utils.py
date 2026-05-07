"""
Utilities functions.
"""

from pathlib import Path
from itertools import zip_longest
import ast
import html
import random
import re

try:
    from markdown2 import markdown
    MD_KWARGS = {"extras": ["fenced-code-blocks", "tables", "strike", "cuddled-lists", "metadata", "code-friendly"]}
except ImportError:
    try:
        from markdown import markdown
        MD_KWARGS = {"extensions": ["fenced_code", "codehilite", "tables", "sane_lists"]}
    except ImportError:
        markdown = None

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


REALLY_BAD = "😣😖😠😡🤬👿💀"               # :-(
MED_BAD = "😕😟😔😩😫😤"                    # :-{
BAD = "😒😞🙁🥺😢😭😳😨😬😦😧🤕"            # :-|
GOOD = "😀😄😁😊😇🙂😋🤓😎🤩🥳🤗🤭🤠😺😸"   # :-)
FACES = {
    ":-(": REALLY_BAD,
    ":-{": MED_BAD,
    ":-|": BAD,
    ":-)": GOOD,
}

class Output:
    """Class to generate output in different formats."""
    def __init__(self):
        self.text = ""
        self.html = ("<!DOCTYPE html>\n<html lang='en'><head>"
                     "<meta charset='utf-8'>"
                     "<meta http-equiv='Content-Type' content='text/html; charset=utf-8'>"
                     "</head><body>")
        self.faces = {
            ":-(": "",
            ":-{": "",
            ":-|": "",
            ":-)": "",
        }

    def reset_faces(self):
        """Reset the faces to empty strings."""
        for key in self.faces:
            self.faces[key] = ""

    def faceify(self, text: str) -> str:
        """Substitute face codes in text for actual faces."""
        for code, face in self.faces.items():
            if code in text and face == "":
                face = random.choice(FACES[code])
                self.faces[code] = face
            text = text.replace(code, face)
        return text

    def p(self, content: str) -> None:
        """
        Output content as a paragraph. The content can include face codes (:-(, :-{, :-|, and :-))
        which will be replaced with random faces from the appropriate category. The content can
        also include inline code surrounded by backticks (`) which will be wrapped in <code> tags
        in HTML output.
        """
        content = self.faceify(content)
        self.text += f"{content}\n"
        self.html += f"<p>{_htmlify(content)}</p>"

    def pre_terminal(self, content: str, plain_content: str|None = None) -> None:
        """Output content as a preformatted block."""
        plain_content = _remove_ansi_colors((plain_content
                                            if plain_content is not None else content).strip())
        # TODO: _htmlify(content) here? how about the spans (colors), links (ruff output), and difference table (tests)?
        # still have to remove spurious < > and similar characters from output that aren't meant to be HTML
        content = _ansi_colors_to_html(content.strip())
        if not plain_content and not content:
            return
        self.text += f"{plain_content}\n"
        self.html += f"<pre style='font-family:monospace;width:max-content;background-color:#111;color:#fff;padding-top:10px;padding-bottom:10px;padding-left:10px;padding-right:10px'>>{content}</pre>"

    def br(self) -> None:
        """Output a line break or empty line."""
        self.text += "\n"
        self.html += "<br>"

    def md(self, content: str) -> None:
        """Output content as markdown."""
        self.text += f"{content}\n"
        if markdown is not None:
            self.html += f"<div>{markdown(content, **MD_KWARGS)}</div>"
        else:
            self.html += f"<div>{_htmlify(content)}</div>"

    def print(self, html_output: bool) -> None:
        """Print the output in the appropriate format."""
        if html_output:
            print(self.html + "</body></html>")
        else:
            print(self.text)


def _htmlify(text: str) -> str:
    """Substitute special characters in text for HTML display."""
    #re.replace(r'  +', lambda m: '&nbsp;' * (len(m.group(0)) - 1) + ' ', ...)
    return re.sub(r'`([^`]*)`', lambda m: f"<code>{m.group(1)}</code>", html.escape(text)).replace("\n", "<br>")

def _ansi_colors_to_html(text: str) -> str:
    """Convert ANSI color codes into HTML span tags with inline styles."""
    color_map = {
        '1': 'font-weight:bold',
        '4': 'text-decoration:underline',
        '31': 'color:red',
        '32': 'color:green',
        '33': 'color:yellow',
        '34': 'color:blue',
        '35': 'color:magenta',
        '36': 'color:cyan',
        '37': 'color:gainsboro',
        '90': 'color:gray',
        '91': 'color:lightcoral',
        '92': 'color:lightgreen',
        '93': 'color:lightyellow',
        '94': 'color:lightblue',
        '95': 'color:lightpink',
        '96': 'color:lightcyan',
        '97': 'color:white',
        '40': 'background-color:black',
        '41': 'background-color:red',
        '42': 'background-color:green',
        '43': 'background-color:yellow',
        '44': 'background-color:blue',
        '45': 'background-color:magenta',
        '46': 'background-color:cyan',
        '47': 'background-color:gainsboro',
        '100': 'background-color:gray',
        '101': 'background-color:lightcoral',
        '102': 'background-color:lightgreen',
        '103': 'background-color:lightyellow',
        '104': 'background-color:lightblue',
        '105': 'background-color:lightpink',
        '106': 'background-color:lightcyan',
        '107': 'background-color:white',
    }
    
    def replace_color(match):
        codes = match.group(1).split(';')
        reset = max(_rfind(codes, '0'), _rfind(codes, ''))
        if reset != -1:
            codes = codes[:reset]  # ignore any codes after final reset
        if len(codes) == 0:
            return '</span>'
        style = ';'.join(color_map.get(code, '') for code in codes)
        return ('</span>' if reset != -1 else '') + (f'<span style="{style}">' if style else '')
    
    text = re.sub(r'\x1b\[(\d+(;\d+)*)?m', replace_color, text)
    text = text.replace('\x1b[0m', '</span>')  # reset code closes the span
    return text


def _remove_ansi_colors(text: str) -> str:
    """Remove ANSI color codes from output."""
    return re.sub(r'\x1b\[(\d+(;\d+)*)?m', '', text)


def _rfind(lst: list, value) -> int:
    """Find the last index of value in list, or -1 if not found."""
    for i in range(len(lst) - 1, -1, -1):
        if lst[i] == value:
            return i
    return -1
