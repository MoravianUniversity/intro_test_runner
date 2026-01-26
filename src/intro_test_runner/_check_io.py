"""
Pytest functions for checking user input and output of functions.
"""

from collections.abc import Callable, Sequence
import builtins
import contextlib
import difflib
import io
import itertools
import re


class redirect_stdin(contextlib._RedirectStream):  # noqa: SLF001, N801
    """Equivalent to the contextlib.redirect_stdout() but for stdin."""

    _stream = 'stdin'


class OutputError(AssertionError):
    """An exception that indicates output did not match expected output."""


class InputError(AssertionError):
    """An exception that indicates the input was not read correctly."""


def _indent_lines(string: str, num_spaces: int) -> str:
    if string == '':
        return string
    spaces = ' ' * num_spaces
    return spaces + ('\n' + spaces).join(string.splitlines())

def _indent_lines_maybe(string: str, num_spaces: int, no: bool) -> str:
    return string if no else ('\n' + _indent_lines(string, num_spaces))

def __strikethrough(text: str, charcode: str = '\u0334') -> str:
    """
    Uses unicode combining characters to strikethrough an entire string. By
    default this uses the ~ symbol instead of - to reduce confusion when placed
    over a space. To use -, the second argument should be '\u0336'.
    """
    return ''.join(ch + charcode for ch in text)

def __strikethrough_line(text: str, charcode: str = '\u0334') -> str:
    """
    Uses unicode combining characters to strikethrough an entire string line.
    By default this uses the ~ symbol instead of - to reduce confusion when
    placed over a space. To use -, the second argument should be '\u0336'.
    """
    return __strikethrough(text, charcode) if text else __italics("(extra blank line here)")

def __underline_line(text: str, charcode: str = '\u0333') -> str:
    """
    Uses unicode combining characters to underline an entire string line. By
    default this uses a double underscore instead of _ to reduce confusion when
    placed over a space. To use _, the second argument should be '\u0332'.
    """
    return __underline(text, charcode) if text else __italics("(missing a blank line here)")

def __underline(text: str, charcode: str = '\u0333') -> str:
    """
    Uses unicode combining characters to underline an entire string. By default
    this uses a double underscore instead of _ to reduce confusion when placed
    over a space. To use _, the second argument should be '\u0332'.
    """
    return ''.join(ch + charcode for ch in text)

def __italics(string: str, charcode: str = "\u2060") -> str:
    """
    Italicizes a string using unicode. Only letters and parentheses are
    supported. All other characters are passed through unchanged except that
    all characters (ones changed or not) are appended with the zero-width word
    joiner unicode symbol \\u2060.
    """
    italic_chars = {
        'a': '𝑎', 'b': '𝑏', 'c': '𝑐', 'd': '𝑑', 'e': '𝑒', 'f': '𝑓', 'g': '𝑔', 'h': 'ℎ', 'i': '𝑖', # noqa: RUF001
        'j': '𝑗', 'k': '𝑘', 'l': '𝑙', 'm': '𝑚', 'n': '𝑛', 'o': '𝑜', 'p': '𝑝', 'q': '𝑞', 'r': '𝑟', # noqa: RUF001
        's': '𝑠', 't': '𝑡', 'u': '𝑢', 'v': '𝑣', 'w': '𝑤', 'x': '𝑥', 'y': '𝑦', 'z': '𝑧', # noqa: RUF001
        'A': '𝐴', 'B': '𝐵', 'C': '𝐶', 'D': '𝐷', 'E': '𝐸', 'F': '𝐹', 'G': '𝐺', 'H': '𝐻', 'I': '𝐼', # noqa: RUF001
        'J': '𝐽', 'K': '𝐾', 'L': '𝐿', 'M': '𝑀', 'N': '𝑁', 'O': '𝑂', 'P': '𝑃', 'Q': '𝑄', 'R': '𝑅', # noqa: RUF001
        'S': '𝑆', 'T': '𝑇', 'U': '𝑈', 'V': '𝑉', 'W': '𝑊', 'X': '𝑋', 'Y': '𝑌', 'Z': '𝑍', # noqa: RUF001
        '(': '〈', ')': '〉',
    }
    output = ''
    for ch in string:
        output += italic_chars.get(ch, ch) + charcode
    return output

ORD_0 = ord('0')
ORD_9 = ord('9')
ORD_A = ord('A')
ORD_Z = ord('Z')
ORD_a = ord('a')
ORD_z = ord('z')

