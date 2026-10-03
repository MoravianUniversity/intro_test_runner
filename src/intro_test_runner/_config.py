"""
Load and merge assignment tests.json with optional global defaults.
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path


def find_global_config(cli_path: str | None = None) -> Path | None:
    """
    Return the first existing global config path, or None.

    Order: --global-config, ITR_CONFIG, XDG/user config, /etc/intro_test_runner/config.json.
    """
    candidates: list[Path] = []
    if cli_path:
        candidates.append(Path(cli_path).expanduser())
    env_path = os.environ.get("ITR_CONFIG")
    if env_path:
        candidates.append(Path(env_path).expanduser())
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        candidates.append(Path(xdg) / "intro_test_runner" / "config.json")
    else:
        candidates.append(Path.home() / ".config" / "intro_test_runner" / "config.json")
    candidates.append(Path("/etc/intro_test_runner/config.json"))

    for path in candidates:
        if path.is_file():
            return path
    return None


def deep_merge(base: dict, override: dict) -> dict:
    """
    Deep-merge override onto a copy of base. Nested dicts are merged; other
    values in override replace base. Assignment (override) wins on conflicts.
    """
    result = deepcopy(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = deepcopy(value)
    return result


def load_merged_config(assignment_path: str | Path, global_cli_path: str | None = None) -> dict:
    """
    Load assignment JSON and deep-merge any discovered global defaults underneath
    it (assignment wins).
    """
    with open(assignment_path, encoding="utf-8") as f:
        assignment = json.load(f)
    if not isinstance(assignment, dict):
        msg = f"Config file must contain a JSON object: {assignment_path}"
        raise ValueError(msg)

    global_path = find_global_config(global_cli_path)
    if global_path is None:
        return assignment

    with open(global_path, encoding="utf-8") as f:
        global_config = json.load(f)
    if not isinstance(global_config, dict):
        msg = f"Global config file must contain a JSON object: {global_path}"
        raise ValueError(msg)

    return deep_merge(global_config, assignment)
