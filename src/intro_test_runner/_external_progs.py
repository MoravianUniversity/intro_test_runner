"""
External program integrations, such as linters and test runners.
"""

from collections.abc import Sequence
from pathlib import Path
import random
import re
import subprocess
import requests

from ._faces import BAD
from ._utils import name


def lint(files: Sequence[str|Path]) -> bool:
    """Run ruff on the given files. Returns True if linting passed, False otherwise."""
    ruff_cmd = ["ruff", "check", "-n", "-q"]
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
            face = random.choice(BAD)
            print(f"{face} Your submission has style issues. Please fix them and try again.")
            print(result.stdout.strip())
            print(result.stderr.strip())
            return False
    except FileNotFoundError:
        print("⁉️ 'ruff' is not installed or not found in PATH. "
              "The instructor must install ruff to enable linting checks.")
        return False
    return True


def test(files: Sequence[str|Path], instructor: bool = False) -> bool:  # noqa: PT028
    """Run pytest on the given files. If instructor is True, the files are considered instructor tests."""
    if len(files) == 0:
        return True

    result = subprocess.run(  # noqa: S603
        ["python3", "-m", "pytest", "--no-header", "--tb=short", "--color=no", "--cache-clear"] +
        [name(file) for file in files],
        capture_output=True, text=True, check=False,
    )
    if result.returncode != 0:
        face = random.choice(BAD)
        if instructor:
            print(f"{face} Your code failed the instructor tests. "
                  "These tests are designed to catch common mistakes.")
        else:
            print(f"{face} Your own tests failed on your own code. "
                    "Make sure your own code passes your own tests!")
        print(result.stdout.strip())
        print(result.stderr.strip())
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


def llm_summary(instructor_results: str, config: dict) -> str|None:
    """Get a summary of the instructor test results from the LLM."""
    if "llm-host" not in config:
        return None
    llm_host = config['llm-host']
    llm_model = config.get('llm-model', "")
    prompt_header = config.get('llm-prompt-header', "You are tutor explaining the results of a linter and automated tests to a student for their Python code. Address the student but don't ask for follow up. The output doesn't need an intro, conclusion, or general advice. Be succinct. Give an overall summary of each unique problem and state the next steps and how to fix (for example which line of code to look at and/or what to do). Combine repeats. You may not suggest that they suppress linting messages or change linting settings. Instead, guide the student on how they should fix the underlying problems. The instructor tests may not be changed and are correct; thus the suggestions should be to fix their code. Here is the results the student received:")
    prompt = f"{prompt_header}\n\n{instructor_results}\n"
    try:
        return llm_chat(prompt, host=llm_host, model=llm_model)
    except requests.RequestException as ex:
        print("⁉️ Failed to get LLM summary. Please check your LLM configuration and ensure your LLM is running and accessible.")
        print(f"Error details: {ex}")
        return None