def __bold(string: str, charcode: str = "\u2060") -> str:
    """
    Bolds a string using unicode. Only letters and digits are supported. All
    other characters are passed through unchanged except that all characters
    (ones changed or not) are appended with the zero-width word joiner unicode
    symbol \\u2060.
    """
    output = ''
    for ch in string:
        x = ord(ch)
        if ORD_0 <= x <= ORD_9: # numbers
            output += chr(x+120812-ORD_0)
        elif ORD_A <= x <= ORD_Z: # uppercase
            output += chr(x+120276-ORD_A)
        elif ORD_a <= x <= ORD_z: # lowercase
            output += chr(x+120302-ORD_a)
        else:
            output += ch
        output += charcode
    return output

def __bold_substr(string: str, start: int, end: int) -> str:
    """
    Applies bolding with __bold() to a substring, returning the complete string.
    """
    return string[:start] + __bold(string[start:end]) + string[end:]

def __call_to_str(func: Callable, args: Sequence = (), kwargs: dict[str, object] = {}) -> str:  # noqa: B006
    sep = ', ' if args and kwargs else ''
    args = ', '.join(repr(arg) for arg in args)
    kwargs_repr = ', '.join(key + '=' + repr(value) for key, value in kwargs.items())
    return f"{func.__module__}.{func.__qualname__}({args}{sep}{kwargs_repr})"


def __check_input(func: Callable, inpt: str, args: Sequence = (), kwargs: dict[str, object] = {}):  # noqa: B006
    msg = f"""The function call was: {__call_to_str(func, args, kwargs)}
The 'user' typed:\n{_indent_lines(inpt, 4)}\n"""

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
    except EOFError:
        # Check for EOF
        msg += (
            "Your program read all of the user input and then kept trying to get more input. "
            "This is likely due to too many input() calls or validation not accepting a value "
            "that should have been accepted.\n"
        )
        raise InputError(msg) from None

    # Check that all of the input was used
    if in_.tell() == 0:
        msg += 'You did not read any input at all.'
        raise InputError(msg)
    rem = in_.read()
    if rem:
        msg += 'Not all of that input was used, you stopped reading input once you got:\n'+(
            _indent_lines(inpt[:-len(rem)].rstrip('\n').split('\n')[-1], 4))
        raise InputError(msg)

    # Leave the rest to the assert function
    return msg, retval, out.getvalue().rstrip(), inpt_ranges


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
            out += __strikethrough(a[i1:i2])
        elif tag == 'insert':
            out += __underline(b[j1:j2])
        elif tag == 'replace':
            out += __strikethrough(a[i1:i2])
            out += __underline(b[j1:j2])
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
            out.extend(__strikethrough_line(a[i]) for i in range(i1, i2))
        elif tag == 'insert':
            out.extend(__underline_line(b[j]) for j in range(j1, j2))
        elif tag == 'replace':
            for a_line, b_line in zip(a[i1:i2], b[j1:j2]):
                if (diff := __diff_line(a_line, b_line, 0.5)) is None:
                    # TODO: group some of these lines together?
                    out.append(__strikethrough_line(a_line))
                    out.append(__underline_line(b_line))
                else:
                    out.append(diff)
            out.extend(__strikethrough_line(a[i]) for i in range(i1 + j2-j1, i2))
            out.extend(__underline_line(b[j]) for j in range(j1 + i2-i1, j2))
    return out


def __check_output(msg: str, printed: str, inpt_ranges: list[tuple[int, int]], expected: str,
                   _whitespace: str = 'relaxed', _ordered: bool = True, _regexp: bool = False):
    printed_orig = printed
    # TODO: compare without input ranges or add input to expected
    #for start, length in inpt_ranges:
    #    printed = printed[:start] + printed[start+length:]
    expected_orig = expected
    if _whitespace == 'relaxed':
        printed = '\n'.join(line.rstrip() for line in printed_orig.rstrip('\n').split('\n'))
        expected = '\n'.join(line.rstrip() for line in expected.rstrip('\n').split('\n'))
    elif _whitespace == 'ignore':
        printed = ''.join(printed_orig.split())
        expected = ''.join(expected.split())
    elif _whitespace == 'strict':
        printed = printed_orig

    if not _ordered or not _regexp:
        printed = printed.split('\n')
        expected = expected.split('\n')

    if not _ordered:
        printed.sort()
        expected.sort()

    # Check for match - return if match
    if not _regexp:
        if printed == expected:
            return
    elif isinstance(printed, list):
        if any(re.search(e, p) is not None for e, p in zip(expected, printed)):
            return
    elif re.search(expected, printed) is not None:
        return

    single_line = '\n' not in expected_orig and '\n' not in printed_orig
    exp_note = actual_note = ''
    if _regexp:
        exp_note = ' (this is a regular-expression, so will likely look cryptic)'
    if inpt_ranges:
        inpt_ranges.sort(key=lambda x: x[0], reverse=True)
        for start, length in inpt_ranges:
            printed_orig = __bold_substr(printed_orig, start, start+length)
        exp_note += ' (including user input)'
        actual_note = ' (bold text is user input)'
    msg += f"Expected output{exp_note}: {_indent_lines_maybe(expected_orig, 4, single_line)}"
    msg += f"\nActual output{actual_note}: {_indent_lines_maybe(printed_orig, 4, single_line)}"
    if not _regexp and _whitespace != 'ignore':
        # diffs not supported for whitespace='ignore' or _regexp
        # TODO: support whitespace='ignore'
        if single_line:
            diff = __diff_line(printed[0], expected[0])
        else:
            diff = '\n'.join(__diff_lines(printed, expected))
        msg += (
            "\nDifference ( \u0333 are things your output is missing, "
            " \u0334 are things your output has extra):\n"
        )
        msg += _indent_lines(diff, 4)

    if _whitespace == 'ignore':
        msg += '\nNote: all whitespace is ignored'
    if not _ordered:
        msg += '\nNote: order of the lines does not matter'

    raise OutputError(msg)


