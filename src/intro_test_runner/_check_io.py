"""
Pytest functions for checking user input and output of functions.
"""

from collections.abc import Callable, Sequence
import builtins
import contextlib
import difflib
import io
import itertools
import os
import html

from intro_test_runner._utils import tb_info, unicode_bold, unicode_italics


HTML_OUTPUT = os.environ.get('ITR_HTML_OUTPUT', '')
SHOW_DUMMY_LINES = False  # adds lines to the HTML diff output to keep the two sides lined up (not completely supported yet when there are user inputs)

CSS_REMOVE = "background-color:#ff2e003d;border-radius:3px;"
CSS_ADD = "background-color:#00b49047;border-radius:3px;"
CSS_REMOVE_LINE = "background-color:#f52b0018;border-radius:3px;"
CSS_ADD_LINE = "background-color:#00c69d1f;border-radius:3px;"
CSS_DUMMY_LINE = "background-color:#4444441f;border-radius:3px;"
CSS_USER_INPUT = "color:#008800;font-weight:bold;font-style:italic;"

BOLD_NOTE = " (bold is user input)"
ADD_CHAR = '\u0333'  # unicode character (double underline) that goes under the previous character, used to indicate additions in a diff
REMOVE_CHAR = '\u0334'  # unicode character (squiggle strikethrough) that goes through the previous character, used to indicate removals in a diff
DIFFERENCE_NOTE = (f"\nDifference ( {ADD_CHAR} are missing from your output,"
                   f"  {REMOVE_CHAR} are extra in your output):\n")


# TODO: Dark mode: #fe332153 / #00ffea3b / #ff35232b / #00ffe61e

class redirect_stdin(contextlib._RedirectStream):  # noqa: SLF001, N801
    """Equivalent to the contextlib.redirect_stdout() but for stdin."""

    _stream = 'stdin'


class OutputError(AssertionError):
    """An exception that indicates output did not match expected output."""


class InputError(AssertionError):
    """An exception that indicates the input was not read correctly."""


@contextlib.contextmanager
def no_html():
    """
    A context manager that temporarily disables HTML output (even if the
    environment variable is set).
    """
    global HTML_OUTPUT
    original = HTML_OUTPUT
    HTML_OUTPUT = False
    try:
        yield
    finally:
        HTML_OUTPUT = original


def _indent_lines(string: str, num_spaces: int=4) -> str:
    if string == '':
        return string
    spaces = ' ' * num_spaces
    return spaces + ('\n' + spaces).join(string.splitlines())

def _indent_lines_maybe(string: str, no: bool, num_spaces: int=4) -> str:
    return string if no else ('\n' + _indent_lines(string, num_spaces))

def __html_pretrans(output: str) -> str:
    # we need to make sure we encode the HTML, but that messes with the indices
    # so instead we convert them to other characters first, then process, then convert them to HTML entities
    return output.translate(str.maketrans('&<>', '\u0001\u0002\u0003')) if HTML_OUTPUT else output

def __html_posttrans(output: str) -> str:
    escapes = {
        '\u0001': '&amp;',
        '\u0002': '&lt;',
        '\u0003': '&gt;',
    }
    return ''.join(escapes.get(ch, ch) for ch in output) if HTML_OUTPUT else output

def __apply_joiner(string: str, charcode: str) -> str:
    """Applies the given charcode to every character in the string."""
    return ''.join(ch + charcode for ch in string)

def __remove(text: str, charcode: str = REMOVE_CHAR) -> str:
    """
    Uses unicode combining characters to strikethrough an entire string. By
    default this uses the ~ symbol instead of - to reduce confusion when placed
    over a space. To use -, the second argument should be '\u0336'.

    If HTML_OUTPUT is enabled, this will instead use <span style='{CSS_REMOVE}'>
    tags to strikethrough the text.
    """
    return f"<span style='{CSS_REMOVE}'>{text}</span>" if HTML_OUTPUT else __apply_joiner(text, charcode)

def __remove_line(text: str, charcode: str = REMOVE_CHAR) -> str:
    """
    Uses __remove() on the line, or if the line is blank, adds a comment
    indicating that there was an extra blank line.
    """
    return __remove(text, charcode) if text else __italics("(extra blank line)")

