# AI Software Delivery Engineer: Current State

## Architecture Overview
The AI-SDE is a fully autonomous pipeline built with FastAPI. It intercepts GitHub webhook push events, clones target repositories, orchestrates a sequence of specialized AI agents to generate code and tests, recursively verifies its own work in a local workspace, and opens GitHub Pull Requests containing the validated code.

### Completed Phases

#### Phase 0: Project Foundation
- **Dependency Injection & Routing:** Modular FastAPI application structure.
- **Settings & Config:** Environment-based configuration via `pydantic-settings` (API keys, workspace paths).
- **LLM Service Wrapper:** Unified `LLMService` supporting multi-model fallback and strict structured JSON outputs. *Currently updated to natively support OpenRouter alongside Google GenAI SDK.*

#### Phase 1: GitHub Automation
- **GitService (`gitpython`):** Clones repositories locally, creates isolated `ai-sde/review-*` branches, commits changes, and pushes back to remote.
- **GitHubService (`PyGithub`):** Authenticates and automatically opens Pull Requests with the generated changes.

#### Phase 2: Workflow Orchestrator
- **WorkflowContext:** A strongly-typed state machine object tracking the progress, tokens, and metadata passed between agents.
- **Pipeline Abstraction:** Sequential execution of stateless `Stage` classes.

#### Phase 3: Repository Intelligence (Senior Architect Agent)
- **Diff & Metadata Extractors:** Gathers local Git diffs, analyzes the language and framework.
- **Context Builder:** Truncates excessive context and tokenizes only the modified code blocks.
- **Repository Understanding Agent:** Scans the codebase to deduce the business intent, affected modules, and the architecture of the modifications.

#### Phase 4: Test Planning (Senior QA Architect)
- **Test Planning Agent:** Consumes the architectural analysis.
- **Output:** Produces a highly structured `TestPlan` detailing unit, integration, negative, boundary, and security test scenarios required to cover the new code.

#### Phase 5: Test Generation (Senior SDET)
- **Test Generation Agent:** Ingests the `TestPlan` and `ChangeSummary`.
- **Output:** Produces raw code strings mapped to precise file paths.
- **WorkspaceWriter:** Safely injects the raw code strings into the locally cloned repository prior to commit.

#### Phase 6: AI Quality Loop (Test Execution, Coverage, and Self-Correction)
- **TestExecutionService:** Runs `subprocess("pytest")` dynamically in the cloned workspace, injecting `PYTHONPATH` to ensure generated Python tests can import target modules. Returns Pass/Fail execution reports.
- **CoverageService:** Runs `subprocess("pytest --cov --cov-report=json")` and mathematically parses the exact un-covered line numbers without consuming LLM tokens.
- **Review Agent:** Critiques the readability and robustness of the generated code (e.g., weak assertions).
- **Coverage Agent:** Correlates the missing lines of code against the repository architecture to deduce which specific scenarios were missed.
- **IterationController:** Evaluates execution and coverage metrics. If thresholds (<90% coverage or failing tests) are unmet, it dynamically rebuilds the LLM Context with the compiled Feedback Report and loops the Generation/Execution stages (up to 3 times) before terminating and pushing the PR.

---

## Known Behaviors & Operational Notes

1. **Webhook Concurrency:** 
   Currently, multiple simultaneous webhooks to the same repository cause race conditions because the local clone directory (e.g., `workspace/DeliveryOS`) is statically mapped to the repository name. *Pending fix in Phase 7: Append `commit_sha` to workspace directories.*
2. **OpenRouter Integration:**
   The `LLMService` utilizes OpenAI's structured output payload (`response_format: json_object`) when targeting OpenAI models, and gracefully strips it to rely purely on System Prompts when routing through Anthropic, Meta, or generic Gemini models to avoid `400 Bad Request` errors on OpenRouter.
3. **Execution Environment Dependencies:**
   Because Phase 6 strictly relies on `pytest` and `pytest-cov`, the target repository being analyzed *must* be a Python codebase. Non-Python repositories (e.g., Terraform) will trigger immediate exit code 2 crashes and loop out.
