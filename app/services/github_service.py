from github import Github
from app.config.settings import settings
from app.utils.logger import logger

class GitHubService:
    """Service for interacting with the GitHub API."""
    
    def __init__(self, token: str = None):
        self.token = token or settings.GITHUB_TOKEN
        self.github = Github(self.token) if self.token else None
        
    def open_pull_request(self, repo_full_name: str, head_branch: str, base_branch: str, title: str, body: str) -> str:
        """Opens a pull request on GitHub.
        
        Args:
            repo_full_name: Format 'owner/repo'
            head_branch: The branch containing the changes
            base_branch: The branch to merge into
            title: Title of the PR
            body: Body description of the PR
            
        Returns:
            URL of the created pull request, or a dummy URL if no token is configured.
        """
        if not self.github:
            logger.warning("No GitHub token configured. Skipping PR creation.")
            return "http://dummy-pr-url"
            
        try:
            repo = self.github.get_repo(repo_full_name)
            logger.info(f"Creating PR from {head_branch} to {base_branch} in {repo_full_name}")
            
            pr = repo.create_pull(title=title, body=body, head=head_branch, base=base_branch)
            logger.info(f"Successfully created PR: {pr.html_url}")
            return pr.html_url
        except Exception as e:
            logger.error(f"Failed to create PR: {e}")
            return ""