def __add(text: str, charcode: str = ADD_CHAR) -> str:
    """
    Uses unicode combining characters to underline an entire string. By default
    this uses a double underscore instead of _ to reduce confusion when placed
    over a space. To use _, the second argument should be '\u0332'.

    If HTML_OUTPUT is enabled, this will instead use <span style='{CSS_ADD}'>
    tags to underline the text.
    """
    return f"<span style='{CSS_ADD}'>{text}</span>" if HTML_OUTPUT else __apply_joiner(text, charcode)

def __add_line(text: str, charcode: str = ADD_CHAR) -> str:
    """
    Uses __add() on the line, or if the line is blank, adds a comment indicating
    that a line was added.
    """
    return __add(text, charcode) if text else __italics("(missing blank line)")

def __italics(string: str) -> str:
    """
    Italicizes a string. If HTML_OUTPUT is enabled, this will use <i> tags to
    italicize the text. Otherwise, this will use unicode italic characters to
    italicize the text (which only supports letters and parentheses).
    """
    return f"<i>{string}</i>" if HTML_OUTPUT else unicode_italics(string)

def __bold(string: str) -> str:
    """
    Bolds a string. If HTML_OUTPUT is enabled, this will use <b> tags to bold
    the text. Otherwise, this will use unicode bold characters to bold the
    text (which only supports letters and digits).
    """
    return f'<b>{string}</b>' if HTML_OUTPUT else unicode_bold(string)

def __user_input(string: str, start: int, end: int) -> str:
    """
    Applies bolding with __bold() to a string to indicate that it is user input.

    If HTML_OUTPUT is enabled, this will instead use
    <b style="{CSS_USER_INPUT}"> tags to bold the text.
    """
    substr = string[start:end]
    with no_html():
        faux_bold = __bold(substr)
    if HTML_OUTPUT:
        substr = f"<b style='{CSS_USER_INPUT}' data-plain-text='{html.escape(faux_bold)}'>{html.escape(substr)}</b>"
    else:
        substr = faux_bold
    return string[:start] + substr + string[end:]

def __process_user_input(
        output: str,
        inpt_ranges: list[tuple[int, int]],
        process: Callable[[str, int, int], str] = __user_input,
        ) -> str:
    output = __html_pretrans(output)
    if inpt_ranges:
        inpt_ranges.sort(key=lambda x: x[0], reverse=True)
        for start, length in inpt_ranges:
            if length <= 0:
                continue
            output = process(output, start, start+length)
    return __html_posttrans(output)

def __highlight_user_input(output: str, inpt_ranges: list[tuple[int, int]]) -> str:
    return _indent_lines(__process_user_input(output, inpt_ranges, __user_input))
    
def __find_user_input(inpt: str, expected: str, last_end: int) -> int:
    # assumes inpt contains the trailing \n
    # TODO: this can mis-find if the input is also at the end of a line in the expected output
    return expected.rfind(inpt, 0, last_end)

def __highlight_user_input_combined(actual: str, expected: str, inpt_ranges: list[tuple[int, int]]) -> tuple[str, str]:
    with no_html():  # this always generates plain text
        last_end = len(expected)
        def process(string, start, end):
            nonlocal last_end, expected
            inpt = string[start:end]
            index = __find_user_input(inpt, expected, last_end)
            if index != -1:
                expected = __user_input(expected, index, index+len(inpt))
                last_end = index - 1
            return __user_input(string, start, end)
        return __process_user_input(actual, inpt_ranges, process), expected

def __split_trailing_html(line: str) -> tuple[str, str]:
    end_html = ""
    while line[-1] == '>':
        index = line.rfind('<', 0, -1)
        if index == -1:
            break
        end_html = line[index:]
        line = line[:index]
    return line, end_html

def __highlight_user_input_on_line(lines: list[str], line_num: int, length: int):
    if line_num < len(lines):
        line, end_html = __split_trailing_html(lines[line_num])
        lines[line_num] = f"{line[:-length]}<span style='{CSS_USER_INPUT}'>{line[-length:]}</span>{end_html}"

def __highlight_user_input_html(actual: str, expected: str,
                                actual_lines: list[str], expected_lines: list[str],
                                inpt_ranges: list[tuple[int, int]]):
    last_end = len(expected)
    def process(string, start, end):
        nonlocal last_end, expected
        __highlight_user_input_on_line(actual_lines, actual.count('\n', 0, start), end - start)
        inpt = string[start:end]
        index = __find_user_input(inpt, expected, last_end)
        if index != -1:
            __highlight_user_input_on_line(expected_lines, expected.count('\n', 0, index), len(inpt))
            last_end = index - 1
        return __user_input(string, start, end)
    __process_user_input(actual, inpt_ranges, process)

