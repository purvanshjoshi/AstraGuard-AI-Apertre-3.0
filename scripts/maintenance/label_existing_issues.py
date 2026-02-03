import subprocess
import json

def get_all_issue_numbers(repo):
    cmd = [
        "gh", "issue", "list",
        "--repo", repo,
        "--limit", "1000",
        "--json", "number",
        "--state", "all"
    ]
    result = subprocess.run(cmd, input="", capture_output=True, text=True, check=True)
    issues = json.loads(result.stdout)
    return [issue["number"] for issue in issues]

def add_label_to_issues(repo, issue_numbers, label):
    for number in issue_numbers:
        print(f"Adding label '{label}' to issue #{number}...")
        cmd = [
            "gh", "issue", "edit", str(number),
            "--repo", repo,
            "--add-label", label
        ]
        try:
            subprocess.run(cmd, input="", capture_output=True, text=True, check=True)
            print(f"Successfully labeled #{number}")
        except subprocess.CalledProcessError as e:
            print(f"Failed to label #{number}: {e.stderr}")

def main():
    repo = "sr-857/AstraGuard-AI-Apertre-3.0"
    label = "apertre3.0"
    
    print(f"Fetching issue numbers for {repo}...")
    issue_numbers = get_all_issue_numbers(repo)
    print(f"Found {len(issue_numbers)} issues.")
    
    if not issue_numbers:
        print("No issues found to label.")
        return

    add_label_to_issues(repo, issue_numbers, label)
    print("Labeling complete.")

if __name__ == "__main__":
    main()
