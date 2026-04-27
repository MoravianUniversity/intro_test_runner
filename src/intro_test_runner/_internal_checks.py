"""
Internal checks for student submissions.
"""

from collections.abc import Callable, Sequence
from pathlib import Path
import ast
import random
import shutil

from ._faces import BAD, MED_BAD, REALLY_BAD
from ._utils import ast_eq, name


def copy_files(src: str, paths: Sequence[str]) -> bool:
    good = True
    for path_str in paths:
        full_path = Path(src).joinpath(path_str).resolve()
        path = Path(path_str).resolve()
        if not full_path.exists() or not full_path.is_file():
            face = random.choice(REALLY_BAD)
            print(f"{face} Your submission does not include '{path_str}' at all.")
            good = False
        elif full_path != path:
            shutil.copy(full_path, path)
    return good


def check_text_file(path_str: str, config: dict[str, int|float]) -> bool:
    orig_lines = config.get("original-lines", 0)
    min_lines = config.get("min-lines", 0)
    max_lines = config.get("max-lines", float('inf'))

    # Copy the path to be relative to the source directory
    path = Path(path_str).resolve()
    face = random.choice(MED_BAD)
    try:
        lines = path.read_text(encoding='utf-8').strip().splitlines()
        line_count = len(lines)

        if line_count == orig_lines:
            print(f"{face} Your submission seems to have an unmodified '{path_str}'.")
            return False
        elif line_count < min_lines:
            print(f"{face} Your submission seems to have an incomplete '{path_str}'.")
            return False
        elif line_count > max_lines:
            print(f"{face} Your submission has a ridiculous number of lines in '{path_str}'.")
            return False
    except FileNotFoundError:
        print(f"{face} Your submission does not include '{path_str}' at all.")
        return False
    return True


GOOD_AST_NODES = (
    ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import,
    ast.ImportFrom, ast.Assign, ast.AnnAssign,
)
if hasattr(ast, "TypeAlias"):
    GOOD_AST_NODES += (ast.TypeAlias,)

def _is_docstring(node: ast.AST) -> bool:
    return isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)


def _get_code_ast(file: Path, face: str|None = None) -> tuple[ast.Module|None, bool]:
    if face is None:
        face = random.choice(BAD)
    try:
        good = True
        code = ast.parse(file.read_text(encoding='utf-8'))
        body = code.body

        # Check for misplaced docstrings
        for i, child in enumerate(body):
            if _is_docstring(child):
                if i == 0:
                    continue # Module docstring is fine
                elif _is_docstring(body[i-1]):
                    print(f"{face} Multiple consecutive docstrings found in '{name(file)}' as lines {body[i-1].lineno} {child.lineno}. Combine them. Only the first one is considered a module docstring.")
                    good = False
                elif isinstance(body[i-1], (ast.Import, ast.ImportFrom)):
                    print(f"{face} Misplaced docstring found in '{name(file)}' at line {child.lineno}. Move it above the imports to be a module docstring.")
                    good = False
                else:
                    print(f"{face} Misplaced docstring found in '{name(file)}' at line {child.lineno}.")
                    good = False

        body = [child for child in body if not _is_docstring(child)]

        # Make sure the code is "clean":
        #   no top-level statements other than function definitions/imports/assignments and a final if
        #   the final if is only an if __name__ == "__main__": block and only contains a call to main()
        for i, child in enumerate(body):
            if isinstance(child, GOOD_AST_NODES):
                continue

            # Final statement must be if __name__ == "__main__":
            if not (i == len(body) - 1 and
                    isinstance(child, ast.If) and
                    isinstance(child.test, ast.Compare) and
                    isinstance(child.test.left, ast.Name) and
                    child.test.left.id == "__name__" and
                    len(child.test.ops) == 1 and
                    isinstance(child.test.ops[0], ast.Eq) and
                    len(child.test.comparators) == 1 and
                    isinstance(child.test.comparators[0], ast.Constant) and
                    child.test.comparators[0].value == "__main__"):
                print(f"{face} Top-level code found in '{name(file)}' which is not allowed.")
                print(f"   Instructor diagnosis info: {i}/{len(body)} {ast.dump(child)}")
                print()
                return code, False
            # Body of if must only be a call to main() or pytest.main()
            if len(child.body) != 1 or not isinstance(child.body[0], ast.Expr) or not isinstance(
                    child.body[0].value, ast.Call):
                print(f"{face} Top-level code found in '{name(file)}' which is not allowed.")
                print(f"   Instructor diagnosis info: {len(body)} {ast.dump(child)}")
                print()
                return code, False
            call = child.body[0].value
            if not ((isinstance(call.func, ast.Name) and call.func.id == "main") or
                    (isinstance(call.func, ast.Attribute) and
                        isinstance(call.func.value, ast.Name) and
                        call.func.value.id == "pytest" and
                        call.func.attr == "main")):
                print(f"{face} Top-level code found in '{name(file)}' which is not allowed.")
                print(f"   Instructor diagnosis info: call {ast.dump(call)}")
                print()
                return code, False

        return code, good
    except SyntaxError as e:
        print(f"{face} Your submission has a syntax error in '{name(file)}': {e}")
        return None, False


