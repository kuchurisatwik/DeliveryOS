import pytest
from unittest.mock import patch
from app.services.repository.planner import FeaturePlanner

class TestFeaturePlanner:
    @pytest.fixture
    def dummy_structured_diff(self):
        return {
            'added': [],
            'modified': [],
            'deleted': [],
            'renamed': []
        }

    def test_extract_feature_name_with_test_prefix(self):
        result = FeaturePlanner.extract_feature_name('some/path/test_payment.py')
        assert result == 'payment'

    def test_extract_feature_name_with_service_suffix(self):
        result = FeaturePlanner.extract_feature_name('some/path/payment_service.py')
        assert result == 'payment'

    def test_create_tasks_no_changed_files(self, dummy_structured_diff):
        result = FeaturePlanner.create_tasks([], dummy_structured_diff)
        assert result == []

    def test_create_tasks_with_single_file(self, dummy_structured_diff):
        changed_files = ['some/path/test_payment.py']
        result = FeaturePlanner.create_tasks(changed_files, dummy_structured_diff)
        assert len(result) == 1
        assert result[0].feature_name == 'payment'
        assert result[0].related_files == changed_files
    
    def test_create_tasks_with_multiple_files(self, dummy_structured_diff):
        changed_files = ['some/path/test_payment.py', 'some/path/test_order.py']
        result = FeaturePlanner.create_tasks(changed_files, dummy_structured_diff)
        assert len(result) == 2
        assert all(task.feature_name in ['payment', 'order'] for task in result)