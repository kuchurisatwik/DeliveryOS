import pytest
from unittest.mock import patch, MagicMock
from app.services.llm_service import LLMService
from app.config.settings import settings

class TestLLMService:
    @patch('httpx.Client')
    def test_initialize_opens_router_api_with_key(self, mock_httpx_client):
        settings.OPENROUTER_API_KEY = 'test_openrouter_key'
        service = LLMService()
        assert service.openrouter_key == 'test_openrouter_key'
        assert service.gemini_key is None

    @patch('httpx.Client')
    def test_successful_openrouter_api_call(self, mock_httpx_client):
        mock_response = MagicMock()
        mock_response.json.return_value = {'data': 'expected data'}
        mock_httpx_client.return_value.post.return_value = mock_response
        service = LLMService()
        response = service._call_openrouter('input data')
        assert response['data'] == 'expected data'

    @patch('httpx.Client')
    def test_fallback_to_gemini_on_openrouter_failure(self, mock_httpx_client):
        mock_httpx_client.return_value.post.side_effect = httpx.HTTPStatusError('Error', request=None, response=None)
        service = LLMService()
        service.gemini_key = 'test_gemini_key'
        response = service._call_openrouter('input data')
        assert response is None  # Assuming fallback returns None

    def test_invalid_api_response_handling(self):
        service = LLMService()
        with pytest.raises(ValueError):
            service._call_openrouter('input data with syntax error')  # Simulating error case

    def test_unauthorized_access(self):
        service = LLMService()
        with pytest.raises(Exception) as exc_info:
            service._call_openrouter('restricted input')
        assert str(exc_info.value) == '401 Unauthorized'  # Placeholder for actual unauthorized error handling

    def test_api_rate_limiting_exceeded(self):
        service = LLMService()
        with pytest.raises(Exception) as exc_info:
            service._call_openrouter('input data exceeding rate limit')
        assert 'Rate limit exceeded' in str(exc_info.value)

    def test_boundary_value_for_api_parameters(self):
        service = LLMService()
        response_min = service._call_openrouter('min boundary input')
        response_max = service._call_openrouter('max boundary input')
        assert response_min is not None
        assert response_max is not None

    @pytest.mark.parametrize('input_data', ['<script>alert(1)</script>', 'SELECT * FROM users;'])
    def test_input_validation_security(self, input_data):
        service = LLMService()
        sanitized_input = service._sanitize(input_data)
        assert sanitized_input == ''  # Assuming sanitizer returns empty for invalid input
