# Phase 6: AI Quality Loop Implementation Context

This document provides technical context and architectural details regarding the implementation of **Phase 6: AI Quality Loop**.

## Objective
To transform the AI Software Delivery Engineer from a linear "fire-and-forget" generator into an adaptive system that executes generated code, measures coverage, critiques itself, and auto-corrects over multiple iterations until quality thresholds are met.

## Core Components

### 1. Deterministic Execution Services
Unlike the AI agents, these services are strictly deterministic Python sub-processes designed to execute local code safely without consuming LLM tokens.
- **`app/services/test_executor.py` (`TestExecutionService`)**:
  - Runs `subprocess.run(["pytest", "-q"])` in the cloned workspace.
  - Injects `PYTHONPATH=workspace_path` into the subprocess environment to prevent `ImportError` when generated tests attempt to load internal application modules.
  - Parses `stdout` to count passes/fails and extracts exit codes.
- **`app/services/coverage_service.py` (`CoverageService`)**:
  - Runs `subprocess.run(["pytest", "--cov=.", "--cov-report=json"])` in the workspace.
  - Parses the resulting `coverage.json` file.
  - Mathematically maps total lines, covered lines, and precisely which line numbers are missing coverage.

### 2. Autonomous Critique Agents
Specialized LLM agents that analyze the results of the execution services.
- **`app/agents/review/agent.py` (`ReviewAgent`)**:
  - Acts as a Senior Code Reviewer.
  - Analyzes the generated code strings for readability, proper mock usage, and assertion robustness.
  - Returns a boolean `approved` flag and a list of `weak_assertions`.
- **`app/agents/coverage/agent.py` (`CoverageAgent`)**:
  - Receives the raw missing line numbers from `CoverageService` and the `ChangeSummary`.
  - Deduces exactly *which* edge cases or scenarios from the `TestPlan` were missed based on the architectural gaps.

### 3. Iteration and Feedback Controllers
- **`app/workflows/feedback.py` (`FeedbackBuilder`)**:
  - Merges the `TestExecutionReport`, `ReviewReport`, and `CoverageGapReport`.
  - Determines if the iteration was a `CRITICAL` failure (tests crashed) or `HIGH` priority (coverage < 90%).
  - Produces a unified `GenerationFeedback` schema.
- **`app/workflows/iteration.py` (`IterationController`)**:
  - Evaluates the current `WorkflowContext`.
  - Returns `True` if regeneration is required (e.g., `failed > 0` or `coverage < 90.0`).
  - Returns `False` if thresholds are met OR if `max_iterations` (default: 3) is reached, acting as the failsafe against infinite loops.

### 4. Context Injection & Orchestration
- **`app/github/routes.py` (`run_ai_sde_workflow`)**:
  - Refactored the linear `stages` array into a `while True:` loop.
  - Executes `[TestGeneration, TestExecution, CoverageAnalysis]`.
  - Checks `IterationController`. If it fails, executes `[Review, Coverage, FeedbackBuilder]` and loops back.
- **`app/agents/test_generation/context_builder.py`**:
  - Dynamically inspects the `WorkflowContext` for existing `generation_feedback`.
  - If a previous iteration failed, it appends a critical `=== AI QUALITY LOOP FEEDBACK ===` block to the system prompt, forcing the LLM to patch the exact failed tests and coverage gaps.
- **`app/workflows/stages.py` (`GenerateDummyReportStage`)**:
  - Updated to append the AI Quality Loop metrics (Total Iterations, Final Pass Rate, Final Coverage) into the GitHub `AI_REPORT.md` pull request summary.

## Data Schemas (`app/schemas/quality.py`)
All internal communication between the loop stages is strongly typed using Pydantic:
- `TestExecutionReport`: Tracks duration, stdout, and parsed `passed`/`failed` counts.
- `CoverageReport`: Tracks line counts, percentage, and exact `missing_line_numbers`.
- `ReviewReport`: Boolean approval and explicit critique arrays.
- `CoverageGapReport`: Array of `missing_scenarios`.
- `GenerationFeedback`: The merged master object fed back into the generator.
