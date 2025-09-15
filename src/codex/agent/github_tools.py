"""
The GitHub Toolkit: The Agent's Interface to the Developer World.

This module provides a set of tools for the agent to interact with the
GitHub API. It uses the `PyGithub` library to handle the complexities of
API communication.

Core responsibilities:
1.  Securely authenticating with the GitHub API using a Personal Access Token.
2.  Providing tools to interact with GitHub Issues.
3.  Providing tools to interact with GitHub Pull Requests for code review.
"""

import os
import json
from github import Github, GithubException

# --- "Just-in-Time" Authentication ---
_github_instance = None

def _get_github_instance():
    """
    Initializes and returns a singleton Github instance.
    This function is called by tools only when they are needed.
    """
    global _github_instance
    if _github_instance is None:
        try:
            GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN")
            if not GITHUB_TOKEN:
                raise ValueError("GITHUB_TOKEN not found in environment.")
            
            _github_instance = Github(GITHUB_TOKEN)
            auth_user = _github_instance.get_user()
            print(f"--- ✅ Successfully authenticated with GitHub as '{auth_user.login}' ---")
        except (ValueError, GithubException) as e:
            print(f"--- ❌ ERROR: Failed to authenticate with GitHub. ---")
            print(f"--- Please ensure a valid GITHUB_TOKEN is set in your .env file. Error: {e} ---")
            return None
    return _github_instance

# --- Issue Tools (from Sprint 8) ---

def get_issue_details(repo_name: str, issue_number: int) -> str:
    """
    Fetches the title and body of a specific issue from a GitHub repository.
    
    Args:
        repo_name: The full name of the repository (e.g., 'Manoj-Murari/codex-veritas').
        issue_number: The number of the issue to retrieve.
        
    Returns:
        A formatted string containing the issue's title and body, or an error message.
    """
    g = _get_github_instance()
    if g is None:
        return "Error: GitHub API is not authenticated. Cannot get issue details."
        
    try:
        repo = g.get_repo(repo_name)
        issue = repo.get_issue(number=issue_number)
        
        return f"Issue #{issue.number}: {issue.title}\n\nBody:\n{issue.body}"
        
    except GithubException as e:
        return f"Error: Could not retrieve issue '{repo_name}#{issue_number}'. Status: {e.status}, Message: {e.data}"
    except Exception as e:
        return f"An unexpected error occurred: {e}"

def post_comment_on_issue(repo_name: str, issue_number: int, comment_body: str) -> str:
    """
    Posts a new comment to a specific issue in a GitHub repository.
    
    Args:
        repo_name: The full name of the repository (e.g., 'Manoj-Murari/codex-veritas').
        issue_number: The number of the issue to comment on.
        comment_body: The content of the comment to post.
        
    Returns:
        A success message with a link to the new comment, or an error message.
    """
    g = _get_github_instance()
    if g is None:
        return "Error: GitHub API is not authenticated. Cannot post comment."

    if not comment_body or not comment_body.strip():
        return "Error: Comment body cannot be empty."

    try:
        repo = g.get_repo(repo_name)
        issue = repo.get_issue(number=issue_number)
        comment = issue.create_comment(comment_body)
        
        return f"Success: Comment posted successfully. URL: {comment.html_url}"

    except GithubException as e:
        return f"Error: Could not post comment to '{repo_name}#{issue_number}'. Status: {e.status}, Message: {e.data}"
    except Exception as e:
        return f"An unexpected error occurred: {e}"

# --- NEW Pull Request Tools (for Sprint 9) ---

def get_pr_changed_files(repo_name: str, pr_number: int) -> str:
    """
    Fetches a list of file paths that were changed in a specific pull request.
    
    Args:
        repo_name: The full name of the repository (e.g., 'Manoj-Murari/codex-veritas').
        pr_number: The number of the pull request.
        
    Returns:
        A JSON string containing a list of changed file paths, or an error message.
    """
    g = _get_github_instance()
    if g is None:
        return "Error: GitHub API is not authenticated."

    try:
        repo = g.get_repo(repo_name)
        pr = repo.get_pull(number=pr_number)
        files = [file.filename for file in pr.get_files()]
        return json.dumps(files)
        
    except GithubException as e:
        return f"Error retrieving PR changed files: {e.status} {e.data}"
    except Exception as e:
        return f"An unexpected error occurred: {e}"

def get_file_content_from_pr(repo_name: str, pr_number: int, file_path: str) -> str:
    """
    Gets the complete content of a specific file as it appears in the pull request branch.
    
    Args:
        repo_name: The full name of the repository.
        pr_number: The number of the pull request.
        file_path: The path to the file within the repository.
        
    Returns:
        The decoded content of the file as a string, or an error message.
    """
    g = _get_github_instance()
    if g is None:
        return "Error: GitHub API is not authenticated."
        
    try:
        repo = g.get_repo(repo_name)
        pr = repo.get_pull(number=pr_number)
        # Get the commit SHA of the PR's head branch
        head_sha = pr.head.sha
        # Get the file content at that specific commit
        file_content = repo.get_contents(file_path, ref=head_sha)
        
        # The content is base64 encoded, so we must decode it.
        return file_content.decoded_content.decode('utf-8')
        
    except GithubException as e:
        return f"Error retrieving file content from PR: {e.status} {e.data}"
    except Exception as e:
        return f"An unexpected error occurred: {e}"

def post_pr_review_comment(repo_name: str, pr_number: int, comment_body: str) -> str:
    """
    Posts a formal review comment on an entire pull request.
    
    Args:
        repo_name: The full name of the repository.
        pr_number: The number of the pull request to review.
        comment_body: The content of the review comment.
        
    Returns:
        A success message with a link to the new review, or an error message.
    """
    g = _get_github_instance()
    if g is None:
        return "Error: GitHub API is not authenticated."
        
    if not comment_body or not comment_body.strip():
        return "Error: Review comment body cannot be empty."
        
    try:
        repo = g.get_repo(repo_name)
        pr = repo.get_pull(number=pr_number)
        review = pr.create_review(body=comment_body, event="COMMENT")
        
        return f"Success: Review comment posted successfully. URL: {review.html_url}"
        
    except GithubException as e:
        return f"Error posting review comment: {e.status} {e.data}"
    except Exception as e:
        return f"An unexpected error occurred: {e}"

