import os
import git
from typing import List
from app.utils.logger import logger
from app.config.settings import settings

class GitService:
    """Service for interacting with git repositories locally."""
    
    def __init__(self, workspace_dir: str = None):
        self.workspace_dir = workspace_dir or settings.WORKSPACE_DIR
        os.makedirs(self.workspace_dir, exist_ok=True)
        
    def clone_repository(self, clone_url: str, repo_name: str) -> str:
        """Clones a repository into the workspace.
        
        Args:
            clone_url: URL to clone from
            repo_name: Name of the repository folder
            
        Returns:
            The path to the cloned repository
        """
        repo_path = os.path.join(self.workspace_dir, repo_name)
        if os.path.exists(repo_path):
            logger.info(f"Repository {repo_name} already exists at {repo_path}. Fetching latest changes.")
            repo = git.Repo(repo_path)
            try:
                repo.remotes.origin.fetch()
            except Exception as e:
                logger.error(f"Failed to fetch latest changes: {e}")
            return repo_path
            
        # Inject GitHub Token for authentication if available
        auth_url = clone_url
        if settings.GITHUB_TOKEN and clone_url.startswith("https://"):
            auth_url = clone_url.replace("https://", f"https://x-access-token:{settings.GITHUB_TOKEN}@")

        logger.info(f"Cloning repository to {repo_path}")
        git.Repo.clone_from(auth_url, repo_path)
        return repo_path

    def get_changed_files(self, repo_path: str, commit_sha: str) -> List[str]:
        """Gets a list of changed files for a specific commit."""
        repo = git.Repo(repo_path)
        try:
            commit = repo.commit(commit_sha)
            
            # If it has parents, diff with the first parent. Otherwise, it's the initial commit.
            if commit.parents:
                diff_index = commit.parents[0].diff(commit)
                changed_files = [item.b_path for item in diff_index]
                return changed_files
            else:
                return list(commit.stats.files.keys())
        except Exception as e:
            logger.error(f"Failed to get changed files for {commit_sha}: {e}")
            return []

    def get_commit_diff(self, repo_path: str, commit_sha: str) -> dict:
        """Gets the structured diff containing actual code changes."""
        repo = git.Repo(repo_path)
        result = {"added": [], "modified": [], "deleted": [], "renamed": []}
        try:
            commit = repo.commit(commit_sha)
            if not commit.parents:
                return result # Initial commit logic can be added if needed
                
            diff_index = commit.parents[0].diff(commit, create_patch=True)
            for diff in diff_index:
                # Handle different change types
                file_info = {
                    "path": diff.b_path if diff.b_path else diff.a_path,
                    "diff": diff.diff.decode('utf-8') if diff.diff else ""
                }
                
                if diff.new_file:
                    result["added"].append(file_info)
                elif diff.deleted_file:
                    result["deleted"].append(file_info)
                elif diff.renamed_file:
                    result["renamed"].append({
                        "old_path": diff.a_path,
                        "new_path": diff.b_path,
                        "diff": file_info["diff"]
                    })
                else:
                    result["modified"].append(file_info)
                    
            return result
        except Exception as e:
            logger.error(f"Failed to get commit diff for {commit_sha}: {e}")
            return result

    def create_branch(self, repo_path: str, branch_name: str, base_commit_sha: str = None) -> None:
        """Creates and checks out a new branch."""
        repo = git.Repo(repo_path)
        
        if base_commit_sha:
            # Check out the base commit and clean any leftover files from previous runs
            repo.git.checkout(base_commit_sha)
            repo.git.reset('--hard', base_commit_sha)
            repo.git.clean('-fd')
            
        logger.info(f"Creating branch {branch_name} in {repo_path}")
        new_branch = repo.create_head(branch_name)
        new_branch.checkout()

    def commit_changes(self, repo_path: str, commit_message: str) -> None:
        """Stages all changes and commits them."""
        repo = git.Repo(repo_path)
        repo.git.add(A=True)
        logger.info(f"Committing changes: {commit_message}")
        repo.index.commit(commit_message)

    def push_branch(self, repo_path: str, branch_name: str) -> None:
        """Pushes the given branch to the origin."""
        repo = git.Repo(repo_path)
        origin = repo.remote(name='origin')
        logger.info(f"Pushing branch {branch_name} to origin")
        
        # Assuming we might be using HTTP/HTTPS without stored credentials,
        # we might need to inject the token into the remote URL.
        # For Phase 1 dummy testing, this attempts a normal push.
        # Real implementation would handle auth.
        try:
            origin.push(branch_name)
        except Exception as e:
            logger.error(f"Failed to push branch: {e}")
            raise
