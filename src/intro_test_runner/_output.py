"""
Module for generating output in different formats (plain text and HTML). The Output class provides
methods to add content in various formats (paragraphs, preformatted blocks, markdown) and handles
the conversion of special face codes into actual faces, as well as the conversion of ANSI color
codes into HTML styles. The final output can be printed in either plain text or HTML format.
"""

import html
import random
import re
from typing import Callable

try:
    from markdown2 import markdown
    MD_KWARGS = {"extras": ["fenced-code-blocks", "tables", "strike", "cuddled-lists", "metadata", "code-friendly"]}
except ImportError:
    try:
        from markdown import markdown
        MD_KWARGS = {"extensions": ["fenced_code", "codehilite", "tables", "sane_lists"]}
    except ImportError:
        markdown = None

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
        self.text += f"{content}\n\n"
        self.html += f"<p>{_htmlify(content)}</p>"

    def pre_terminal(
            self, content: str, post_process: Callable[[str], str]|None = None
            ) -> None:
        """Output content as a preformatted block."""
        html_content, plain_content = split_html_and_plain_text(content)
        plain_content = _remove_ansi_colors(plain_content.strip())
        html_content = _ansi_colors_to_html(html_content.strip())
        if not plain_content and not html_content:
            return
        if post_process:
            html_content = post_process(html_content)
        self.text += f"{plain_content}\n\n"
        self.html += f"<pre style='font-family:monospace;width:max-content;background-color:#111;color:#fff;padding-top:10px;padding-bottom:10px;padding-left:10px;padding-right:10px'>>{html_content}</pre>"

    def br(self) -> None:
        """Output a line break or empty line."""
        self.text += "\n"
        self.html += "<br>"

    def hr(self) -> None:
        """Output a horizontal rule."""
        self.text += f"{'-'*80}\n"
        self.html += "<hr>"

    def md(self, content: str) -> None:
        """Output content as markdown."""
        self.text += f"{content}\n\n"
        if markdown is not None:
            self.html += f"<div>{markdown(content, **MD_KWARGS)}</div>"  # type: ignore
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
        '31': 'color:#ff0000',
        '32': 'color:#00ff00',
        '33': 'color:#ffff00',
        '34': 'color:#0000ff',
        '35': 'color:#ff00ff',
        '36': 'color:#00ffff',
        '37': 'color:#aaaaaa',
        '90': 'color:#555555',
        '91': 'color:#ff8080',
        '92': 'color:#80ff80',
        '93': 'color:#ffff80',
        '94': 'color:#8080ff',
        '95': 'color:#ff80ff',
        '96': 'color:#80ffff',
        '97': 'color:#ffffff',
        '40': 'background-color:#000000',
        '41': 'background-color:#ff0000',
        '42': 'background-color:#00ff00',
        '43': 'background-color:#ffff00',
        '44': 'background-color:#0000ff',
        '45': 'background-color:#ff00ff',
        '46': 'background-color:#00ffff',
        '47': 'background-color:#aaaaaa',
        '100': 'background-color:#555555',
        '101': 'background-color:#ff8080',
        '102': 'background-color:#80ff80',
        '103': 'background-color:#ffff80',
        '104': 'background-color:#8080ff',
        '105': 'background-color:#ff80ff',
        '106': 'background-color:#80ffff',
        '107': 'background-color:#ffffff',
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


def split_html_and_plain_text(mixed: str) -> tuple[str, str]:
    """
    Splits a mixed HTML/plain-text string into separate HTML and plain-text
    versions as follows:
     * Valid HTML tags that have a `data-plain-text` attribute are treated as
       HTML blocks. They are preserved verbatim in the HTML output. In the
       plain-text output they are replaced by the value of their
       `data-plain-text` attribute.
     * Everything else is treated as raw plain text. In the HTML output it is
       HTML-encoded. In the plain-text output it is left as-is.

    Parameters
    ----------
    mixed : str
        The input string that may contain a mixture of literal text and HTML
        elements annotated with `data-plain-text`.

    Returns
    -------
    html: str
        the HTML-safe version of the input
    plain_text: str
        the plain-text version of the input

    Examples
    --------
    >>> html, plain_text = split_html_and_plain_text(
    ...     'Hello <b data-plain-text="bold word">World</b>!'
    ... )
    >>> html
    'Hello <b data-plain-text="bold word">World</b>!'
    >>> plain_text
    'Hello bold word!'
    """

    # Matches an HTML tag with a data-plain-text attribute:
    #   1: tag name
    #   2: the whole opening tag
    #   3/4: value of data-plain-text
    OPEN_TAG_RE = re.compile(
        r'(<([a-zA-Z][a-zA-Z0-9]*)\b[^>]*?\bdata-plain-text=(?:"([^"]*)"|\'([^\']*)\')[^>]*?>)',
    )

    html_parts: list[str] = []
    plain_parts: list[str] = []
    pos = 0  # current position in `mixed`

    for match in OPEN_TAG_RE.finditer(mixed):
        # Plain-text before this tag
        if (before := mixed[pos:match.start()]):
            html_parts.append(html.escape(before))
            plain_parts.append(before)

        # Grab the HTML block
        tag_name = match.group(2)
        open_tag = match.group(1)
        plain_text_value = match.group(3) if match.group(4) is None else match.group(4)

        # Find the matching closing tag, accounting for nesting.
        close_pat = re.compile(
            rf"<{re.escape(tag_name)}\b[^>]*>|</{re.escape(tag_name)}\s*>",
            re.IGNORECASE | re.DOTALL,
        )

        depth = 1
        search_from = match.end()
        closing_end = None
        for cm in close_pat.finditer(mixed, search_from):
            if cm.group(0).startswith("</"):
                depth -= 1
                if depth == 0:
                    closing_end = cm.end()
                    break
            else:
                depth += 1

        if closing_end is None:
            # No matching close tag found – treat as plain text
            html_parts.append(html.escape(open_tag))
            plain_parts.append(open_tag)
            pos = match.end()
            continue

        full_block = mixed[match.start():closing_end]

        # Append the HTML block
        html_parts.append(full_block)
        plain_parts.append(plain_text_value)

        pos = closing_end

    # Any trailing plain-text after the last tag
    tail = mixed[pos:]
    if tail:
        html_parts.append(html.escape(tail))
        plain_parts.append(tail)

    return "".join(html_parts), "".join(plain_parts)
