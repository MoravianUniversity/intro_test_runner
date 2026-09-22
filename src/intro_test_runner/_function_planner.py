"""
Checks against the online function-planner API (plan problems and Python compare).
"""

from __future__ import annotations

from pathlib import Path
from subprocess import run
from urllib.parse import quote

import requests

from ._output import Output


def resolve_student_email(cli_email: str | None, src: str) -> str | None:
    """Return student email from CLI, or last git commit author in src, or None."""
    if cli_email:
        email = cli_email.strip()
        if email:
            return email
    try:
        result = run(
            ["git", "log", "-1", "--format=%ae"],
            cwd=src,
            capture_output=True,
            text=True,
            timeout=5,
            check=False,
        )
        if result.returncode == 0:
            email = result.stdout.strip()
            if email:
                return email
    except (OSError, TimeoutError):
        pass
    return None


def modules_needing_planner(modules: dict[str, dict]) -> list[str]:
    """Module names that have a function-planner config object."""
    return [name for name, conf in modules.items() if isinstance(conf.get("function-planner"), dict)]


def check_all_function_planners(
    modules: dict[str, dict],
    planner_settings: dict | None,
    email: str | None,
    output: Output,
) -> bool:
    """
    Run function-planner checks for every module that configures them.

    Returns True if all such checks pass (or none are configured).
    """
    names = modules_needing_planner(modules)
    if not names:
        return True

    if not isinstance(planner_settings, dict):
        output.p(
            ":-{ Function planner checks are configured, but the top-level "
            "`function-planner` settings (api-prefix / api-token) are missing."
        )
        return False

    api_prefix = (planner_settings.get("api-prefix") or "").rstrip("/")
    api_token = planner_settings.get("api-token") or ""
    if not api_prefix or not api_token:
        output.p(
            ":-{ Function planner checks are configured, but `api-prefix` and/or "
            "`api-token` are missing from the top-level `function-planner` settings."
        )
        return False

    if not email:
        output.p(
            ":-{ Function planner checks require a student email "
            "(pass `--student-email` or ensure the submission is a git repo with a commit)."
        )
        return False

    good = True
    for name in names:
        if not check_function_planner(name, modules[name]["function-planner"], api_prefix, api_token, email, output):
            good = False
        output.reset_faces()
    return good


def check_function_planner(
    module_name: str,
    config: dict,
    api_prefix: str,
    api_token: str,
    email: str,
    output: Output,
) -> bool:
    """Run plan problems and/or Python compare checks for one module."""
    plan = config.get("plan")
    if not plan or not isinstance(plan, str):
        output.p(
            f":-{{ Module `{module_name}` has `function-planner` configured but no `plan` id."
        )
        return False

    do_check = config.get("check", True)
    do_compare = config.get("compare", True)
    if not do_check and not do_compare:
        return True

    headers = {"Authorization": f"Bearer {api_token}"}
    good = True

    if do_check and not _check_plan_problems(module_name, plan, api_prefix, headers, email, output):
        good = False

    if do_compare and not _compare_plan_python(module_name, plan, api_prefix, headers, email, output):
        good = False

    return good


def _check_plan_problems(
    module_name: str,
    plan: str,
    api_prefix: str,
    headers: dict[str, str],
    email: str,
    output: Output,
) -> bool:
    url = f"{api_prefix}/plans/base/{quote(plan, safe='')}/members/{quote(email, safe='')}/problems"
    try:
        response = requests.get(url, headers=headers, timeout=30)
    except requests.RequestException as ex:
        output.p(
            f":-( Could not reach the function planner API while checking the plan "
            f"for `{module_name}`: {ex}"
        )
        return False

    if response.status_code != 200:
        output.p(_http_error_message(module_name, "plan problems", response))
        return False

    try:
        data = response.json()
    except ValueError:
        output.p(
            f":-( The function planner API returned invalid JSON while checking "
            f"the plan for `{module_name}`."
        )
        return False

    problems = data.get("problems") or {}
    items = _flatten_problems(problems)
    if not items:
        return True

    output.p(
        f":-| The function plan for `{module_name}` (plan `{plan}`) has "
        f"{len(items)} problem{'s' if len(items) != 1 else ''}:"
    )
    for severity, context, message in items:
        label = "Error" if severity == "error" else "Warning"
        if context:
            output.p(f":-| {label} ({context}): {message}")
        else:
            output.p(f":-| {label}: {message}")
    return False


