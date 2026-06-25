import os
import sys

# Ensure app is in path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from github import Github
from app.workflows.controller import WorkflowController
from app.config.settings import settings

try:
    g = Github(settings.GITHUB_TOKEN)
    repo = g.get_repo("kuchurisatwik/aws-web-hosting-infrastructure")
    commit = repo.get_branch("main").commit.sha

    payload = {
        "ref": "refs/heads/main",
        "before": "0000000000000000000000000000000000000000",
        "after": commit,
        "repository": {
            "name": "aws-web-hosting-infrastructure",
            "full_name": "kuchurisatwik/aws-web-hosting-infrastructure",
            "clone_url": "https://github.com/kuchurisatwik/aws-web-hosting-infrastructure.git"
        },
        "pusher": {"name": "kuchurisatwik"},
        "sender": {"login": "kuchurisatwik"}
    }

    controller = WorkflowController()
    print("Executing workflow manually...")
    controller.handle_push_event(payload)
    print("Workflow execution finished.")
except Exception as e:
    print(f"Error: {e}")