def _get_func_defs(code: ast.Module) -> list[ast.FunctionDef]:
    return [child for child in code.body if isinstance(child, ast.FunctionDef)]


def _check_func_count(
        all_names: Sequence[str],
        file: Path|str, expected_count: int,
        more_allowed: bool = False, face: str|None = None,
        typ: str = "function",
) -> bool:
    good = True
    if face is None:
        face = random.choice(BAD)
    names = list(set(all_names))
    if len(names) != len(all_names):
        print(f"{face} You have duplicate {typ} names in '{name(file)}'.")
        good = False
    if more_allowed and len(names) < expected_count:
        print(f"{face} You must have at least {expected_count} {typ}s in '{name(file)}'. "
              f"You have {len(names)}.")
        good = False
    elif not more_allowed and len(names) != expected_count:
        print(f"{face} You must have exactly {expected_count} {typ}s in '{name(file)}'. "
              f"You have {len(names)}.")
        good = False
    return good


def _check_funcs(
        file: Path, funcs: Sequence[ast.FunctionDef], req_funcs: Sequence[str],
        min_doc_length: int|dict[str, int] = 0,
        addl_funcs_allowed: bool = False, face: str|None = None,
) -> bool:
    if face is None:
        face = random.choice(BAD)
    func_names = [func.name for func in funcs]
    good = _check_func_count(func_names, file, len(req_funcs), addl_funcs_allowed, face, "function")

    names = list(set(func_names))
    given_exp_names = [name for name in req_funcs if not name.startswith("_")]
    for exp_name in given_exp_names:
        if exp_name not in names:
            print(f"{face} You are missing the '{exp_name}' function in '{name(file)}'.")
            good = False

    for func in funcs:
        if func.name == "main" or func.name.startswith("test_") or func.name.startswith("_"):
            continue
        if isinstance(min_doc_length, dict):
            exp_len = min_doc_length.get(func.name, min_doc_length.get("_default", 16))
        else:
            exp_len = min_doc_length
        doc = ast.get_docstring(func)
        doc_len = 0 if doc is None else len(doc)
        if doc_len < exp_len:
            print(f"{face} The '{name(file)}.{func.name}' function docstring "
                  "should be more descriptive...")
            good = False

    return good


def _check_for_unused_funcs(
        file: Path,
        code: ast.Module,
        face: str|None = None,
) -> bool:
    if face is None:
        face = random.choice(BAD)
    func_calls = {node.func.id for node in ast.walk(code)
                  if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    good = True
    for func in _get_func_defs(code):
        if func.name not in func_calls:
            print(f"{face} The '{func.name}' function in '{name(file)}' is not called anywhere.")
            good = False
    return good


def _is_forwarding_call(call: ast.expr, func: ast.FunctionDef) -> bool:
    if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name):
        return False
    args = {arg.id for arg in call.args if isinstance(arg, ast.Name)}
    if len(args) != len(call.args):  # not just forwarding arguments
        return False
    params = {param.arg for param in func.args.args}
    return args <= params


def _is_useless_func(func: ast.FunctionDef) -> bool:
    # A useless function is one that follows one of the following patterns (not counting docstrings):
    #  - just a pass
    #  - just a return of a constant value
    #  - just a call to another function with the same (or less) arguments
    #  - just a call to another function with the same (or less) arguments and returning its result
    body = func.body
    # Remove all bare strings and passes
    body = [stmt for stmt in body if not _is_docstring(stmt) and not isinstance(stmt, ast.Pass)]
    if len(body) == 0:
        return True
    if len(body) == 1:
        stmt = body[0]
        if isinstance(stmt, ast.Return) and isinstance(stmt.value, ast.Constant):
            return True
        if isinstance(stmt, ast.Expr) and _is_forwarding_call(stmt.value, func):
            return True
        if isinstance(stmt, ast.Return) and (stmt.value is None or _is_forwarding_call(stmt.value, func)):
            return True
    return False


def _check_for_useless_funcs(
        file: Path,
        funcs: Sequence[ast.FunctionDef],
        face: str|None = None,
) -> bool:
    if face is None:
        face = random.choice(BAD)
    good = True
    for func in funcs:
        if _is_useless_func(func):
            print(f"{face} The '{func.name}' function in '{name(file)}' does not seem to do anything.")
            good = False
    return good


