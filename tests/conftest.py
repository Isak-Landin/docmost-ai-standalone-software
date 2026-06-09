import os
import sys

# Make the repo root importable so `from app.query... import ...` works when pytest is
# invoked from anywhere. The repo has no installable package; this is the test entry point.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)
