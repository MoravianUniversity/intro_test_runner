"""
Runs tests for the intro class. The configuration of the tests are defined in tests.json.
"""

from ._cmd_line import main
from ._check_io import check_output_using_user_input, check_output, check_input, no_input, no_print  # noqa: F401


if __name__ == "__main__":
    main()
