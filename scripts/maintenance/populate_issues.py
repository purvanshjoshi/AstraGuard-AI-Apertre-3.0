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
        "labels": ["documentation", "good first issue", "difficulty: easy", "apertre3.0"]
    },
    {
        "title": "Typing: Add type hints to `{filename}`",
        "body": "To improve code reliability and developer experience, we need full type annotation coverage.\n\n**Task:**\n- Add Python type hints to `{path}`.\n- Run `mypy` to verify correctness.\n- Ensure complex types are properly imported from `typing`.",
        "labels": ["enhancement", "typing", "difficulty: easy", "apertre3.0"]
    },
    {
        "title": "Testing: Implement unit tests for `{filename}`",
        "body": "We need to ensure high reliability for `{path}`.\n\n**Task:**\n- Create a test file in `tests/` mirroring the structure.\n- Implement unit tests using `pytest`.\n- Aim for at least 80% code coverage for this module.",
        "labels": ["testing", "help wanted", "difficulty: medium", "apertre3.0"]
    },
    {
        "title": "Refactor: Improve error handling in `{filename}`",
        "body": "Review the error handling logic in `{path}`.\n\n**Task:**\n- Ensure specific exceptions are caught instead of generic `Exception`.\n- Verify that errors are logged meaningfully.\n- suggest improvements for edge cases.",
        "labels": ["refactor", "quality", "difficulty: medium", "apertre3.0"]
    },
    {
        "title": "Optimization: Performance Review for `{filename}`",
        "body": "Analyze `{path}` for potential performance bottlenecks.\n\n**Task:**\n- identifying loops or I/O operations that could be optimized.\n- Consider async/await usage if applicable.\n- Benchmark before and after changes if optimizations are applied.",
        "labels": ["optimization", "performance", "difficulty: hard", "apertre3.0"]

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
        "--title", title,
        "--body", body,
        "--repo", repo
    ]
    for label in labels:
        cmd.extend(["--label", label])
    
    try:
        print(f"Creating issue: {title}")
        # Using input="" to ensure it doesn't wait for stdin
        result = subprocess.run(cmd, input="", capture_output=True, text=True, check=True)
        print(f"Success: {result.stdout.strip()}")
        time.sleep(0.5) # Slight rate limiting prevention
    except subprocess.CalledProcessError as e:
        print(f"Error creating issue '{title}':\nSTDOUT: {e.stdout}\nSTDERR: {e.stderr}")
    except FileNotFoundError:
        print("Error: 'gh' CLI not found. Please install GitHub CLI.")
        exit(1)

def main():
    print("Scanning for Python files...")
    files = get_python_files(BASE_DIR)
    print(f"Found {len(files)} Python files.")
    
    # confirm = input(f"This will create approx {len(files) * len(TEMPLATES)} issues. Proceed? (y/n): ")
    # if confirm.lower() != 'y':
    #     print("Aborted.")
    #     return
    print(f"Proceeding to create approx {len(files) * len(TEMPLATES)} issues...")

    count = 0
    for file_path in files:
        filename = os.path.basename(file_path)
        for tmpl in TEMPLATES:
            title = tmpl["title"].format(filename=filename, path=file_path)
            body = tmpl["body"].format(filename=filename, path=file_path)
            labels = tmpl["labels"]
            
            create_issue(title, body, labels)
            count += 1
            if count >= 100:
                print("Reached 100 issues limit. Stopping.")
                return

if __name__ == "__main__":
    main()
