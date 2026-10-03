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
      "forbid": ["f-string", "str.format", "function:print"], // optional list of forbidden language features (supported: "f-string", "str.format", "percent-format", "lambda", "comprehension", "ternary", "if-exp", "class", "walrus", "match", "try", "with", "global", "nonlocal", "eval", "exec", "while", "for", "break", "continue", "map", "filter", "reduce", "nested-function", "async", "yield"; also "function:<name>" to forbid any call by that name, e.g. "function:print")
      "function-planner": { // optional; checks the online function plan for this module; see Function Planner section below for more details
        "plan": "project-1", // base plan id (slug) in the function-planner tool
        "check": true, // default true; query the planner for plan warnings/errors (both fail the check)
        "compare": true // default true; compare the plan to this module's Python (and its *_test.py when check-tests includes that file)
      }
    }
  },
  "text-files": {
    "README.md": {
      "original-lines": 0, // default is 0, number of lines in the original file
      "min-lines": 0, // default is 0, minimum number of lines in the file
      "max-lines": 100, // default is inf, maximum number of lines in the file
    }
  },
  "function-planner": { // optional; required when any module uses function-planner checks
    "api-prefix": "https://example.com/api", // base URL for the function-planner API (no trailing slash needed)
    "api-token": "<bearer jwt>" // course API bearer token from the function-planner roster
  }
}
```

The program also looks for a `.ruff.toml` or `ruff.toml` file to determine how to run ruff.

The student test files must be named with the format `<module_name>_test.py` (e.g. `project_1_test.py` for `project_1.py`) and must be in the same directory as the module files. If a `_instructor_test.py` file is present in the testing directory, it will also be run as part of the tests.

Global Defaults
---------------

Shared settings such as `llm` and `function-planner` (including API tokens) can live in a global defaults file that is deep-merged under the assignment `tests.json`. Assignment values win on conflicts; nested objects are merged key-by-key.

The first existing file in this list is used:

1. `--global-config PATH`
2. `ITR_CONFIG` environment variable (path to a JSON file)
3. `$XDG_CONFIG_HOME/intro_test_runner/config.json`, or `~/.config/intro_test_runner/config.json` if `XDG_CONFIG_HOME` is unset
4. `/etc/intro_test_runner/config.json`

If none of those exist, only the assignment config is used.

Example global config:

```json
{
  "llm": {
    "host": "http://llm.example:30000/v1",
    "model": "...",
    "api-key": "..."
  },
  "function-planner": {
    "api-prefix": "https://example.com/api",
    "api-token": "..."
  }
}
```

On Gitkeeper with firejail (default), the user config directory under `$HOME` is typically unavailable; use `/etc/intro_test_runner/config.json`, `ITR_CONFIG`, or `--global-config` instead.

Function Planner
----------------

[Function Planner](https://github.com/MoravianUniversity/function-planner) is an online tool where students design a plan for their program (functions, parameters, call structure, and related documentation) before or alongside writing Python. When `function-planner` is configured in `tests.json`, this runner calls that tool's API to:

* report warnings and errors in the student's plan (`check`), and
* compare the plan to the submitted Python module (`compare`), including the student `*_test.py` when that file is part of the submission via `check-tests`.

The top-level `api-prefix` / `api-token` come from the Function Planner course settings (roster API token), and may be supplied via the assignment `tests.json` or the [global defaults](#global-defaults) file. Each module's `plan` value is the base plan id (slug) in that course. Student identity is supplied with `--student-email` (or the last git commit author in `--src`).

HTML Output
-----------

The runner supports some limited HTML output. The most notable use is when using the `check_output()` and similar functions which renders the difference in a side-by-side format with color coding. Other places include adding links to the ruff documentation and formatting the LLM output.

To enable this, use the `--html` flag (and the output needs to be viewed somewhere that supports HTML).

The HTML output still includes the plain text output as a `data-plain-text` attribute on the body tag, so that it can be extracted for use in places that only support plain text. A simple way to extract this for all HTML files is with a command like `for file in **/*.html; do pup -f "$file" -p 'body attr{data-plain-text}' > "${file%.html}.txt"; done` (using the [`pup` HTML parsing tool](https://github.com/gromgit/pup))

Using on Gitkeeper
------------------

* Cannot use snap-based installations of python or ruff due to sandboxing issues.
* Must install this library as a system-wide Python package (including the dependencies).
* To install: `python3 -m pip install git+https://github.com/MoravianUniversity/intro_test_runner.git`
* You may need to enable support for HTML output in Gitkeeper's assignment configuration.
* Use the following action.sh file (along with including the `tests.json`, `.ruff.toml`, and `_instructor_test.py` files in the testing directory):
  ```bash
  #!/bin/bash
  python3 -m intro_test_runner -s "$1" --student-email "$3" --html
  exit 0
  ```
  (`$3` is the student email from Gitkeeper; it is used when `function-planner` checks are configured. If omitted, the runner falls back to the author email of the last git commit in the submission directory.)

Publicly Exposed API
--------------------

This module provides the following functions for helping with instructor testing:

```python
def check_output(
  expected_output: str, func: Callable, *args,
  _whitespace: str = 'relaxed', **kwargs,
) -> object|None
```

Assert that the output (written to stdout) equals `expected_output` when calling `func(*args, **kwargs)`. Return the value returned by the function call.

Optionally, the `_whitespace` keyword argument can be given to determine how whitespace is compared. It can be either `'strict'` (whitespace must be exactly equal) or `'relaxed'` (the default, trailing whitespace on each line is ignored).

-----------------------------------------------------------------------------

```python
def check_output_using_user_input(
  user_input: str, expected_output: str, func: Callable, *args,
  _whitespace: str = 'relaxed', _input_placeholder: str = '<>',
  *kwargs,
) -> object|None
```

Assert that the output (written to stdout) equals `expected_output` when calling `func(*args, **kwargs)` when `user_input` is provided via stdin. This asserts that all of the user input is consumed by the function call. The `expected_output` should either include the user input as well or use a placeholder for it (default `'<>'`, it is highlighted in the output, set with `_input_placeholder` keyword argument). Return the value returned by the function call.

The optional `_whitespace` keyword argument is treated as per `check_output_equal()`.

-----------------------------------------------------------------------------

```python
def check_input(user_input: str, func: Callable, *args, _must_output_args: bool = True,
                **kwargs) -> object|None
```

Get the return value when calling `func(*args, **kwargs)` when `user_input` is provided via stdin. This asserts that all of the user input is consumed by the function call. By default you also makes sure that provided arguments show up in the output, but setting `_must_output_args=False` will not check that.

-----------------------------------------------------------------------------

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

-----------------------------------------------------------------------------

```python
@contextlib.contextmanager
def no_input(msg: str = "You are not allowed to use input(), instead use parameters")
```

Context manager that raises an assert error if `input()` is called or if `sys.stdin` is read from by any source. Has the side effect that this will suppress any `EOFError` exceptions. Used like:

```python
with no_input():
    pass # code to run that should never input() or read from stdin
```

-----------------------------------------------------------------------------

```python
@contextlib.contextmanager
def no_io_during_import()
```

Context manager that raises an assert error if `print()` is called, `sys.stdout` is written to, `input()` is called, or `sys.stdin` is read from during the import of a module. This can be used to check that a module does not have any side effects during import. Used like:

```python
with no_io_during_import():
    import my_module
```

Enabling AI Summary
-------------------

New students often struggle to understand the lint and test messages. To help with this, the `intro_test_runner` can be configured to provide an AI-generated summary of the lint and test results. This summary is generated by sending the lint and test output to an LLM and asking it to summarize the results in a way that is helpful for students.

To enable this feature, you need to set up an LLM that supports the OpenAI API. Three locally hosted LLM options are [llama.cpp](https://llama-cpp.com/), [vllm](https://vllm.ai/), and [ollama](https://ollama.com/). We have been using the the [Llama-3.1-8B-Instruct model](https://huggingface.co/unsloth/Llama-3.1-8B-Instruct-GGUF) which provides decent results and is quite fast (results in <5 seconds in our setup).

Once it is set up, you can enable it in the test runner with options in the `tests.json` file (or in the [global defaults](#global-defaults) file):

```json
{
  // other options...
  "llm": {
    "host": "http://localhost:30000/v1", // URL of the LLM's OpenAI API endpoint
    "model": "...", // optional, name of the model to specify in the API request (only required if your LLM's API endpoint serves multiple models)
    "api-key": "...", // optional; when set, sent as Authorization: Bearer <key>; when omitted, no auth header is sent
    "enabled": true, // optional, default true; set false to disable LLM summary even if host is configured globally
    "system-prompt": "...", // optional, system prompt to include at the beginning of the prompt sent to the LLM (see below)
    "addl-prompt": "", // optional, additional prompt to include at the end of the default system prompt
    "temperature": 0.1, // optional, temperature to use for the API request (default 0.1)
    "top_p": 0.9, // optional, top_p to use for the API request (default 0.9)
  }
}
```

The default `system-prompt` is:

```plain-text
You are an introductory Python programming tutor explaining {types_str} to a beginner student.

CRITICAL RULES:
1. NO FLUFF: Jump straight to the problems. Do NOT include greetings, intros, conclusions, or generic encouragement.
2. NO HALLUCINATIONS: Address ONLY problems present in the provided report. Do NOT invent problems or suggest out-of-scope concepts.
3. NO DIRECT SOLUTIONS: Do NOT provide complete corrected code blocks. Guide the student on what logic or specific lines to check.
4. ACTIONABLE FOCUS: Address high-level issues first. Group repeated or dependent errors into a single actionable feedback point. Speak directly to the student ("You...", "Your code..."). Do NOT ask follow-up questions.
```

where `{types_str}` is replaced with the types of problems in the report (e.g. "linting and instructor test problems").

The system prompt always includes the following specific guidelines (regardless of using the default or providing a custom system prompt):

```plain-text
SPECIFIC GUIDELINES:
{instructor_note}{supression_note}{either_note}
{addl_prompt}
```

where `{supression_note}` is replaced with "You may not suggest that they suppress linting messages or change linting settings." if there are linting problems, `{instructor_note}` is replaced with "The instructor tests may not be changed and are correct. " if there are instructor test problems, `{either_note}` is replaced with "Instead, guide the student on how they should fix the underlying problems in their code. " if there are either linting or instructor test problems, and `{addl_prompt}` is replaced with any additional prompt specified in the `tests.json` file.

The user prompt is (and cannot be customized):
```plain-text
[STUDENT CODE]
{student_code}

[REPORT TO EXPLAIN]
{results}

Provide a succinct, bulleted breakdown of the unique issues found above, referencing specific line numbers from the student code where applicable, and the immediate next step to fix each issue.
```

TODO
----

* Improve HTML rendering on different devices (dark vs light mode, mobile vs desktop, etc.)
* Use pytest-html and ruff + ciqar to generate more detailed HTML reports and include those in the output to students

Future: Secrets Handling
------------------------

API tokens may currently be placed inline in the global or assignment JSON. On Gitkeeper this is an obscurity tradeoff: student code runs in the same firejail environment and can read world-readable paths such as `/etc/intro_test_runner/` if it looks for them. Motivated students are uncommon for this use case today; treat tokens accordingly.

Possible improvements (not implemented):

* Separate secrets file with `secret:name` references from config, plus optional CLI-only consume-after-read for writable secrets files.
* Nested firejail around pytest that blacklists the config/secrets path after the parent process has loaded secrets into memory (needs validation inside Gitkeeper's existing firejail).
* Native secrets support in Gitkeeper itself, if/when that lands.
