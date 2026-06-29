import pytest
from unittest.mock import MagicMock, patch
from app.workflows.intelligence_stages import FeaturePlannerStage, ContextRetrievalStage

class TestFeaturePlannerStage:
    @patch('app.services.repository.planner.FeaturePlanner')
    def test_execute_creates_tasks(self, MockFeaturePlanner):
        context = MockContext()
        context.changed_files = ['file1.py', 'file2.py']
        context.structured_diff = {'added': [], 'modified': []}

        context = MagicMock()
        context.changed_files = ['file1.py']
        context.structured_diff = {'added': [], 'modified': []}

        # Arrange
        context = MagicMock()
        context.changed_files = ['file1.py', 'file2.py']
        context.structured_diff = {'added': [], 'modified': []}
        MockFeaturePlanner.create_tasks.return_value = ['task1', 'task2']
        planner_stage = FeaturePlannerStage()

        # Act
        planner_stage.execute(context)

        # Assert
        assert context.tasks == ['task1', 'task2']
        MockFeaturePlanner.create_tasks.assert_called_once_with(context.changed_files, context.structured_diff)

class TestContextRetrievalStage:
    @patch('app.services.repository.retriever.ContextRetrievalEngine')
    def test_execute_retrieves_context(self, MockRetriever):
        context = MockContext()
        context.current_task = MagicMock()
        context.current_task.related_files = ['file1.py']
        context.current_task.structured_diff = {'added': [{'path': 'file1.py'}], 'modified': []}

        context = MagicMock()
        context.workspace = 'mock_workspace'
        context.current_task = MagicMock()
        context.current_task.related_files = ['file1.py']
        context.current_task.structured_diff = {'added': [], 'modified': []}

        # Arrange
        context = MagicMock()
        context.workspace = 'mock_workspace'
        context.current_task = MagicMock()
        context.current_task.related_files = ['file1.py']
        context.current_task.structured_diff = {'added': [{'path': 'file1.py'}], 'modified': []}
        mock_retriever_instance = MockRetriever.return_value
        mock_retriever_instance.retrieve.return_value = 'retrieved_context'
        retrieval_stage = ContextRetrievalStage()

        # Act
        retrieval_stage.execute(context)

        # Assert
        assert context.retrieved_knowledge == 'retrieved_context'
        MockRetriever.assert_called_once_with(context.workspace)
        assert context.current_task.related_files == ['file1.py']