def __call_to_str(func: Callable, args: Sequence = (), kwargs: dict[str, object] = {}) -> str:  # noqa: B006
    sep = ', ' if args and kwargs else ''
    args = ', '.join(repr(arg) for arg in args)
    kwargs_repr = ', '.join(key + '=' + repr(value) for key, value in kwargs.items())
    return f"{func.__module__}.{func.__qualname__}({args}{sep}{kwargs_repr})"

def __user_input_line(line: str) -> str:
    if line == "":
        return __italics('(empty line)')
    elif line == " ":
        return __italics('(line with 1 space)')
    elif line.isspace():
        return __italics(f'(line with {len(line)} spaces)')
    return line

def __user_input_list(inpt: str) -> str:
    return _indent_lines('\n'.join(__user_input_line(line) for line in inpt.splitlines()))

def __check_input(func: Callable, inpt: str, args: Sequence = (), kwargs: dict[str, object] = {}):  # noqa: B006
    msg = f"User input issues with a call to `{__call_to_str(func, args, kwargs)}`\nWith the user input:\n{__user_input_list(inpt)}\n"

    # Prepare the simulated standard input and output
    # The input read() and readline() functions are wrapped so input also shows in the output
    out = io.StringIO()
    in_ = io.StringIO(inpt)
    inpt_ranges = [] # ranges in the output that are actually from the input
    def _read(*args, **kwargs) -> str:  # noqa: ANN002, ANN003
        data = io.StringIO.read(in_, *args, **kwargs)
        inpt_ranges.append((len(out.getvalue()), len(data)))
        out.write(data)
        return data
    def _readline(*args, **kwargs) -> str:  # noqa: ANN002, ANN003
        data = io.StringIO.readline(in_, *args, **kwargs)
        inpt_ranges.append((len(out.getvalue()), len(data)))
        out.write(data)
        return data
    in_.read = _read
    in_.readline = _readline

    # Call the function with the simulated stdin and stdout
    try:
        with contextlib.redirect_stdout(out), redirect_stdin(in_):
            retval = func(*args, **kwargs)
    except EOFError as ex:
        # Check for EOF
        msg += (
            "All of the given user input was read and then it kept trying to get more input.\n"
            "This is likely due to too many `input()` calls or validation not accepting a value "
            "that it should.\n"
            "The output/input up until the error was:\n"
        )
        msg += __highlight_user_input(out.getvalue(), inpt_ranges)
        msg += "\n"
        tb = tb_info(ex.__traceback__)
        if tb is not None:
            msg += f"The `input()` that failed was {tb}.\n"
        raise InputError(msg) from None

    # Check that all of the input was used
    output = out.getvalue()
    if in_.tell() == 0:
        msg += "No input was read at all.\nThe output produced was:\n"
        msg += __highlight_user_input(output, inpt_ranges)
        raise InputError(msg)
    rem = in_.read()
    if rem:
        msg += "Not all of the user input was read.\n"
        msg += "The output/input up until the error was:\n"
        msg += __highlight_user_input(output, inpt_ranges)
        raise InputError(msg)

    # Leave the rest to the check function
    return retval, output, inpt_ranges

def __diff_line(a: str, b: str, limit: float = 0.0) -> str|None:
    """
    Computes a line difference between the a and b strings (in theory they
    should be each a single line that is similar, but they can also be
    multiples lines each (using \n)).

    Returns a string with underlines where there should be insertions in a and
    strikethroughs for things that should be deleted from a.

    The third argument limit determines if a string should be analyzed or not.
    If not analyzed because too much of the line has been changed, then this
    will return None instead of the matching string. A value of 1.0 would make
    this always return None, a value of 0.0 makes this never return None.
    """
    out = ''
    matcher = difflib.SequenceMatcher(a=a, b=b)
    if limit > 0 and limit >= matcher.ratio():
        return None
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag =='equal':
            out += a[i1:i2]
        elif tag == 'delete':
            out += __remove(a[i1:i2])
        elif tag == 'insert':
            out += __add(b[j1:j2])
        elif tag == 'replace':
            out += __remove(a[i1:i2])
            out += __add(b[j1:j2])
    return out

