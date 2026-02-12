"""
External program integrations, such as linters and test runners.
"""

from collections.abc import Sequence
from pathlib import Path
import random
import re
import subprocess

from ._faces import BAD
from ._utils import name


def lint(files: Sequence[str|Path]) -> bool:
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
            r'^(def\s+main\s*\([^)]*\)\s*(->\s*None\s*)?:.*)(?!\n    """)',
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


def test(files: Sequence[str|Path], instructor: bool = False) -> bool:
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
