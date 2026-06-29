
import pytest
from unittest.mock import MagicMock, patch
from app.agents.engineering.agent import EngineeringAgent

class MockContext:
    def __init__(self, current_task=None):
        self.current_task = current_task
        self.changed_files = []
        self.repository = 'kuchurisatwik/DeliveryOS'
        self.branch = 'main'
        self.feature_name = 'dummy_feature_name'

    def __init__(self, current_task=None):
        self.current_task = current_task
        self.changed_files = ['file1.py']
        self.repository = 'kuchurisatwik/DeliveryOS'
        self.branch = 'main'

    def __init__(self, current_task=None):
        self.current_task = current_task
        self.changed_files = []
        self.repository = 'kuchurisatwik/DeliveryOS'
        self.branch = 'main'
        self.related_files = []
        self.repository_language = 'Python'
        self.framework = 'FastAPI/Pytest'

    def __init__(self, current_task=None):
        self.current_task = current_task
        self.changed_files = []
        self.repository = 'kuchurisatwik/DeliveryOS'
        self.branch = 'main'

    def __init__(self, current_task=None):
        self.current_task = current_task
        self.changed_files = []
        self.repository = 'kuchurisatwik/DeliveryOS'
        self.branch = 'main'

    def __init__(self, current_task=None):
        self.current_task = current_task
        self.changed_files = []
        self.repository = 'kuchurisatwik/DeliveryOS'
        self.branch = 'main'

    def __init__(self, current_task=None):
        self.current_task = current_task
        self.changed_files = []
        self.repository = 'kuchurisatwik/DeliveryOS'
        self.branch = 'main'
        self.repository_language = 'Python'

    def __init__(self, current_task=None):
        self.current_task = current_task
        self.changed_files = []
        self.repository = 'kuchurisatwik/DeliveryOS'
        self.branch = 'main'

    def __init__(self, current_task=None):
        self.current_task = current_task
        self.repository = 'kuchurisatwik/DeliveryOS'
        self.branch = 'main'
        self.repository_language = 'Python'
        self.framework = 'FastAPI/Pytest'
        self.structured_diff = {'added': [], 'modified': []}
        self.changed_files = []
        self.changed_files = ['file1.py', 'file2.py']
    def __init__(self, current_task=None):
        self.current_task = current_task
        self.repository = 'kuchurisatwik/DeliveryOS'
        self.branch = 'main'
        self.repository_language = 'Python'
        self.framework = 'FastAPI/Pytest'
        self.structured_diff = {'added': [], 'modified': []}
        self.changed_files = []
    def __init__(self, current_task=None):
        self.current_task = current_task
        self.repository = 'kuchurisatwik/DeliveryOS'
        self.branch = 'main'
        self.repository_language = 'Python'
        self.framework = 'FastAPI/Pytest'
        self.structured_diff = {'added': [], 'modified': []}

@pytest.fixture
def mock_engineering_agent():
    llm_service = MagicMock()
    return EngineeringAgent(llm_service)


def test_conduct_session_no_current_task(mock_engineering_agent):
    context = MockContext()
    with pytest.raises(ValueError) as exc:
        mock_engineering_agent.conduct_session(context)
    assert str(exc.value) == 'No current task set. Feature Planner failed to extract a task.'


def test_conduct_session_no_meaningful_changes(mock_engineering_agent):
    task = MagicMock()
    task.related_files = []
    task.structured_diff = {'added': [], 'modified': []}
    context = MockContext(current_task=task)
    with pytest.raises(ValueError) as exc:
        mock_engineering_agent.conduct_session(context)
    assert str(exc.value) == 'No meaningful code changes detected in this task.'


def test_conduct_session_success(mock_engineering_agent):
    task = MagicMock()
    task.related_files = ['app/agents/engineering/agent.py']
    task.structured_diff = {'added': ['new_feature.py'], 'modified': []}
    context = MockContext(current_task=task)
    try:
        mock_engineering_agent.conduct_session(context)
    except ValueError:
        pytest.fail('conduct_session raised ValueError unexpectedly!')
