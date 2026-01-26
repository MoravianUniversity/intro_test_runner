When using with gitkeeper:
- May need to have an assignment.cfg file containing:
  ```ini
  [tests]
  env = host
  ```
- Cannot use snap-based installations of python or ruff due to sandboxing issues. That may
  alleviate the assignment.cfg requirement as well.
- Must install system-wide Python package pytest.
- To install: `python3 -m pip install git+https://github.com/MoravianUniversity/intro_test_runner.git`
- Use the following action.sh file:
  ```bash
  #!/bin/bash
  python3 -m intro_test_runner -s "$1"
  exit 0
  ```


TODO
----
- Break into multiple files.
- Make a pytest plugin from conftest.py file (which won't work when this is turned into a package).