def check_output(
        expected_output: str, func: Callable, *args: object|None,
        _whitespace: str = 'relaxed', _ordered: bool = True, _regexp: bool = False,
        **kwargs: object|None,
) -> object|None:
    """
    Assert that the output (written to stdout) equals the expected output. The function object must
    be passed in (not already called). If it takes arguments, they can be passed in the args and
    kwargs arguments.

    Optionally, the _whitespace keyword argument can be given to determine how whitespace is
    compared. It can be either 'strict' (whitespace must be exactly equal), 'relaxed' (the default,
    trailing whitespace on each line is ignored), or 'ignore' (all whitespace is ignored).

    The optional _ordered keyword can be given as False to cause the order of the lines to not
    matter when checking the output. This is not compatible with ignoring the whitespace.

    The optional _regexp keyword can be given as True to cause the `expected` argument to be
    treated as as a regular expression during matching.

    Not all combinations of keyword arguments will produce reasonable results. Specifically,
    when using _ordered=False with _regexp=True or _whitespace='ignore'.
    """
    msg = f"The function call was: {__call_to_str(func, args, kwargs)}\n"
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        retval = func(*args, **kwargs)
    __check_output(msg, out.getvalue(), [], expected_output, _whitespace, _ordered, _regexp)
    return retval

def check_output_using_user_input(
        user_input: str, expected_output: str, func: Callable, *args: object|None,
        _whitespace: str = 'relaxed', _ordered: bool = True, _regexp: bool = False,
        **kwargs: object|None,
) -> object|None:
    """
    Check that the output (written to stdout) equals the expected_output. The callable must be
    passed in (not already called). If it takes arguments, they can be passed in the args and
    kwargs arguments. Additionally, the function grabs user input (from stdin) and this is checked
    for as well. The input is given in the user_input argument and is added to the printed output.

    The optional _whitespace, _ordered, and _regexp keyword arguments are treated as per
    check_output_equal().
    """
    msg, retval, out, inpt_ranges = __check_input(func, user_input, args, kwargs)
    __check_output(msg, out, inpt_ranges, expected_output, _whitespace, _ordered, _regexp)
    return retval

def check_input(user_input: str, func: Callable, *args: object|None, _must_output_args: bool = True,
                **kwargs: object|None) -> object|None:
    """
    Assert that the return value is equal when calling the function with the given arguments and
    keyword arguments along with providing the given input to stdin to be read in. It makes sure
    that all of the input is read. By default you also makes sure that provided arguments also
    show up in the output, but settings _must_output_args=False this will not be checked.
    """
    # Call the function and deal with input checks
    msg, retval, out, _ = __check_input(func, user_input, args, kwargs)

    # Check that all the pieces of text showed up in the output
    if _must_output_args:
        for arg in itertools.chain(args, kwargs.values()):
            if isinstance(arg, str) and arg not in out:
                msg += f'The argument value "{arg}" was supposed to appear in the output.\n'
                msg += f'The actual output was:\n{_indent_lines(out, 4)}'
                raise OutputError(msg)

    return retval

@contextlib.contextmanager
def no_print(
    print_func_okay: bool = False,
    msg: str = "You are not allowed to use print(), instead use return values",
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
def no_input(msg: str = "You are not allowed to use input(), instead use parameters"):
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