def __diff_lines(a: list[str], b: list[str]) -> list[str]:
    """
    Computes the difference between the a and b list-of-strings with each string
    being one line. This finds equal sections of the lists and the parts that
    need editing are run through __diff_line individually.

    Returns a string with underlines where there should be insertions in a and
    strikethroughs for things that should be deleted from a. The returned result
    is a list of strings.
    """
    out = []
    matcher = difflib.SequenceMatcher(a=a, b=b)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag =='equal':
            out.extend(a[i1:i2])
        elif tag == 'delete':
            out.extend(__remove_line(a[i]) for i in range(i1, i2))
        elif tag == 'insert':
            out.extend(__add_line(b[j]) for j in range(j1, j2))
        elif tag == 'replace':
            for a_line, b_line in zip(a[i1:i2], b[j1:j2]):
                if (diff := __diff_line(a_line, b_line, 0.5)) is None:
                    # TODO: group some of these lines together?
                    out.append(__remove_line(a_line))
                    out.append(__add_line(b_line))
                else:
                    out.append(diff)
            out.extend(__remove_line(a[i]) for i in range(i1 + j2-j1, i2))
            out.extend(__add_line(b[j]) for j in range(j1 + i2-i1, j2))
    return out

def __diff_line_html(a: str, b: str, limit: float = 0.0) -> tuple[str, str]|None:
    """
    Computes a line difference between the a and b strings (in theory they
    should be each a single line that is similar, but they can also be
    multiples lines each (using \n)).

    Returns two strings with the changes required to get from a to b
    respectively.

    The third argument limit determines if a string should be analyzed or not.
    If not analyzed because too much of the line has been changed, then this
    will return None instead of the matching string. A value of 1.0 would make
    this always return None, a value of 0.0 makes this never return None.
    """
    a_out = ''
    b_out = ''
    matcher = difflib.SequenceMatcher(a=a, b=b)
    if limit > 0 and limit >= matcher.ratio():
        return None
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag =='equal':
            a_out += a[i1:i2]
            b_out += b[j1:j2]
        elif tag == 'delete':
            a_out += __remove(a[i1:i2])
        elif tag == 'insert':
            b_out += __add(b[j1:j2])
        elif tag == 'replace':
            a_out += __remove(a[i1:i2])
            b_out += __add(b[j1:j2])
    return a_out, b_out

def __span_line(contents: str, style: str) -> str:
    return f"<span style='{style};width:100%;display:inline-block'>{contents}</span>"

def __span_remove_line(contents: str) -> str:
    return __span_line(__remove_line(contents), CSS_REMOVE_LINE)

def __span_add_line(contents: str) -> str:
    return __span_line(__add_line(contents), CSS_ADD_LINE)

def __span_dummy_line() -> str:
    return __span_line(" ", CSS_DUMMY_LINE)

def __diff_lines_html(a: list[str], b: list[str]) -> tuple[list[str], list[str]]:
    """
    Computes the difference between the a and b list-of-strings with each string
    being one line. This finds equal sections of the lists and the parts that
    need editing are run through __diff_line_html individually.
    """
    out_a = []
    out_b = []
    matcher = difflib.SequenceMatcher(a=a, b=b)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag =='equal':
            out_a.extend(a[i1:i2])
            out_b.extend(b[j1:j2])
        elif tag == 'delete':
            out_a.extend(__span_remove_line(a[i]) for i in range(i1, i2))
            if SHOW_DUMMY_LINES:
                out_b.extend(__span_dummy_line() for j in range(j1, j2))
        elif tag == 'insert':
            if SHOW_DUMMY_LINES:
                out_a.extend(__span_dummy_line() for i in range(i1, i2))
            out_b.extend(__span_add_line(b[j]) for j in range(j1, j2))
        elif tag == 'replace':
            for a_line, b_line in zip(a[i1:i2], b[j1:j2]):
                if (diff := __diff_line_html(a_line, b_line, 0.5)) is None:
                    out_a.append(__span_remove_line(a_line))
                    out_b.append(__span_add_line(b_line))
                else:
                    diff_a, diff_b = diff
                    out_a.append(__span_line(diff_a, CSS_REMOVE_LINE))
                    out_b.append(__span_line(diff_b, CSS_ADD_LINE))
            out_a.extend(__span_remove_line(a[i]) for i in range(i1 + j2-j1, i2))
            out_b.extend(__span_add_line(b[j]) for j in range(j1 + i2-i1, j2))
            if SHOW_DUMMY_LINES:
                out_a.extend(__span_dummy_line() for _ in range(j1 + i2-i1, j2))
                out_b.extend(__span_dummy_line() for _ in range(i1 + j2-j1, i2))
    return out_a, out_b

