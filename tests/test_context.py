import pytest
from app.workflows.context import WorkflowContext, EngineeringTask


def test_engineering_task_initialization():
    task = EngineeringTask(feature_name='context')
    assert task.feature_name == 'context'
    assert task.related_files == []
    assert task.structured_diff == {'added': [], 'modified': [], 'deleted': [], 'renamed': []}


def test_workflow_context_with_engineering_task():
    task = EngineeringTask(feature_name='context')
    workflow_context = WorkflowContext(
        repository='kuchurisatwik/DeliveryOS',
        commit_sha='dummy_sha',
        changed_files=["app/workflows/context.py"],
        tasks=[task]
    )
    assert len(workflow_context.tasks) == 1
    assert workflow_context.tasks[0].feature_name == 'context'
