import os
import subprocess
import time

# Base directory to scan
BASE_DIR = "src"

# Templates for issues
# Each template has a title format, body format, label list, and difficulty
TEMPLATES = [
    {
        "title": "Documentation: Enhance docstrings for `{filename}`",
        "body": "The module `{path}` currently lacks comprehensive docstrings. \n\n**Task:**\n- Add module-level docstrings.\n- Add function/class-level docstrings following Google/NumPy style guidelines.\n- Ensure all parameters and return types are documented.",
        "labels": ["documentation", "good first issue", "difficulty: easy"]
    },
    {
        "title": "Typing: Add type hints to `{filename}`",
        "body": "To improve code reliability and developer experience, we need full type annotation coverage.\n\n**Task:**\n- Add Python type hints to `{path}`.\n- Run `mypy` to verify correctness.\n- Ensure complex types are properly imported from `typing`.",
        "labels": ["enhancement", "typing", "difficulty: easy"]
    },
    {
        "title": "Testing: Implement unit tests for `{filename}`",
        "body": "We need to ensure high reliability for `{path}`.\n\n**Task:**\n- Create a test file in `tests/` mirroring the structure.\n- Implement unit tests using `pytest`.\n- Aim for at least 80% code coverage for this module.",
        "labels": ["testing", "help wanted", "difficulty: medium"]
    },
    {
        "title": "Refactor: Improve error handling in `{filename}`",
        "body": "Review the error handling logic in `{path}`.\n\n**Task:**\n- Ensure specific exceptions are caught instead of generic `Exception`.\n- Verify that errors are logged meaningfully.\n- suggest improvements for edge cases.",
        "labels": ["refactor", "quality", "difficulty: medium"]
    },
    {
        "title": "Optimization: Performance Review for `{filename}`",
        "body": "Analyze `{path}` for potential performance bottlenecks.\n\n**Task:**\n- identifying loops or I/O operations that could be optimized.\n- Consider async/await usage if applicable.\n- Benchmark before and after changes if optimizations are applied.",
        "labels": ["optimization", "performance", "difficulty: hard"]
    }
]

def get_python_files(start_dir):
    py_files = []
    for root, dirs, files in os.walk(start_dir):
        for file in files:
            if file.endswith(".py") and file != "__init__.py":
                rel_path = os.path.join(root, file)
                py_files.append(rel_path)
    return py_files

def create_issue(title, body, labels):
    repo = "sr-857/AstraGuard-AI-Apertre-3.0"
    cmd = [
        "gh", "issue", "create",
    create_issue('Smoke Test Permanent Fix', 'Body content', ['documentation'])
