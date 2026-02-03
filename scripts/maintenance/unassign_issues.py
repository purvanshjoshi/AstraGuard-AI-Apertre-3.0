import subprocess
import json
import time

def get_assigned_issue_numbers(repo, assignee):
    cmd = [
        "gh", "issue", "list",
        "--repo", repo,
        "--limit", "1000",
        "--assignee", assignee,
        "--json", "number",
        "--state", "all"
    ]
    try:
        result = subprocess.run(cmd, input="", capture_output=True, text=True, check=True)
        issues = json.loads(result.stdout)
        return [issue["number"] for issue in issues]
    except Exception as e:
        print(f"Error fetching assigned issues: {e}")
        return []

def unassign_issues(repo, issue_numbers, assignee):
    for number in issue_numbers:
        print(f"Removing assignment from issue #{number}...")
        cmd = [
            "gh", "issue", "edit", str(number),
            "--repo", repo,
            "--remove-assignee", assignee
        ]
        try:
            subprocess.run(cmd, input="", capture_output=True, text=True, check=True)
            print(f"Successfully unassigned #{number}")
            time.sleep(0.1) # Throttle
        except subprocess.CalledProcessError as e:
            print(f"Failed to unassign #{number}: {e.stderr}")

def main():
    repo = "sr-857/AstraGuard-AI-Apertre-3.0"
    assignee = "sr-857"
    
    print(f"Fetching issues assigned to {assignee} in {repo}...")
    issue_numbers = get_assigned_issue_numbers(repo, assignee)
    print(f"Found {len(issue_numbers)} assigned issues.")
    
    if not issue_numbers:
        print("No assigned issues found.")
        return

    unassign_issues(repo, issue_numbers, assignee)
    print("Unassignment complete.")

if __name__ == "__main__":
    main()
