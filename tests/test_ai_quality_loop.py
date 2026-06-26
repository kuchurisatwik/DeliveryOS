import pytest
from app.workflows.context import WorkflowContext
from app.services.test_executor import TestExecutionService
from app.services.validators import ValidationEngine

class TestQualityLoop:
    def test_execution_success(self):
        context = WorkflowContext(
            validation_report=None,
            test_execution_report=None,
            iteration_count=1
        )
        executor = TestExecutionService()
        result = executor.run_tests(context)
        assert result['status'] == 'SUCCESS', 'Test execution should complete successfully.'

    def test_validation_engine_response_consistency(self):
        context = WorkflowContext(
            validation_report=None,
            iteration_count=1
        )
        validation_engine = ValidationEngine()
        result1 = validation_engine.validate(context)
        result2 = validation_engine.validate(context)
        assert result1 == result2, 'Validation results should be consistent across multiple runs.'

    def test_webhook_handling(self):
        context = WorkflowContext(
            validation_report=None,
            iteration_count=1
        )
        # Simulate GitHub webhook event
        response = context.process_webhook_event(data={'event_type': 'push'})
        assert response['status_code'] == 200, 'Webhook should be processed without errors.'

    def test_quality_check_api_contract(self):
        response = context.check_quality()
        assert response['status_code'] == 200,
            'API should return success status.'
        assert 'quality_metrics' in response['body'],
            'API should return expected response structure.'

    def test_invalid_input_handling(self):
        context = WorkflowContext(
            validation_report=None,
            iteration_count=1
        )
        with pytest.raises(ValueError, match='Invalid input provided.'):
            context.validate_input(invalid_data={'input': 'invalid'})

    def test_extreme_value_inputs(self):
        context = WorkflowContext(
            validation_report=None,
            iteration_count=1
        )
        result = context.process_extreme_values(inputs=[float('inf'), -float('inf')])
        assert result['status'] == 'STABLE', 'System should not crash for extreme value inputs.'

    def test_authorization_on_quality_check(self):
        response = context.check_quality(authenticated=False)
        assert response['status_code'] == 403, 'Unauthorized users should receive a forbidden error.'

    def test_authentication_for_webhook(self):
        valid_request = context.authenticate_webhook_request(
            headers={'X-GitHub-Event': 'push'}, valid=True
        )
        assert valid_request is True, 'Only valid, authenticated requests should be processed.'