def __gen_output_message_text(
        printed_lines: list[str], expected_lines: list[str],
        printed_orig: str, expected_orig: str, inpt_ranges: list[tuple[int, int]]
    ) -> str:
    with no_html():
        printed_orig, expected_orig = __highlight_user_input_combined(printed_orig, expected_orig, inpt_ranges)
        single_line = '\n' not in expected_orig and '\n' not in printed_orig
        note = BOLD_NOTE if inpt_ranges else ''
        msg = f"Expected{note}: {_indent_lines_maybe(expected_orig, single_line)}"
        msg += f"\nActual{note}: {_indent_lines_maybe(printed_orig, single_line)}"
        if single_line:
            diff = __diff_line(printed_lines[0], expected_lines[0])
        else:
            diff = '\n'.join(__diff_lines(printed_lines, expected_lines))
        msg += (
            "\nDifference ( \u0333 are missing from your output, "
            " \u0334 are extra in your output):\n"
        )
        msg += _indent_lines(diff)
        return msg

def __gen_output_message_html(
        printed_lines: list[str], expected_lines: list[str],
        printed_orig: str, expected_orig: str, inpt_ranges: list[tuple[int, int]]
    ) -> str:
    plain = html.escape(__gen_output_message_text(printed_lines, expected_lines, printed_orig, expected_orig, inpt_ranges))
    printed_lines = [__html_pretrans(line) for line in printed_lines]
    expected_lines = [__html_pretrans(line) for line in expected_lines]
    prt_diff, exp_diff = __diff_lines_html(printed_lines, expected_lines)
    __highlight_user_input_html(printed_orig, expected_orig, prt_diff, exp_diff, inpt_ranges)
    prt_diff = [__html_posttrans(line) for line in prt_diff]
    exp_diff = [__html_posttrans(line) for line in exp_diff]
    HEADER_STYLE="vertical-align:bottom;border-style:solid;border-color:currentColor;padding-top:0;padding-bottom:0;padding-left:8px;padding-right:8px"
    CELL_STYLE="vertical-align:top;border-style:solid;border-color:currentColor;padding-top:8px;padding-bottom:8px;padding-left:8px;padding-right:8px"
    PRE_STYLE="margin-top:0;margin-bottom:0;margin-left:0;margin-right:0;font-family:monospace"
    if inpt_ranges:
        note = f"<br><span style='font-size:smaller'><b style='{CSS_USER_INPUT}'>green</b> is user input</span>"
    else:
        note = ''
    return (
        f"<table style='color:black;background-color:white;border-collapse:collapse;margin-top:6px' data-plain-text='{plain}'><tr>"
        f"<th style='{HEADER_STYLE};border-width:0 1px 1px 0'>Expected<br><span style='font-size:smaller'><span style='{CSS_ADD}'>Highlights</span> are missing from your output</span>{note}</th>"
        f"<th style='{HEADER_STYLE};border-width:0 0 1px 0'>Actual<br><span style='font-size:smaller'><span style='{CSS_REMOVE}'>Highlights</span> are extra in your output</span>{note}</th></tr>"
        f"<td style='{CELL_STYLE};border-width:0 1px 0 0'><pre style='{PRE_STYLE}'>{'\n'.join(exp_diff)}</pre></td>"
        f"<td style='{CELL_STYLE};border-width:0 0 0 0'><pre style='{PRE_STYLE}'>{'\n'.join(prt_diff)}</pre></td></tr></table>"
    )

def __check_output(call_str, printed: str, inpt_ranges: list[tuple[int, int]], expected: str,
                   _whitespace: str = 'relaxed'):
    printed_orig = printed
    expected_orig = expected
    if _whitespace == 'relaxed':
        printed_lines = [line.rstrip() for line in printed_orig.rstrip('\n').split('\n')]
        expected_lines = [line.rstrip() for line in expected.rstrip('\n').split('\n')]
    else:
        printed_lines = printed.split('\n')
        expected_lines = expected.split('\n')

    # Check for match - return if match
    if printed_lines == expected_lines:
        return

    msg = f"Output mismatch for function call: `{call_str}`\n"
    if HTML_OUTPUT:
        msg += __gen_output_message_html(printed_lines, expected_lines, printed_orig, expected_orig, inpt_ranges)
    else:
        msg += __gen_output_message_text(printed_lines, expected_lines, printed_orig, expected_orig, inpt_ranges)

    raise OutputError(msg)

