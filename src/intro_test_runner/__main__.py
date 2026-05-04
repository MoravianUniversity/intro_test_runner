"""
Command line program that reads tests.json and runs tests accordingly.
"""

from argparse import ArgumentParser
from pathlib import Path
import json
import random
import signal
import io
from contextlib import redirect_stdout

from ._faces import GOOD, REALLY_BAD
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
    args = parser.parse_args()
    src = args.src

    # Read the test configuration
    with open(args.config, encoding="utf-8") as f:
        config = json.load(f)

    modules = config.get("modules", {})
    text_files = config.get("text-files", {})
    py_files = [f"{name}.py" for name in modules]
    test_files = [f"{name}_test.py" for name, conf in modules.items() if check_tests(conf)]

    # Copy files from source directory (this is fatal if any are missing)
    good = copy_files(src, py_files + test_files + list(text_files))
    if not good:
        face = random.choice(REALLY_BAD)
        print(f"{face} No further checks can be done until the missing files are provided. "
                "Please fix and submit again.")
        return

    output = io.StringIO()
    with redirect_stdout(output):
        # Lint all files
        good = lint(py_files + test_files) and good

        # Check modules
        good = check_all(modules, check_module) and good

        # Run tests
        try:
            with timeout(config.get("test-timeout", 5)):
                if not test(test_files) or (Path("_instructor_test.py").is_file() and
                    not test(["_instructor_test.py"], instructor=True)):
                    good = False
        except Timeout as ex:
            print("⌛ The tests took too long to run and timed out. "
                    "There may be an infinite loop or an extra input() in your code.")
            print(f"Your code was terminated in file {ex.__traceback__.tb_frame.f_globals['__file__']} at line {ex.__traceback__.tb_lineno}.")
            good = False

        # Check text files
        good = check_all(text_files, check_text_file) and good

        if good:
            face = random.choice(GOOD)
            print(f"{face} You passed all style checks and code tests! Your submission looks good!")
            print("Due to the nature of these checks, passing does not guarantee full credit.")
        else:
            face = random.choice(REALLY_BAD)
            print(f"{face} Some problems were found in your submission. "
                f"Please fix them and submit again.")

    output_value = output.getvalue()
    print(output_value)
    if not good:
        summary = llm_summary(output_value, config)
        if summary is not None:
            print("\n💡 LLM Summary of Issues: (remember: this is an automated summary and may not be perfect)")
            print(summary)

main()
