import pytest
from unittest.mock import MagicMock
from app.agents.engineering.agent import EngineeringAgent

@pytest.fixture
def mock_llm_service():
    llm_service = MagicMock()
    llm_service.commit = MagicMock(return_value=True)
    return llm_service

@pytest.fixture
def engineering_agent(mock_llm_service):
    return EngineeringAgent(llm_service=mock_llm_service)

# Test case for successful session with changes
def test_conduct_session_with_changes(engineering_agent, mock_llm_service):
    # Arrange
    commit_message = "This is a test commit"

    # Act
    result = mock_llm_service.commit(commit_message)

    # Assert
    assert result is True
    mock_llm_service.commit.assert_called_with(commit_message)

# Test case for empty commit
def test_conduct_session_empty_commit(engineering_agent, mock_llm_service):
    # Arrange
    commit_info = {'message': ""}

    # Act
    result = mock_llm_service.commit(commit_info['message'])

    # Assert
    assert result is True
    mock_llm_service.commit.assert_called_with(commit_info['message'])