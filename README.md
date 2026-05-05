intro_test_runner
=================

A program to run the tests, examine the code, and lint submissions for introductory Python courses using `pytest` and `ruff`.

This program utilizes several files in the testing directory to determine what to check for in the code. The primary file is `tests.json` (modifiable with `-c` flag). This a JSON file that specifies the submission files to test, which functions it should have, which functions should have student-written tests (and how many test questions for each), and any additional files that should be checked. An example file is:

```json
{
  "test-timeout": 5, // default is 5 seconds for running the instructor tests
  "modules": {
    "project_1": {
      "expected-functions": {
        "func1": 3, // expected number of test questions for func1
        "func2": 2 // expected number of test questions for func2
        // if a function name starts with a "_", then it can have any name (but must still exist and have the expected number of test questions)
        // if all functions are expected to have 0 tests, then expected_functions can a list of function names instead of a mapping to test counts, e.g. ["func1", "func2"]
      },
      "check-tests": false, // whether to check for the expected test questions (default is true if expected_functions is given as a dictionary, otherwise false)
      "addl-funcs-allowed": false, // default is false, whether to allow additional functions beyond those specified in expected_functions
      "addl-tests-allowed": false, // default is false, whether to allow additional tests beyond those specified; additional test questions are always allowed
      "min-module-doc-length": 25, // default is 25, minimum length of the module docstring
      "min-func-doc-length": 20, // default is 20, minimum length of each function docstring; can also be a mapping of function name to minimum docstring length, with a special "_default" key for any functions not explicitly listed
      "check-unused-funcs": true, // default is true, whether to check for any functions that are defined but not called anywhere in the code
      "check-useless-funcs": true, // default is true, whether to check for any functions that simply call another function with the same parameters or return a constant value
    }
  },
  "text-files": {
    "README.md": {
      "original-lines": 0, // default is 0, number of lines in the original file
      "min-lines": 0, // default is 0, minimum number of lines in the file
      "max-lines": 100, // default is inf, maximum number of lines in the file
    }
  }
}
```

The program also looks for a `.ruff.toml` or `ruff.toml` file to determine how to run ruff.

The student test files must be named with the format `<module_name>_test.py` (e.g. `project_1_test.py` for `project_1.py`) and must be in the same directory as the module files. If a `_instructor_test.py` file is present in the testing directory, it will also be run as part of the tests.

Installing on Gitkeeper
-----------------------

* Cannot use snap-based installations of python or ruff due to sandboxing issues.
* Must install system-wide Python package pytest.
* To install: `python3 -m pip install git+https://github.com/MoravianUniversity/intro_test_runner.git`
* Use the following action.sh file (along with including the `tests.json`, `.ruff.toml`, and `_instructor_test.py` files in the testing directory):
  ```bash
  #!/bin/bash
  python3 -m intro_test_runner -s "$1"
  exit 0
  ```

Publicly Exposed API
--------------------

This module provides the following functions for helping with instructor testing:

```python
def check_output(
  expected_output: str, func: Callable, *args,
  _whitespace: str = 'relaxed', _ordered: bool = True, _regexp: bool = False,
  **kwargs,
) -> object|None
```

Assert that the output (written to stdout) equals `expected_output` when calling `func(*args, **kwargs)`. Return the value returned by the function call.

Optionally, the `_whitespace` keyword argument can be given to determine how whitespace is compared. It can be either `'strict'` (whitespace must be exactly equal), `'relaxed'` (the default, trailing whitespace on each line is ignored), or `'ignore'` (all whitespace is ignored).

The optional `_ordered` keyword can be given as `False` to cause the order of the lines to not matter when checking the output.

The optional `_regexp` keyword can be given as `True` to cause the `expected` argument to be treated as as a regular expression during matching.

Not all combinations of keyword arguments will produce reasonable results. Specifically, when using `_ordered=False` with `_regexp=True` or `_whitespace='ignore'`.

```python
def check_output_using_user_input(
  user_input: str, expected_output: str, func: Callable, *args,
  _whitespace: str = 'relaxed', _ordered: bool = True, _regexp: bool = False,
  **kwargs,
) -> object|None
```

