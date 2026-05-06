"""
Utilities functions.
"""

from pathlib import Path
from itertools import zip_longest
import ast
import html
import random
import re

import markdown

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
MED_BAD = "😕😟😔😩😫😮‍💨😤"                  # :-{
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
        self.html = "<html><body>"
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

    def htmlify(self, text: str) -> str:
        """Substitute special characters in text for HTML display."""
        #re.replace(r'  +', lambda m: '&nbsp;' * (len(m.group(0)) - 1) + ' ', ...)
        return re.sub(r'`([^`]*)`', lambda m: f"<code>{m.group(1)}</code>", html.escape(text)).replace("\n", "<br>")

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
        self.html += f"<p>{self.htmlify(content)}</p>"

    def pre(self, content: str) -> None:
        """Output content as a preformatted block."""
        self.text += f"{content}\n"
        self.html += f"<pre>{content}</pre>" # TODO: self.htmlify(content) here? how about the links?

    def br(self) -> None:
        """Output a line break or empty line."""
        self.text += "\n"
        self.html += "<br>"

    def md(self, content: str) -> None:
        """Output content as markdown."""
        self.text += f"{content}\n"
        self.html += f"<div>{markdown.markdown(content)}</div>"

    def print(self, html_output: bool) -> None:
        """Print the output in the appropriate format."""
        if html_output:
            print(self.html + "</body></html>")
        else:
            print(self.text)
