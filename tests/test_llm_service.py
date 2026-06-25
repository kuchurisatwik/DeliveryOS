import pytest
from unittest.mock import patch, Mock
from app.services.llm_service import LLMService
from app.config.settings import settings

@pytest.fixture
def llm_service():
    with patch('app.services.llm_service.settings') as mock_settings:
        mock_settings.OPENROUTER_API_KEY = 'test_openrouter_key'
        mock_settings.GEMINI_API_KEY = None
        service = LLMService()
        yield service

@pytest.mark.parametrize('response_data,expected', [
    ({'status': 'success', 'data': {'result': 'test'}}, 'test'),
    ({'status': 'error', 'message': 'Invalid request'}, None)
])
@patch('httpx.AsyncClient.post')
def test_openrouter_api_integration_logic(mock_post, llm_service, response_data, expected):
    mock_post.return_value.__aenter__.return_value.json.return_value = response_data
    result = llm_service._call_openrouter('some_payload')
    if expected:
        assert result['result'] == expected
    else:
        assert result is None

@patch('httpx.AsyncClient.post')
def test_handle_invalid_openrouter_api_response(mock_post, llm_service):
    mock_post.return_value.__aenter__.return_value.json.return_value = {'status': 'error', 'message': 'Invalid request'}
    with patch('app.utils.logger') as mock_logger:
        result = llm_service._call_openrouter('some_payload')
        assert result is None
        mock_logger.warning.assert_called_with('Invalid response from OpenRouter API.')

@patch('httpx.AsyncClient.post')
def test_openrouter_api_contract_compliance(mock_post, llm_service):
    mock_post.return_value.__aenter__.return_value.json.return_value = {'status': 'success', 'data': {'result': 'data'}}
    result = llm_service._call_openrouter('some_payload')
    assert 'status' in result and 'data' in result
    assert isinstance(result['data'], dict)

@patch('httpx.AsyncClient.post')
def test_auth_failure_openrouter(mock_post, llm_service):
    mock_post.return_value.__aenter__.return_value.status_code = 403
    result = llm_service._call_openrouter('some_payload')
    assert result is None

@patch('httpx.AsyncClient.post')
def test_simulate_openrouter_downtime(mock_post, llm_service):
    mock_post.side_effect = httpx.ConnectError('Failed to connect')
    with patch('app.utils.logger') as mock_logger:
        result = llm_service._call_openrouter('some_payload')
        assert result is None
        mock_logger.error.assert_called_with('OpenRouter API is currently unavailable.')

@patch('httpx.AsyncClient.post')
def test_test_invalid_configuration_openrouter(mock_post, llm_service):
    with patch('app.utils.logger') as mock_logger:
        llm_service.openrouter_key = None
        result = llm_service._call_openrouter('some_payload')
        assert result is None
        mock_logger.error.assert_called_with('OpenRouter API configuration is invalid.')

@patch('httpx.AsyncClient.post')
def test_test_maximum_input_size_openrouter(mock_post, llm_service):
    large_payload = 'x' * 10**6
    mock_post.return_value.__aenter__.return_value.json.return_value = {'status': 'success', 'data': {'result': 'valid'}}
    result = llm_service._call_openrouter(large_payload)
    assert result['data']['result'] == 'valid'

@patch('httpx.AsyncClient.post')
def test_check_input_validation_against_injection_attacks(mock_post, llm_service):
    malicious_payload = '<script>alert(1)</script>'
    with patch('app.utils.logger') as mock_logger:
        result = llm_service._call_openrouter(malicious_payload)
        assert result is None
        mock_logger.warning.assert_called_with('Malicious data detected and rejected.')