Assert that the output (written to stdout) equals `expected_output` when calling `func(*args, **kwargs)` when `user_input` is provided via stdin. This asserts that all of the user input is consumed by the function call. The `expected_output` must include the user input as well. Return the value returned by the function call.

The optional `_whitespace`, `_ordered`, and `_regexp` keyword arguments are treated as per `check_output_equal()`.

```python
def check_input(user_input: str, func: Callable, *args, _must_output_args: bool = True,
                **kwargs) -> object|None
```

Get the return value when calling `func(*args, **kwargs)` when `user_input` is provided via stdin. This asserts that all of the user input is consumed by the function call. By default you also makes sure that provided arguments show up in the output, but setting `_must_output_args=False` will not check that.

```python
@contextlib.contextmanager
def no_print(
    print_func_okay: bool = False,
    msg: str = "You are not allowed to use print(), instead use return values",
)
```

Context manager that raises an assert error if `print()` is called (with any file) or if `sys.stdout` is written to from any source. Passing `print_func_okay=True` allows the `print()` function to be called, but it still raises an assert error if anything is written to `sys.stdout` from any source (including `print()`). The optional `msg` argument can be used to specify the message of the assert error that is raised.

Used like:

```python
with no_print():
    pass # code to run that should never print() or write to stdout
```

```python
@contextlib.contextmanager
def no_input(msg: str = "You are not allowed to use input(), instead use parameters")
```

Context manager that raises an assert error if `input()` is called or if `sys.stdin` is read from by any source. Has the side effect that this will suppress any `EOFError` exceptions. Used like:

```python
with no_input():
    pass # code to run that should never input() or read from stdin
```

Enabling AI Summary
-------------------

New students often struggle to understand the lint and test messages. To help with this, the `intro_test_runner` can be configured to provide an AI-generated summary of the lint and test results. This summary is generated by sending the lint and test output to an LLM and asking it to summarize the results in a way that is helpful for students.

To enable this feature, you need to set up an LLM that supports the OpenAI API. Three locally hosted LLM options are [llama.cpp](https://llama-cpp.com/), [vllm](https://vllm.ai/), and [ollama](https://ollama.com/). We have been using the the [Llama-3.1-8B-Instruct model](https://huggingface.co/unsloth/Llama-3.1-8B-Instruct-GGUF) which provides decent results and is quite fast (results in <5 seconds in our setup).

Once it is set up, you can enable it in the test runner with options in the `tests.json` file:

```json
{
  // other options...
  "llm": {
    "host": "http://localhost:30000/v1", // URL of the LLM's OpenAI API endpoint
    "model": "...", // optional, name of the model to specify in the API request (only required if your LLM's API endpoint serves multiple models)
    "prompt-header": "...", // optional, header to include at the beginning of the prompt sent to the LLM (see below)
    "addl-prompt": "", // optional, additional prompt to include at the end of the default prompt
  }
}
```

The default `prompt-header` is:

```plain-text
You are tutor explaining the results of {types_str} to a student for their Python code assignment.
Address the student but don't ask for follow up. The output doesn't need an intro, conclusion, or
general advice. Be succinct. Address the highest-level problems first. It is okay to ignore
specific problems, especially if they are repeated or dependent on other issues. Give an overall
summary of each unique problem in the report with the next steps and how to fix it (for example
which line of code to look at and/or what to do). Combine repeats. Do not mention problems that are
not in the report. Do not give any advice that is not directly related to the problems in the
report. {supession_note}{instructor_note}{either_note}{addl_prompt}Here is the report the student
received:
```

where `{types_str}` is replaced with the types of problems in the report (e.g. "linting and instructor test problems"),`{supression_note}` is replaced with "You may not suggest that they suppress linting messages or change linting settings." if there are linting problems, `{instructor_note}` is replaced with "The instructor tests may not be changed and are correct. " if there are instructor test problems, `{either_note}` is replaced with "Instead, guide the student on how they should fix the underlying problems in their code. " if there are either linting or instructor test problems, and `{addl_prompt}` is replaced with any additional prompt specified in the `tests.json` file.
