import pytest
from unittest.mock import MagicMock
from app.agents.engineering.agent import EngineeringAgent
from app.schemas.session import EngineeringSessionSchema
from app.workflows.context import WorkflowContext


@pytest.fixture
def mock_llm_service():
    service = MagicMock()
    service.generate_structured_json.return_value = EngineeringSessionSchema(
        summary='Test summary',
        overall_risk='Low',
        confidence=0.95,
        change_summary={
            'summary': 'Summary of changes',
            'feature_type': 'Feature',
            'risk_level': 'Low',
            'confidence': 1.0,
            'affected_modules': [],
            'affected_services': [],
            'affected_routes': [],
            'affected_database_tables': [],
            'breaking_change': False,
            'architecture_impact': 'None',
            'reasoning': 'Changes to improve functionality.'
        },
        test_plan={
            'summary': 'Test plan generated.',
            'overall_risk': 'Low',
            'confidence': 1.0,
            'recommended_test_levels': {
                'unit': True,
                'integration': True,
                'api': False,
                'e2e': False,
            },
            'priority': 'High'
        },
        generated_tests={
            'framework': 'pytest',
            'generated_files': [
                {
                    'path': 'mock/path.py',
                    'content': 'print("Hello World")',
                    'language': 'python'
                }
            ],
            'new_fixtures': [],
            'mock_objects': [],
            'confidence': 1.0
        }
    )
    return service


def test_conduct_session_success(mock_llm_service):
    agent = EngineeringAgent(mock_llm_service)
    context = WorkflowContext(
        repository='test/repo',
        branch='main',
        commit_sha='123',
        changed_files=['app/agents/engineering/agent.py'],
        llm_context='mocked context'
    )
    result = agent.conduct_session(context)
    assert isinstance(result, EngineeringSessionSchema)
    assert result.summary == 'Test summary'


def test_conduct_session_no_changes(mock_llm_service):
    agent = EngineeringAgent(mock_llm_service)
    context = WorkflowContext(
        repository='test/repo',
        branch='main',
        commit_sha='123',
        changed_files=[],
        llm_context=''
    )
    with pytest.raises(ValueError, match="No meaningful code changes detected in this commit."):  
        agent.conduct_session(context)