# adapted from gemini 2025-05-26
from datetime import datetime, timezone
from dotenv import load_dotenv
import os
import requests
import time
import argparse # Import the argparse library

# --- Configuration user specific : see .env files 

# --- Load Environment Variables ---
load_dotenv()
YOUTRACK_TOKEN = os.getenv("YOUTRACK_TOKEN")
BASE_YOUTRACK_URL = os.getenv("YOUTRACK_URL")
# PROJECT_ID = os.getenv("YOUTRACK_PROJECT_ID")
ID_PAD_LENGTH = int(os.getenv("ID_PAD_LENGTH"))
EXTENSION = os.getenv("EXTENSION") # Use "html" for the spaces that use rich text formatting
MAX_SUMMARY_LENGTH_IN_PATH=int(os.getenv("MAX_SUMMARY_LENGTH_IN_PATH"))

# --- Helper functions from the original script (unchanged) ---

def clean_folder_name(
    name: str, replace_space: bool = True, space_replacement: str = "_"
) -> str:
    """
    Cleans a string to make it a valid folder name for both Linux and Windows.
    """
    invalid_chars = '<>:"/\\|?*'
    for char in invalid_chars:
        name = name.replace(char, "")
    if replace_space:
        name = name.replace(" ", space_replacement)
    reserved_names = [
        "CON", "PRN", "AUX", "NUL", "COM1", "COM2", "COM3", "COM4", "COM5",
        "COM6", "COM7", "COM8", "COM9", "LPT1", "LPT2", "LPT3", "LPT4",
        "LPT5", "LPT6", "LPT7", "LPT8", "LPT9",
    ]
    if name.upper() in reserved_names or name.startswith("."):
        name = "_" + name
    return name

def download_attachments(attachments, issue_folder_path, headers):
    """Download attachments for a given issue."""
    for attachment in attachments:
        # The attachment URL from the API is a relative path, needs the base URL
        attachment_url = BASE_YOUTRACK_URL + attachment["url"]
        print(f"  Downloading attachment: {attachment['name']}")
        response = requests.get(attachment_url, headers=headers, stream=True)
        if response.status_code == 200:
            attachment_path = os.path.join(issue_folder_path, attachment["name"])
            with open(attachment_path, "wb") as f:
                for chunk in response.iter_content(1024):
                    f.write(chunk)
        else:
            print(f"    Failed to download {attachment['name']}. Status: {response.status_code}")


def format_yt_time(atime):
   timestamp_obj = datetime.fromtimestamp(
       atime / 1000, tz=timezone.utc
   )
   return timestamp_obj.isoformat(timespec="seconds")


def proc_issues(issues, headers):
    """
    Processes a list of issue objects, creating folders and files.
    This function is reused from the original script.
    """
    if not issues:
        print("No issues found matching the provided IDs.")
        return

    for issue in issues:
        issue_id = issue["idReadable"]
        issue_number_in_project = issue["numberInProject"]
        issue_summary = issue["summary"] or "" # Ensure summary is not None
        project_short_name = issue["project"]["shortName"]

        # Truncating summary for both directory and file ---
        # 1. Truncate the summary to the max length
        truncated_summary = issue_summary[:MAX_SUMMARY_LENGTH_IN_PATH]
        # 2. Clean it for use in a path
        safe_summary_part = clean_folder_name(truncated_summary)
        # 3. Use the safe summary part to build the directory name
        directory_name = f"{project_short_name}-{str(issue_number_in_project).zfill(ID_PAD_LENGTH)}-{safe_summary_part}"
        issue_target_path = os.path.join("exports", directory_name)
        
        print(f"Processing {issue_target_path}")
        os.makedirs(issue_target_path, exist_ok=True)

        # 4. Use the safe summary part to build the filename
        file_name = f"{issue_id}-{safe_summary_part}.{EXTENSION}" 
        
        
        # Save issue details with the new filename
        with open(os.path.join(issue_target_path, file_name), "w", encoding='utf-8') as f:
            f.write(f"# {issue_id} - {issue['summary']}\n\n")
            icreated = format_yt_time(issue["created"]) if ("created" in issue) else "-"
            iupdated = format_yt_time(issue["updated"]) if ("updated" in issue) else "-"
            f.write(f"\nCreated: {icreated}\nUpdated: {iupdated}\n")
            if "tags" in issue and issue["tags"]:
              f.write("\nTAGS:\n")
              for tag in issue["tags"]:
                f.write(f"- {tag['name']}\n")

            if "customFields" in issue and issue["customFields"]:
              f.write("\nCUSTOM FIELDS:\n")
              for field in issue["customFields"]:
                fname = field.get('name') or "-"
                fval = field.get('value')
                if isinstance(fval, dict):
                    fval = fval.get('name') or str(fval)
                f.write(f"- {fname}: {fval}\n")

            f.write(f"\n---\n{issue.get('description', 'No description')}\n\n")
            f.write(f"\n---\n# Comments")
            for comment in issue.get("comments", []):
                comment_timestamp = format_yt_time(comment["created"]) if 'created' in comment else "-"
                comment_author = comment.get('author', {}).get('name', 'Unknown User')
                comment_section_title = f"Comment by {comment_author} at {comment_timestamp}"
                f.write(f"\n\n---\n---\n{comment_section_title}\n")
                if comment.get('deleted'):
                    f.write(f"  (This comment was deleted)\n")
                else:
                    f.write(f"\n{comment['text']}\n")

        if "attachments" in issue and issue["attachments"]:
            download_attachments(issue["attachments"], issue_target_path, headers)

# --- NEW function to get specific issues ---
def get_specific_issues(permanent_token: str, issue_ids: list):
    """
    Download specific issues by their readable IDs.
    """
    headers = {"Authorization": f"Bearer {permanent_token}"}
    
    # Create the query string by joining the issue IDs with spaces
    query_string = " ".join(issue_ids)
    
    params = {
        "fields": "idReadable,numberInProject,summary,created,updated,description,comments(author(name),created,deleted,text),attachments(name,url),project(id,shortName),tags(name),customFields(name,value(name))",
        "query": query_string,
    }
    issues_endpoint = f"{BASE_YOUTRACK_URL}/api/issues"

    print(f"Requesting issues: {query_string}")
    response = requests.get(issues_endpoint, headers=headers, params=params)

    if response.status_code != 200:
        print(f"Failed to fetch issues. Status: {response.status_code}")
        print("Response:", response.text)
        return

    issues = response.json()
    proc_issues(issues, headers)


if __name__ == "__main__":
    # Define the usage examples as a multi-line string
    example_text = """examples:
    > to export a single issue
    python export_specific_issue.py PROJECT-123
    > to export multiple issues
    python export_specific_issue.py PROJECT-123 TST-45
    """
    parser = argparse.ArgumentParser(
        description="Export specific issues from YouTrack by their readable IDs."
    )
    parser.add_argument(
        "issue_ids",
        metavar="ISSUE_ID",
        type=str,
        nargs="+",
        help="One or more issue IDs to export (e.g., PRJ-123 TST-456)",
    )

    args = parser.parse_args()

    if not YOUTRACK_TOKEN or not BASE_YOUTRACK_URL:
        print("Error: YOUTRACK_TOKEN and YOUTRACK_URL must be set in your .env file.")
    else:
        get_specific_issues(YOUTRACK_TOKEN, args.issue_ids)