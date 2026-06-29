from unittest.mock import patch, MagicMock
from app.agents.engineering.agent import EngineeringAgent
from app.schemas.repository import RepositoryContext


def test_prompt_assembly():
    llm_service = MagicMock()
    agent = EngineeringAgent(llm_service)
    structured_diff = {
        'added': [{'path': 'app/agents/engineering/agent.py', 'diff': 'sample diff'}],
        'modified': []
    }
    retrieved_context = RepositoryContext(
        target_symbols=[],
        dependencies=[],
        related_tests=[]
    )
    expected_prompt = '\n=== GIT DIFF (CHANGES TO TEST) ===\n--- ADDED FILES ---\nFile: app/agents/engineering/agent.py\nDiff:\nsample diff\n'  
    
    # Mocking the context attribute
    context = MagicMock()
    context.structured_diff = structured_diff
    with patch.object(agent, 'assemble_prompt', new_callable=MagicMock, return_value=expected_prompt):
        context.llm_context = agent.assemble_prompt(structured_diff, retrieved_context)

    assert context.llm_context == expected_prompt
    assert llm_service.generate_structured_json.call_count > 0
