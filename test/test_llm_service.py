import pytest
from app.services.llm_service import LLMService
from unittest.mock import patch, MagicMock
from app.config.settings import settings

@pytest.fixture
def llm_service():
    return LLMService()

@pytest.fixture
def mock_openrouter_response():
    return {'success': True, 'data': {'result': 'sample response'}}

@pytest.fixture
def mock_openrouter_error_response():
    return {'success': False, 'error': 'Invalid API key'}

def test_openrouter_api_key_success(llm_service):
    settings.OPENROUTER_API_KEY = 'valid_api_key'
    assert llm_service.openrouter_key == 'valid_api_key'

def test_openrouter_api_key_validation_failure(llm_service):
    settings.OPENROUTER_API_KEY = 'invalid_api_key'
    with patch('app.services.llm_service.httpx.AsyncClient') as mock_client:
        mock_instance = mock_client.return_value
        mock_instance.post.return_value.status_code = 401
        mock_instance.post.return_value.json.return_value = mock_openrouter_error_response()
        with pytest.raises(Exception) as excinfo:
            llm_service._call_openrouter('test input')
        assert 'Invalid API key' in str(excinfo.value)

def test_openrouter_api_integration(llm_service, mock_openrouter_response):
    settings.OPENROUTER_API_KEY = 'valid_api_key'
    with patch('app.services.llm_service.httpx.AsyncClient') as mock_client:
        mock_instance = mock_client.return_value
        mock_instance.post.return_value.status_code = 200
        mock_instance.post.return_value.json.return_value = mock_openrouter_response
        response = llm_service._call_openrouter('test input')
        assert response['success'] is True
        assert response['data']['result'] == 'sample response'

def test_llm_service_without_api_key(llm_service):
    settings.OPENROUTER_API_KEY = None
    with pytest.raises(Exception) as excinfo:
        llm_service._call_openrouter('test input')
    assert 'API key is required' in str(excinfo.value)

def test_api_key_max_length(llm_service):
    max_length_key = 'a' * 100
    settings.OPENROUTER_API_KEY = max_length_key
    assert llm_service.openrouter_key == max_length_key

def test_openrouter_api_error_handling(llm_service):
    settings.OPENROUTER_API_KEY = 'valid_api_key'
    with patch('app.services.llm_service.httpx.AsyncClient') as mock_client:
        mock_instance = mock_client.return_value
        mock_instance.post.return_value.status_code = 500
        mock_instance.post.return_value.json.return_value = {'success': False, 'error': 'Internal Server Error'}
        with pytest.raises(Exception) as excinfo:
            llm_service._call_openrouter('test input')
        assert 'Internal Server Error' in str(excinfo.value)

def test_api_key_access_denied(llm_service):
    # This is a placeholder for mock authentication logic
    settings.OPENROUTER_API_KEY = 'unauthorized_key'
    with pytest.raises(Exception) as excinfo:
        llm_service._call_openrouter('test input')
    assert 'Access denied' in str(excinfo.value)
