import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient
from app.github.routes import app

client = TestClient(app)

@pytest.mark.asyncio
async def test_valid_github_webhook_event():
    with patch('app.github.routes.run_ai_sde_workflow') as mock_task:
        response = await client.post('/github-webhook', json={
            'ref': 'refs/heads/main',
            'repository': {
                'full_name': 'owner/repo',
                'name': 'repo',
                'clone_url': 'https://github.com/owner/repo.git'
            },
            'after': 'commit_sha'
        })
        assert response.status_code == 200
        assert response.json() == {'status': 'accepted', 'message': 'Push event queued for processing'}
        mock_task.assert_called_once()

@pytest.mark.asyncio
async def test_invalid_signature():
    response = await client.post('/github-webhook', headers={'x_hub_signature_256': 'invalid_signature'})
    assert response.status_code == 403
    assert response.json() == {'detail': 'Invalid signature'}

@pytest.mark.asyncio
async def test_invalid_payload():
    response = await client.post('/github-webhook', json={'invalid_key': 'invalid_value'})
    assert response.status_code == 400
    assert response.json() == {'detail': 'Invalid payload'}

@pytest.mark.asyncio
async def test_ignore_ai_branch_push():
    with patch('app.github.routes.run_ai_sde_workflow') as mock_task:
        response = await client.post('/github-webhook', json={
            'ref': 'refs/heads/ai-sde/some_feature',
            'repository': {
                'full_name': 'owner/repo',
                'name': 'repo',
                'clone_url': 'https://github.com/owner/repo.git'
            },
            'after': 'commit_sha'
        })
        assert response.status_code == 200
        assert response.json() == {'status': 'ignored', 'message': 'Ignoring AI generated branch to prevent infinite loops'}
        mock_task.assert_not_called()