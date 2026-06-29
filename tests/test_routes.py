import pytest
from unittest.mock import patch, MagicMock
from app.github.routes import run_ai_sde_workflow

@pytest.fixture
def mock_context():
    mock = MagicMock()
    mock.changed_files = []
    mock.repository = 'kuchurisatwik/DeliveryOS'
    mock.branch = 'main'
    mock.current_task = MagicMock()
    mock.current_task.feature_name = 'DummyFeature'
    mock.current_task.related_files = []
    mock.current_task.structured_diff = {'added': [], 'modified': []}
    return mock

@pytest.fixture
def mock_orchestrator():
    with patch('app.github.routes.WorkflowOrchestrator') as mock:
        yield mock

@patch('app.github.routes.logger')
def test_no_tasks_processed(mock_logger, mock_orchestrator, mock_context):
    mock_context.tasks = []
    run_ai_sde_workflow(mock_context)
    mock_logger.info.assert_called_with('No tasks to process. Exiting workflow.')

@patch('app.github.routes.WorkflowOrchestrator')
def test_feature_planner_stage(mock_workflow_orchestrator):
    run_ai_sde_workflow(mock_context)
    pre_stages = mock_workflow_orchestrator.run_pipeline.call_args[0][1]
    assert 'FeaturePlannerStage' in [stage.__class__.__name__ for stage in pre_stages]

@patch('app.github.routes.WorkflowOrchestrator')
@patch('app.github.routes.logger')
def test_task_processing_logic(mock_logger, mock_workflow_orchestrator, mock_context):
    mock_context.tasks = [MagicMock(feature_name='Task1')]
    run_ai_sde_workflow(mock_context)
    mock_logger.info.assert_called_with('Processing 1 independent Engineering Tasks...')
