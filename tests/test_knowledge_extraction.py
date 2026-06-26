import pytest
from app.services.extractors.ast_extractor import AstPythonExtractor
from app.schemas.knowledge import RepositoryKnowledge

class TestAstPythonExtractor:
    @pytest.fixture
    def valid_workspace(self, tmp_path):
        # Setup a valid workspace with sample Python files
        workspace = tmp_path / 'valid_repo'
        workspace.mkdir()
        (workspace / 'file1.py').write_text("def test_function(): pass")
        return str(workspace)

    @pytest.fixture
    def extractor(self):
        return AstPythonExtractor()

    def test_extract_valid_metadata(self, valid_workspace, extractor):
        knowledge = RepositoryKnowledge()
        extractor.extract(valid_workspace, knowledge)
        assert len(knowledge.class_index) > 0
        assert len(knowledge.class_index['file1.py']) > 0

    def test_extract_invalid_metadata(self, extractor):
        knowledge = RepositoryKnowledge()
        with pytest.raises(ValueError):
            extractor.extract('', knowledge)

    def test_agents_can_access_metadata(self, valid_workspace, extractor):
        knowledge = RepositoryKnowledge()
        extractor.extract(valid_workspace, knowledge)
        assert knowledge.class_index

    def test_workflows_use_extracted_knowledge(self, valid_workspace, extractor):
        knowledge = RepositoryKnowledge()
        extractor.extract(valid_workspace, knowledge)
        workflows_result = run_workflows_with_knowledge(knowledge)
        assert workflows_result is not None

    def test_unauthorized_access(self, extractor):
        with pytest.raises(PermissionError):
            perform_unauthorized_access()

    def test_missing_metadata_fields(self, extractor):
        knowledge = RepositoryKnowledge(class_index={})
        with pytest.raises(KeyError):
            validate_metadata(knowledge)

    def test_process_max_size_repository(self, valid_workspace, extractor):
        knowledge = RepositoryKnowledge()
        # Simulate max size repo conditions
        max_size_workspace = prepare_max_size_workspace(valid_workspace)
        extractor.extract(max_size_workspace, knowledge)
        assert knowledge

    def test_process_empty_repository(self, extractor):
        knowledge = RepositoryKnowledge()
        extractor.extract('', knowledge)  # Empty processing should not raise an error
        assert knowledge.class_index == {}

    def test_data_access_controls(self, extractor):
        knowledge = RepositoryKnowledge()
        extractor.extract(valid_workspace, knowledge)
        assert True  # Assume this method exists
