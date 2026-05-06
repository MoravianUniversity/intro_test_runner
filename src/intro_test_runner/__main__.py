"""
Command line program that reads tests.json and runs tests accordingly.
"""

from argparse import ArgumentParser
from pathlib import Path
import json
import signal

from ._utils import Output
from ._external_progs import lint, test, llm_summary
from ._internal_checks import check_module, check_text_file, check_all, copy_files, check_tests


class Timeout(RuntimeError):  # noqa: N818
    """Exception raised when a timeout occurs."""


class timeout:  # noqa: N801
    """
    Context manager that raises a Timeout exception if the context (i.e. with statement) is not
    exited before the timeout occurs. If the Timeout is caught but the context is not exited, it
    will be continually be generated again every timeout iteration.
    """

    def __init__(self, seconds: float):
        self.seconds = seconds

    def __handle_timeout(self, _signum: int, _frame):  # noqa: ANN001
        """Called when a timeout occurs"""
        raise Timeout(f"test timed out after {self.seconds}s.")  # noqa: TRY003

    def __enter__(self):
        """Turns on the alarm timer which will call __handle_timeout"""
        signal.signal(signal.SIGALRM, self.__handle_timeout)
        signal.setitimer(signal.ITIMER_REAL, self.seconds, self.seconds)

    def __exit__(self, _exc_type, _exc_val, _exc_tb):  # noqa: ANN001
        """Turns off the alarm timer"""
        signal.setitimer(signal.ITIMER_REAL, 0, self.seconds)


def main():
    # Parse arguments
    parser = ArgumentParser(description="Run intro tests.")
    parser.add_argument("--config", "-c", type=str, default="tests.json",
                        help="Path to the test configuration file (default: tests.json)")
    parser.add_argument("--src", "-s", type=str, default=".",
                        help="Path to the source code directory (default: current directory)")
    parser.add_argument("--html", action="store_true",
                        help="Generate HTML output")
    args = parser.parse_args()
    src = args.src

    # Read the test configuration
    with open(args.config, encoding="utf-8") as f:
        config = json.load(f)
    output = Output()
    problem_types = []

    modules = config.get("modules", {})
    text_files = config.get("text-files", {})
    py_files = [f"{name}.py" for name in modules]
    test_files = [f"{name}_test.py" for name, conf in modules.items() if check_tests(conf)]

    # Copy files from source directory (this is fatal if any are missing)
    missing_files = copy_files(src, py_files + test_files + list(text_files))
    if missing_files:
        for path_str in missing_files:
            output.p(f":-( Your submission does not include `{path_str}` at all.")
        output.p(":-( No further checks can be done until the missing files are provided. "
                 "Please fix and submit again.")
        output.print(args.html)
        return

    # Lint all files
    if not lint(py_files + test_files, output):
        problem_types.append("lint")
    output.reset_faces()

    # Check modules
    if not check_all(modules, output, check_module):
        problem_types.append("module")

    # Run tests
    try:
        with timeout(config.get("test-timeout", 5)):
            if not test(test_files, output):
                problem_types.append("test")
            output.reset_faces()
            if (Path("_instructor_test.py").is_file() and
                not test(["_instructor_test.py"], output, instructor=True)):
                problem_types.append("instructor test")
    except Timeout as ex:
        output.p("⌛ The tests took too long to run and timed out. "
                 "There may be an infinite loop or an extra `input()` in your code.")
        tb = ex.__traceback__
        if tb is not None:
            output.p(f"Your code was terminated in file `{tb.tb_frame.f_globals['__file__']}` at line {tb.tb_lineno}.")
        problem_types.append("timeout")
    output.reset_faces()

    # Check text files
    if not check_all(text_files, output, check_text_file):
        problem_types.append("text")

    if len(problem_types) == 0:
        output.p(":-) You passed all style checks and code tests! Your submission looks good!")
        output.p("Due to the nature of these checks, passing does not guarantee full credit.")
    else:
        output.p(":-( Some problems were found in your submission. "
                 "Please fix them and submit again.")
        llm_summary(output.text, config["llm"], output, problem_types)
    output.print(args.html)

main()