def check_output(
        expected_output: str, func: Callable, *args: object|None,
        _whitespace: str = 'relaxed',
        **kwargs: object|None,
) -> object|None:
    """
    Check that the output (written to stdout) equals the expected output. The function object must
    be passed in (not already called). If it takes arguments, they can be passed in the args and
    kwargs arguments.

    Optionally, the _whitespace keyword argument can be given to determine how whitespace is
    compared. It can be either 'strict' (whitespace must be exactly equal) or 'relaxed' (the
    default, trailing whitespace on each line is ignored).
    """
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        retval = func(*args, **kwargs)
    __check_output(__call_to_str(func, args, kwargs), out.getvalue(), [], expected_output, _whitespace)
    return retval

def check_output_using_user_input(
        user_input: str, expected_output: str, func: Callable, *args: object|None,
        _whitespace: str = 'relaxed', **kwargs: object|None,
) -> object|None:
    """
    Check that the output (written to stdout) equals the expected_output. The callable must be
    passed in (not already called). If it takes arguments, they can be passed in the args and
    kwargs arguments. Additionally, the function grabs user input (from stdin) and this is checked
    for as well. The input is given in the user_input argument and is added to the printed output.

    The optional _whitespace keyword argument is treated as per check_output().
    """
    retval, out, inpt_ranges = __check_input(func, user_input, args, kwargs)
    __check_output(__call_to_str(func, args, kwargs), out, inpt_ranges, expected_output, _whitespace)
    return retval

def check_input(user_input: str, func: Callable, *args: object|None, _must_output_args: bool = True,
                **kwargs: object|None) -> object|None:
    """
    Get the return value when calling the function with the given arguments and keyword arguments
    along with providing the given input to stdin to be read in. It makes sure that all of the input
    is read. By default you also makes sure that provided arguments also show up in the output, but
    settings _must_output_args=False this will not be checked.
    """
    # Call the function and deal with input checks
    retval, out, inpt_ranges = __check_input(func, user_input, args, kwargs)

    # Check that all the pieces of text showed up in the output
    if _must_output_args:
        for arg in itertools.chain(args, kwargs.values()):
            if isinstance(arg, str) and arg not in out:
                msg = f'The argument value "{arg}" was supposed to appear in the output when calling `{__call_to_str(func, args, kwargs)}`\n'
                msg += f'The actual output/input was:\n{__highlight_user_input(out, inpt_ranges)}'
                raise OutputError(msg)

    return retval

@contextlib.contextmanager
def no_io_during_import():
    """
    Context manager that raises an assert error if print() or input() is called (with any file) or if
    sys.stdout or sys.stdin is written to or read from from any source. Used like:

    with no_io_during_import():
        import some_module  # code to run that should never print() or input() during import
    """
    msg = ("You must have all code in functions and make sure that you have the correct "
           "if __name__ == '__main__': guard so that no code runs during import")
    with no_print(msg=msg), no_input(msg=msg):
        yield None

@contextlib.contextmanager
def no_print(
    print_func_okay: bool = False,
    msg: str = "You are not allowed to use `print()`, instead use return values",
):
    """
    Context manager that raises an assert error if print() is called (with any file) or if
    sys.stdout is written to from any source. Used like:

    with no_print():
        pass # code to run that should never print() or write to stdout
    """
    orig_print = builtins.print
    output = io.StringIO()
    with contextlib.redirect_stdout(output):
        try:
            if not print_func_okay:
                def _print(*args, **kwargs): # noqa: ARG001, ANN002, ANN003
                    raise OutputError(msg)
                builtins.print = _print
            yield None
        finally:
            builtins.print = orig_print
            if output.getvalue():
                raise OutputError(msg)

@contextlib.contextmanager
def no_input(msg: str = "You are not allowed to use `input()`, instead use parameters"):
    """
    Context manager that raises an assert error if input() is called or if sys.stdin is read from
    by any source. Has the side effect that this will suppress any EOFError exceptions. Used like:

    with no_input():
        pass # code to run that should never input() or read from stdin
    """
    orig_input = builtins.input
    with redirect_stdin(io.StringIO()):
        try:
            def _input(prompt: str = ""): # noqa: ARG001
                raise InputError(msg)
            builtins.input = _input
            yield None
        except EOFError:
            raise InputError(msg) from None
        finally:
            builtins.input = orig_input
