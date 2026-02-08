import subprocess
import json
import time

def get_issues_by_label(repo, label):
    cmd = [
        "gh", "issue", "list",
        "--repo", repo,
        "--limit", "1000",
        "--label", label,
        "--json", "number",
        "--state", "open"
    ]
    try:
        result = subprocess.run(cmd, input="", capture_output=True, text=True, check=True)
        issues = json.loads(result.stdout)
        return [issue["number"] for issue in issues]
    except Exception as e:
        print(f"Error fetching issues for label '{label}': {e}")
        return []

def assign_issues(repo, issue_numbers, assignee):
    for number in issue_numbers:
        print(f"Assigning issue #{number} to {assignee}...")
        cmd = [
            "gh", "issue", "edit", str(number),
            "--repo", repo,
            "--add-assignee", assignee
        ]
        try:
            subprocess.run(cmd, input="", capture_output=True, text=True, check=True)
            print(f"Successfully assigned #{number}")
            time.sleep(0.2) # Throttle to avoid rate limits
        except subprocess.CalledProcessError as e:
            print(f"Failed to assign #{number}: {e.stderr}")

def main():
    repo = "sr-857/AstraGuard-AI-Apertre-3.0"
    assignee = "sr-857" # Assuming assignment to the owner/current user
    
    difficulties = ["difficulty: easy", "difficulty: medium", "difficulty: hard"]
    
    for diff in difficulties:
        print(f"\nProcessing issues with label: {diff}")
        issue_numbers = get_issues_by_label(repo, diff)
        print(f"Found {len(issue_numbers)} issues.")
        
        if issue_numbers:
            assign_issues(repo, issue_numbers, assignee)

    print("\nAssignment complete.")

if __name__ == "__main__":
    main()
