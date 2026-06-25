from app.workflows.context import WorkflowContext
from app.workflows.results import WorkflowResult
from app.workflows.stages import Stage
from app.workflows.orchestrator import WorkflowOrchestrator

class DummySuccessStage(Stage):
    def execute(self, context, git_service, github_service):
        context.status = "STAGE_SUCCESS"

class DummyFailStage(Stage):
    def execute(self, context, git_service, github_service):
        raise ValueError("Simulated failure")

def test_workflow_orchestrator_success():
    context = WorkflowContext(
        repository="test/repo",
        repo_name="repo",
        clone_url="http://test",
        branch="main",
        commit_sha="123"
    )
    stages = [DummySuccessStage()]
    orchestrator = WorkflowOrchestrator(None, None)
    result = orchestrator.run_pipeline(context, stages)
    
    assert result.status == "SUCCESS"
    assert "DummySuccessStage" in result.completed_stages
    assert context.status == "COMPLETED"

def test_workflow_orchestrator_failure():
    context = WorkflowContext(
        repository="test/repo",
        repo_name="repo",
        clone_url="http://test",
        branch="main",
        commit_sha="123"
    )
    stages = [DummySuccessStage(), DummyFailStage()]
    orchestrator = WorkflowOrchestrator(None, None)
    result = orchestrator.run_pipeline(context, stages)
    
    assert result.status == "FAILED"
    assert "DummySuccessStage" in result.completed_stages
    assert "DummyFailStage" not in result.completed_stages
    assert len(result.errors) == 1
    assert "Simulated failure" in result.errors[0]
    assert context.status == "FAILED"
