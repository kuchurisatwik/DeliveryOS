import os
import pytest
from unittest.mock import patch, MagicMock
from app.services.repository.indexer import RepositoryIndexer

@pytest.fixture
def mock_db():
    with patch('app.services.repository.indexer.RepositoryDB') as mock:
        yield mock

@pytest.fixture
def indexer(mock_db):
    workspace_path = 'test_workspace'
    return RepositoryIndexer(workspace_path)

def test_index_valid_python_file(indexer, mock_db):
    mock_db.get_connection.return_value.__enter__.return_value.execute = MagicMock()
    test_file_path = os.path.join(indexer.workspace_path, 'valid_test.py')
    with open(test_file_path, 'w') as f:
        f.write('def test_func(): pass')
    indexer.index_repository()
    assert mock_db.get_connection.return_value.__enter__.return_value.execute.called
    assert mock_db.get_connection.return_value.__enter__.return_value.execute.call_count == 1


def test_handle_invalid_python_file(indexer, mock_db):
    mock_db.get_connection.return_value.__enter__.return_value.execute = MagicMock()
    test_file_path = os.path.join(indexer.workspace_path, 'invalid_test.py')
    with open(test_file_path, 'w') as f:
        f.write('def test_func() :') # Missing body
    indexer.index_repository()
    assert not mock_db.get_connection.return_value.__enter__.return_value.execute.called


def test_index_test_files(indexer, mock_db):
    mock_db.get_connection.return_value.__enter__.return_value.execute = MagicMock()
    test_file_path = os.path.join(indexer.workspace_path, 'tests/test_func.py')
    os.makedirs(os.path.dirname(test_file_path), exist_ok=True)
    with open(test_file_path, 'w') as f:
        f.write('def test_func(): pass')
    indexer.index_repository()
    assert mock_db.get_connection.return_value.__enter__.return_value.execute.call_count == 1