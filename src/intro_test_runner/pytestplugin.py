"""
Pytest configuration file to customize test reporting behavior.
"""

from collections.abc import Generator

import pytest

from ._check_io import OutputError, InputError

@pytest.hookimpl(wrapper=True, tryfirst=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo) -> Generator:  # noqa: ARG001
    """
    Hook wrapper to process the test report after execution.
    """
    # Execute all other hooks to obtain the report object
    report: pytest.TestReport = yield

    # When a call fails with OutputError or InputError, set longrepr to just the error message
    # These are custom exceptions defined when using check_output_using_user_input(),
    # check_output(), or check_input().
    if (report.when == "call" and report.failed and
        isinstance(call.excinfo.value, (OutputError, InputError))):
            report.longrepr = str(call.excinfo.value)

    return report
