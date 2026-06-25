import httpx
from github import Github
from app.config.settings import settings

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

print("Sending POST request to http://127.0.0.1:8000/github/webhook...")
try:
    response = httpx.post(
        "http://127.0.0.1:8002/github/webhook",
        json=payload,
        headers={"x-github-event": "push"}
    )
    print(f"Status Code: {response.status_code}")
    print(f"Response: {response.json()}")
except Exception as e:
    print(f"Failed to send webhook: {e}\nIs the Uvicorn server running?")
