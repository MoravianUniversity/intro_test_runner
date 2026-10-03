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


def llm_chat(
    system_prompt: str,
    user_prompt: str,
    host: str = "http://localhost:8080/v1",
    model: str = "",
    temperature: float = 0.1,
    top_p: float = 0.9,
    api_key: str | None = None,
) -> str:
    """Send a chat request to the LLM and return the response content."""
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt.strip()},
            {"role": "user", "content": user_prompt.strip()}
        ],
        "temperature": temperature,
        "top_p": top_p,
        "stream": False,
        "reasoning_format": "deepseek"
    }
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    response = requests.post(f"{host}/chat/completions", json=payload, headers=headers or None)
    response.raise_for_status()
    return response.json().get("choices", [{}])[0].get("message", {}).get("content", "")


def _remove_differences(text: str) -> str:
    """
    Removes the DIFFERENCE_NOTE and any blank or indented lines (4+ spaces) immediately following it from the given text.
    """
    dif_note_idx = text.find(DIFFERENCE_NOTE)
    while dif_note_idx != -1:
        before = text[:dif_note_idx]
        after = text[dif_note_idx + len(DIFFERENCE_NOTE):]
        # Remove blank or indented (4+ spaces) lines at the start of 'after'
        after_lines = after.splitlines()
        kept_after = []
        skipping = True
        for line in after_lines:
            if skipping and (line.strip() == "" or re.match(r"^( {4,}|\t+)", line)):
                continue
            skipping = False
            kept_after.append(line)
        text = before + ("\n" + "\n".join(kept_after) if kept_after else "")
        dif_note_idx = text.find(DIFFERENCE_NOTE)
    return text


def llm_summary(
        results: str, config: dict|None, output: Output,
        files: Sequence[str|Path]|None = None,
        problem_types: list[str] = ["lint", "test", "instructor test", "timeout", "module", "text", "plan"],
    ):
    """
    Get a summary of the test results from the LLM.
    
    If "host" is not in config, the config is None, or enabled is false, returns None.
    Otherwise, returns the LLM summary as a string. The config can also include:
        model (default empty string)
        temperature (default 0.1)
        top_p (default 0.9)
        api-key (optional; Bearer auth when set, otherwise no Authorization header)
        enabled (default true; set false to disable even when host is configured)
        addl-prompt (default empty string)
        system-prompt (default value lists off critical rules and specific guidelines)

    The problem_types parameter is a list of the types of problems that were found (e.g. "lint",
    "test", "instructor test", "timeout", "module", "text", "plan") which are used to customize
    the system prompt for the LLM.
    """
    if config is None or "host" not in config or not config.get("enabled", True):
        return
    type_map = {
        "lint": "linter results",
        "test": "student test results",
        "instructor test": "instructor test results",
        "timeout": "tests that timed out",
        "module": "assignment requirements",
        "text": "assignment written answers",
        "plan": "function plan",
    }
    types = [type_map.get(pt, pt) for pt in problem_types]
    if len(types) == 1:
        types_str = types[0]
    elif len(types) == 2:
        types_str = f"{types[0]} and {types[1]}"
    else:
        types_str = ", ".join(types[:-1]) + (", and " + types[-1])

    # Create the system prompt for the LLM
    addl_prompt = config.get("addl-prompt", "")
    has_lint = "lint" in problem_types
    has_instructor_test = "instructor test" in problem_types
    has_specific_guidelines = has_lint or has_instructor_test or addl_prompt

    supression_note = "You may not suggest that they suppress linting messages or change linting settings. " if has_lint else ""
    instructor_note = "The instructor tests may not be changed and are correct. " if has_instructor_test else ""
    if instructor_note and "Output mismatch" in results:
        instructor_note += "Expected outputs are the correct outputs. The actual outputs are produced by the student's code. The outputs can include user inputs as well (typically after a question mark or colon). "
    either_note = "Instead, guide the student on how they should fix the underlying problems in their code. " if has_lint or has_instructor_test else ""

    system_prompt = config.get(
        'system-prompt',
        "You are an introductory Python programming tutor explaining {types_str} to a beginner student.\n\n"
        "CRITICAL RULES:\n"
        "1. NO FLUFF: Jump straight to the problems. Do NOT include greetings, intros, conclusions, or generic encouragement.\n"
        "2. NO HALLUCINATIONS: Address ONLY problems present in the provided report. Do NOT invent problems or suggest out-of-scope concepts.\n"
        "3. NO DIRECT SOLUTIONS: Do NOT provide complete corrected code blocks. Guide the student on what logic or specific lines to check.\n"
        "4. ACTIONABLE FOCUS: Address high-level issues first. Group repeated or dependent errors into a single actionable feedback point. Speak directly to the student (\"You...\", \"Your code...\"). Do NOT ask follow-up questions."
    ).format(types_str=types_str)
    if has_specific_guidelines:
        system_prompt += "\n\nSPECIFIC GUIDELINES:\n"
        system_prompt += f"{instructor_note}{supression_note}{either_note}\n"
        system_prompt += f"{addl_prompt}"

    # Clean up the text for things that may confuse the LLM
    results = unicode_unbold(unicode_unitalics(results.strip().replace(BOLD_NOTE, "")))
    results = _remove_differences(results)

    # Create the user prompt for the LLM
    user_prompt = f"""[REPORT TO EXPLAIN]
{results}

Provide a succinct, bulleted breakdown of the unique issues found above, referencing specific line numbers from the student code where applicable, and the immediate next step to fix each issue."""
    if files:
        # TODO: only include files that are actually in the report
        paths = [Path(f) for f in files]
        student_code = "\n\n".join(f"[FILE: {p.name}]\n{p.read_text(encoding='utf-8').strip()}" for p in paths)
        user_prompt = f"[STUDENT CODE]\n{student_code}\n\n{user_prompt}"

    try:
        summary = llm_chat(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            host=config['host'],
            model=config.get('model', ""),
            temperature=config.get('temperature', 0.1),
            top_p=config.get('top_p', 0.9),
            api_key=config.get('api-key') or None,
        )
        output.hr()
        output.br()
        output.p("💡 The above was run through the AI tutor and the following feedback was generated:\n"
                    "(remember: this is an automated summary and may have mistakes)")
        output.br()
        output.md(summary)
    except requests.RequestException as ex:
        output.p("⁉️ Failed to get LLM summary. Please check your LLM configuration and ensure your LLM is running and accessible.")
        output.p(f"Error details: `{ex}`")
