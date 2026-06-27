import pytest
from app.agents.engineering.agent import EngineeringAgent
from app.agents.repair.agent import RepairAgent
from app.services.llm_service import LLMService
from app.workflows.context import WorkflowContext

@pytest.fixture
def llm_service():
    return LLMService()

@pytest.fixture
def workflow_context():
    return WorkflowContext(
            repository='test_repo',
            repo_name='test_repo',
            clone_url='http://mock.clone.url',
            branch='main',
            commit_sha='abcd1234'
        )

def test_engineering_agent_initialization(llm_service):
    agent = EngineeringAgent(llm_service=llm_service)
    assert agent.llm_service == llm_service


def test_engineering_agent_conduct_session(llm_service, workflow_context):
    agent = EngineeringAgent(llm_service=llm_service)
    result = agent.conduct_session(workflow_context)
    assert result is not None
    assert hasattr(result, 'change_summary')
    assert hasattr(result, 'test_plan')
    assert hasattr(result, 'generated_tests')


def test_repair_agent_initialization(llm_service):
    agent = RepairAgent(llm_service=llm_service)
    assert agent.llm_service == llm_service


def test_repair_agent_conduct_session(llm_service, workflow_context):
    agent = RepairAgent(llm_service=llm_service)
    result = agent.conduct_session(workflow_context)
    assert result is not None
    assert hasattr(result, 'reasoning')
    assert hasattr(result, 'patches')