def _check_test_funcs(
        test_file: Path, req_funcs: dict[str, int],
        addl_tests_allowed: bool = False, face: str|None = None
) -> bool:
    if face is None:
        face = random.choice(BAD)
    code, good = _get_code_ast(test_file, face)
    if code is None:
        return False
    tests = [test for test in _get_func_defs(code) if test.name.startswith("test_")]

    # Check that there are enough test functions
    test_names = [test.name for test in tests]
    good = _check_func_count(test_names, test_file, len(req_funcs),
                             addl_tests_allowed, face, "test function") and good

    # Check that all expected test functions are present
    names = list(set(test_names))
    given_exp_names = [f"test_{n}" for n in req_funcs if not n.startswith("_")]
    for exp_name in given_exp_names:
        if exp_name not in names:
            print(f"{face} You are missing the '{exp_name}' test function in '{name(test_file)}'.")
            good = False

    # Check that there are enough questions in each test
    questions: dict[str, list[ast.AST]] = {
        test.name: [question for question in test.body if isinstance(question, ast.Assert)]
        for test in tests
    }
    counts = {
        n: len(questions) for n, questions in questions.items()
    }
    for n in names:
        count = counts.get(n, 0)
        exp_count = req_funcs.get(n[5:], 0)
        # TODO: if n[5:] is not in req_funcs, look for a close match and use its count
        if count < exp_count:
            print(f"{face} {n} must have at least {exp_count} test 'questions'. "
                  f"You have {count} test 'questions'.")
            good = False

    # Check for duplicate questions
    # TODO: this mis-detects when the code uses an intermediate variable and the result is the same
    for n in names:
        func_questions = questions.get(n, [])
        for i, a in enumerate(func_questions):
            for b in func_questions[i+1:]:
                if ast_eq(a, b):
                    end = "."
                    if isinstance(a, ast.expr) and isinstance(b, ast.expr):
                        end = f" on lines {a.lineno} and {b.lineno}."
                    print(f"{face} You have duplicate test questions in your {n} test function" +
                          end)
                    good = False

    # TODO: Check that function calls have their return values used in the assert statement

    return good



def check_module(name: str, config: dict) -> bool:
    face = random.choice(BAD)
    exp_funcs: list[str] | dict[str, int] = config.get("expected-functions", [])
    addl_funcs_allowed = config.get("addl-funcs-allowed", False)
    addl_tests_allowed = config.get("addl-tests-allowed", False)
    min_module_doc_length = config.get("min-module-doc-length", 25)
    min_func_doc_length = config.get("min-func-doc-length", 20)
    check_unused_funcs = config.get("check-unused-funcs", True)
    check_useless_funcs = config.get("check-useless-funcs", True)

    path = Path(f"{name}.py").resolve()
    test_path = Path(f"{name}_test.py").resolve()

    # Check that the module has a module-level docstring
    code, good = _get_code_ast(path, face)
    if code is None:
        return False
    module_doc = ast.get_docstring(code)
    module_doc_len = 0 if module_doc is None else len(module_doc)
    if module_doc_len < min_module_doc_length:
        if module_doc_len == 0:
            print(f"{face} The '{name}' module should have a docstring at the top.")
        else:
            print(f"{face} The '{name}' module docstring should be more descriptive...")
        good = False

    # Check that the module has the expected functions
    exp_func_names = exp_funcs if isinstance(exp_funcs, list) else list(exp_funcs.keys())
    funcs = _get_func_defs(code)
    if not _check_funcs(path, funcs, exp_func_names, min_func_doc_length, addl_funcs_allowed, face):
        good = False

    # Check for any unused and useless functions
    if check_unused_funcs and not _check_for_unused_funcs(path, code, face):
        good = False
    if check_useless_funcs and not _check_for_useless_funcs(path, funcs, face):
        good = False

    # Check that there are the right number of tests if required
    if check_tests(config) and isinstance(exp_funcs, dict):
        testable_funcs = {f: n for f, n in exp_funcs.items() if n > 0}
        if not _check_test_funcs(test_path, testable_funcs, addl_tests_allowed, face):
            good = False

    return good


def check_all(all_configs: dict[str, dict],
               check: Callable[[str, dict], bool]) -> bool:
    good = True
    for path_str, config in all_configs.items():
        if not check(path_str, config):
            good = False
    return good


def check_tests(config: dict) -> bool:
    check_tests = config.get("check-tests")
    if check_tests is not None:
        return check_tests
    return not isinstance(config.get("expected-functions"), list)