def _flatten_problems(problems: dict) -> list[tuple[str, str, str]]:
    """Return list of (severity, context, message) from a PlanProblemsReport."""
    items: list[tuple[str, str, str]] = []

    for problem in problems.get("model") or []:
        items.append((problem.get("severity", "error"), "", problem.get("message", "")))

    for entry in (problems.get("functions") or {}).values():
        name = entry.get("name") or ""
        params = entry.get("params") or []
        context = _function_context(name, params)
        for problem in entry.get("problems") or []:
            items.append((problem.get("severity", "error"), context, problem.get("message", "")))

    for entry in (problems.get("functionLinks") or {}).values():
        name = entry.get("name") or ""
        params = entry.get("params") or []
        context = _function_context(name, params) or "call links"
        for problem in entry.get("problems") or []:
            items.append((problem.get("severity", "error"), context, problem.get("message", "")))

    for entry in (problems.get("calls") or {}).values():
        from_name = entry.get("fromName") or entry.get("from") or "?"
        to_name = entry.get("toName") or entry.get("to") or "?"
        context = f"call {from_name} → {to_name}"
        for problem in entry.get("problems") or []:
            items.append((problem.get("severity", "error"), context, problem.get("message", "")))

    return [(s, c, m) for s, c, m in items if m]


def _function_context(name: str, params: list) -> str:
    if not name:
        return ""
    params_str = ", ".join(str(p) for p in params)
    return f"`{name}({params_str})`"


def _compare_plan_python(
    module_name: str,
    plan: str,
    api_prefix: str,
    headers: dict[str, str],
    email: str,
    output: Output,
) -> bool:
    py_path = Path(f"{module_name}.py")
    try:
        python_code = py_path.read_text(encoding="utf-8")
    except OSError:
        output.p(f":-( Could not read `{module_name}.py` for plan comparison.")
        return False

    test_path = Path(f"{module_name}_test.py")
    tests_code = ""
    if test_path.is_file():
        try:
            tests_code = test_path.read_text(encoding="utf-8")
        except OSError:
            tests_code = ""

    url = f"{api_prefix}/plans/base/{quote(plan, safe='')}/compare-python"
    body = {
        "python": python_code,
        "tests": tests_code,
        "email": email,
        "compareTo": "student",
    }
    try:
        response = requests.post(url, headers=headers, json=body, timeout=60)
    except requests.RequestException as ex:
        output.p(
            f":-( Could not reach the function planner API while comparing the plan "
            f"to `{module_name}.py`: {ex}"
        )
        return False

    if response.status_code != 200:
        output.p(_http_error_message(module_name, "plan vs Python comparison", response))
        return False

    try:
        data = response.json()
    except ValueError:
        output.p(
            f":-( The function planner API returned invalid JSON while comparing "
            f"the plan to `{module_name}.py`."
        )
        return False

    differences = data.get("differences") or []
    if not differences:
        return True

    output.p(
        f":-| The function plan for `{module_name}` (plan `{plan}`) differs from "
        f"your Python code ({len(differences)} difference{'s' if len(differences) != 1 else ''}):"
    )
    for diff in differences:
        message = diff.get("message") or "Difference found."
        func = diff.get("function")
        if func:
            output.p(f":-| `{func}`: {message}")
        else:
            output.p(f":-| {message}")
    return False


def _http_error_message(module_name: str, action: str, response: requests.Response) -> str:
    message = ""
    try:
        payload = response.json()
        if isinstance(payload, dict):
            message = str(payload.get("message") or "").strip()
    except ValueError:
        message = ""

    status = response.status_code
    if status == 404:
        if "Member not found" in message:
            return (
                f":-{{ No function-planner account was found for this student email "
                f"while doing {action} for `{module_name}`."
            )
        if "membership" in message.lower():
            return (
                f":-{{ No function plan was found for this student "
                f"(plan membership missing) while doing {action} for `{module_name}`."
            )
        if "empty or invalid" in message.lower():
            return (
                f":-{{ The function plan appears empty or invalid "
                f"while doing {action} for `{module_name}`."
            )
        if "Base plan not found" in message:
            return (
                f":-{{ The configured function plan was not found "
                f"while doing {action} for `{module_name}`."
            )
        if message:
            return f":-{{ {message} (while doing {action} for `{module_name}`)"
        return f":-{{ Function planner {action} failed for `{module_name}` (not found)."

    if status in (401, 403):
        detail = f" ({message})" if message else ""
        return (
            f":-( Function planner authentication failed while doing {action} "
            f"for `{module_name}`{detail}."
        )

    detail = f": {message}" if message else ""
    return (
        f":-( Function planner {action} failed for `{module_name}` "
        f"(HTTP {status}){detail}."
    )
