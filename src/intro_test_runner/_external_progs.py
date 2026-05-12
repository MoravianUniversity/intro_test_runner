"""
External program integrations, such as linters and test runners.
"""

from collections.abc import Sequence
import os
from pathlib import Path
import re
import subprocess
import requests

from ._output import Output
from ._utils import name, unicode_unbold, unicode_unitalics
from ._check_io import BOLD_NOTE, DIFFERENCE_NOTE


def lint(files: Sequence[str|Path], output: Output, html_output: bool = False) -> bool:
    """Run ruff on the given files. Returns True if linting passed, False otherwise."""
    ruff_cmd = ["ruff", "check", "-n", "-q", "--color=always"]
    if Path(".ruff.toml").is_file():
        ruff_cmd += ["--config", ".ruff.toml"]
    elif Path("ruff.toml").is_file():
        ruff_cmd += ["--config", "ruff.toml"]
    ruff_cmd += [str(f) for f in files]

    # Prevent main() from needing documentation by adding noqa: D103
    # only add it if it doesn't contain a """ immediately inside of it
    for file in files:
        path = Path(file)
        if not path.is_file():
            continue
        content = path.read_text(encoding='utf-8')
        new_content = re.sub(
            r'^(def\s+main\s*\([^)]*\)\s*(->\s*None\s*)?:.*)(?!\n\s+""")',
            r'\1  # noqa: D103',
            content, flags=re.MULTILINE,
        )
        if new_content != content:
            path.write_text(new_content, encoding='utf-8')

    try:
        result = subprocess.run(ruff_cmd, capture_output=True, text=True, check=False)  # noqa: S603
        if result.returncode != 0:
            msg = ":-{ Your submission has style issues. Please fix them and try again."
            if html_output:
                msg += " The links tell you more about the errors and how to fix them."
            output.p(msg)
            out = result.stdout.strip()
            err = result.stderr.strip()
            output.pre_terminal(out, __ruff_linkify)
            output.pre_terminal(err, __ruff_linkify)
            return False
    except FileNotFoundError:
        output.p("⁉️ `ruff` is not installed or not found in `PATH`. "
                 "The instructor must install ruff to enable linting checks.")
        return False
    return True


def __ruff_linkify(text: str) -> str:
    """Convert ruff output error codes into links to the relevant webpage."""
    # color_code = r'\x1b\[(?:[0-9;]*)?m'  # matches ANSI color codes like \x1b[31m or \x1b[0m
    color_code = r'<span style="[^"]*">|</span>'  # matches HTML span tags with color styles like <span style="color:red">
    return re.sub(rf'^(\s+\d+(?:{color_code})?:(?:{color_code})?\d+\s+)({color_code})?([A-Z]+\d+)({color_code})?(\s)',
                  r'\1\2<a href="https://docs.astral.sh/ruff/rules/\3" title="Ruff Rule \3" style="color:inherit;text-decoration:underline currentColor;">\3</a>\4\5',
                  text, flags=re.MULTILINE)


def test(files: Sequence[str|Path], output: Output, instructor: bool = False, html_output: bool = False) -> bool:  # noqa: PT028
    """
    Run pytest on the given files. If instructor is True, the files are considered instructor tests.
    If html_output is True, the output will be in HTML format.
    """
    if len(files) == 0:
        return True

    result = subprocess.run(  # noqa: S603
        ["python3", "-m", "pytest", "--no-header", "--tb=short", "--color=yes", "--cache-clear"] +
        [name(file) for file in files],
        env=os.environ | {"ITR_HTML_OUTPUT": str(html_output)},
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        if instructor:
            output.p(":-{ Your code failed the instructor tests. "
                     "These tests are designed to catch common mistakes.")
        else:
            output.p(":-{ Your own tests failed on your own code. "
                     "Make sure your own code passes your own tests!")
        output.pre_terminal(result.stdout)
        output.pre_terminal(result.stderr)
        return False
    return True


def llm_chat(prompt: str, host: str = "http://localhost:8080/v1", model: str = "") -> str:
    """Send a chat request to the LLM and return the response content."""
    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "stream": False,
        "reasoning_format": "deepseek"
    }
    response = requests.post(f"{host}/chat/completions", json=payload)
    response.raise_for_status()
    return response.json().get("choices", [{}])[0].get("message", {}).get("content", "")


def llm_summary(
        instructor_results: str, config: dict[str, str]|None, output: Output,
        problem_types: list[str] = ["lint", "test", "instructor test", "timeout", "module", "text"],
    ):
    """
    Get a summary of the instructor test results from the LLM.
    
    If "host" is not in config, returns None. Otherwise, returns the LLM summary as a string.
    The config can also include "model" and "prompt-header" if necessary.

    The problem_types parameter is a list of the types of problems that were found (e.g. "lint",
    "test", "instructor test", "timeout", "module", "text") which are used to customize the prompt
    for the LLM.
    """
    if config is None or "host" not in config:
        return
    llm_host = config['host']
    llm_model = config.get('model', "")
    type_map = {
        "lint": "a linter",
        "test": "student tests",
        "instructor test": "instructor tests",
        "timeout": "tests that timed out",
        "module": "assignment requirements",
        "text": "assignment written answers"
    }
    types = [type_map.get(pt, pt) for pt in problem_types]
    types_str = ", ".join(types[:-1]) + (", and " if len(types) > 1 else "") + types[-1]

    supession_note = "You may not suggest that they suppress linting messages or change linting settings." if "lint" in problem_types else ""
    instructor_note = "The instructor tests may not be changed and are correct. " if "instructor test" in problem_types else ""
    either_note = "Instead, guide the student on how they should fix the underlying problems in their code. " if "lint" in problem_types or "instructor test" in problem_types else ""

    addl_prompt = config.get("addl-prompt", "")
    prompt_header = config.get(
        'prompt-header',
        "You are tutor explaining the results of {types_str} to a student for their Python code "
        "assignment. Address the student but don't ask for follow up. The output doesn't "
        "need an intro, conclusion, or general advice. Be succinct. Address the highest-level "
        "problems first. It is okay to ignore specific problems, especially if they are "
        "repeated or dependent on other issues. Give an overall summary of each unique problem in "
        "the report with the next steps and how to fix it (for example which line of code to look "
        "at and/or what to do). Combine repeats. Do not mention problems that are not in the "
        "report. Do not give any advice that is not directly related to the problems in the report. "
        "{supession_note}{instructor_note}{either_note}{addl_prompt}Here is the report the student received:"
    ).format(
        types_str=types_str,
        supession_note=supession_note,
        instructor_note=instructor_note,
        either_note=either_note,
        addl_prompt=addl_prompt
    )

    # Clean up the text for things that may confuse the LLM
    instructor_results = unicode_unbold(unicode_unitalics(instructor_results.strip().replace(BOLD_NOTE, "")))
    instructor_results = instructor_results.split(DIFFERENCE_NOTE)[0]  # remove the difference chunk

    prompt = f"{prompt_header}\n\n{instructor_results}\n"
    try:
        summary = llm_chat(prompt, host=llm_host, model=llm_model)
        output.hr()
        output.br()
        output.p("💡 The above was run through the AI tutor and the following feedback was generated:\n"
                    "(remember: this is an automated summary and may have mistakes)")
        output.br()
        output.md(summary)
    except requests.RequestException as ex:
        output.p("⁉️ Failed to get LLM summary. Please check your LLM configuration and ensure your LLM is running and accessible.")
        output.p(f"Error details: `{ex}`")
