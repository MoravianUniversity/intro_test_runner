When using with gitkeeper:
- Cannot use snap-based installations of python or ruff due to sandboxing issues.
- Must install system-wide Python package pytest.
- To install: `python3 -m pip install git+https://github.com/MoravianUniversity/intro_test_runner.git`
- Use the following action.sh file:
  ```bash
  #!/bin/bash
  python3 -m intro_test_runner -s "$1"
  exit 0
  ```
