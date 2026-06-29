# DeliveryOS: End-to-End System Flow

This document outlines the current architecture of the DeliveryOS AI-SDE pipeline. The system operates as a state machine orchestrated by `WorkflowOrchestrator`, passing a shared `WorkflowContext` between distinct, single-responsibility `Stage` classes.

---

## High-Level Pipeline Orchestration

The pipeline is triggered via a GitHub Webhook (`POST /github/webhook`). The webhook launches a background task that executes the `WorkflowOrchestrator`.

```mermaid
graph TD
    Webhook[GitHub Webhook Event] --> Orchestrator
    
    subgraph Workflow Orchestrator
    Orchestrator --> P1[Phase 1: Setup & Context]
    P1 --> P2[Phase 2: Generation]
    P2 --> P3[Phase 3: Validation & Repair Loop]
    P3 --> P4[Phase 4: Delivery]
    end
```

---

## Phase 1: Setup & Context
**Goal:** Prepare the local workspace and gather all necessary code context before invoking the LLM.

```mermaid
graph TD
    Start[Phase 1 Start] --> S1[CloneRepositoryStage]
    
    subgraph CloneRepositoryStage
        S1 --> G1[GitService.clone_repository]
        G1 --> ContextWorkspace[Update Context: workspace_path]
    end
    
    ContextWorkspace --> S2[ContextBuilderStage]
    
    subgraph ContextBuilderStage
        S2 --> G2[GitService.get_changed_files]
        G2 --> G3[GitService.get_commit_diff]
        G3 --> K1[RepositoryKnowledgeAggregator.build_or_load]
        K1 --> AstExt[AstPythonExtractor.extract]
    end
    
    AstExt --> S3[CreateBranchStage]
    
    subgraph CreateBranchStage
        S3 --> G4[GitService.create_branch]
    end
    
    G4 --> End[Phase 1 Complete]
```

---

## Phase 2: Test Generation
**Goal:** Analyze the git diff and generate an initial suite of tests focused entirely on the business logic that changed.

```mermaid
graph TD
    Start[Phase 2 Start] --> S4[EngineeringAgentStage]
    
    subgraph EngineeringAgentStage
        S4 --> EA[EngineeringAgent.conduct_session]
        EA --> Prompt[Build bottom-heavy prompt]
        Prompt --> LLM[LLMService.generate_structured_json]
        LLM --> CheckEmpty{Generated Files Empty?}
        CheckEmpty -- Yes --> Retry[Force Retry]
        Retry --> LLM
        CheckEmpty -- No --> WW[WorkspaceWriterService.write_artifact]
        
        WW --> AST[ast.parse pre-validation]
        AST --> Disk[Write valid files to Disk]
    end
    
    Disk --> End[Phase 2 Complete]
```

---

## Phase 3: Validation & Repair Loop
**Goal:** Ensure the generated tests are syntactically correct, importable, pass execution, and provide adequate coverage. If not, trigger the Repair Agent to patch the test files.

```mermaid
graph TD
    Start[Phase 3 Start] --> LoopStart{Iteration < Max}
    
    LoopStart -- Yes --> V[ValidationEngineStage]
    
    subgraph ValidationEngineStage
        V --> VE[ValidationEngine.run_all]
        VE --> Syn[SyntaxValidationService.validate]
        VE --> Imp[ImportValidationService.validate]
        Imp --> |If Build Passes| Exec[TestExecutionService.run_tests]
        Exec --> Cov[CoverageService.run_coverage]
    end
    
    Cov --> IC[IterationController.should_improve]
    
    subgraph IterationController
        IC --> BBroken{Build Broken?}
        BBroken -- Yes --> TriggerRepair[Return True]
        BBroken -- No --> TFailed{Tests Failed?}
        TFailed -- Yes --> StagCheck{Stagnation?}
        StagCheck -- Yes --> AbortRepair[Return False]
        StagCheck -- No --> TriggerRepair
        TFailed -- No --> CovCheck{Coverage < Target?}
        CovCheck -- Yes --> TriggerRepair
        CovCheck -- No --> AbortRepair
    end
    
    TriggerRepair --> R[RepairAgentStage]
    AbortRepair --> End[Phase 3 Complete]
    
    subgraph RepairAgentStage
        R --> RA[RepairAgent.conduct_session]
        RA --> FormatHist[Format Iteration History]
        FormatHist --> FormatFail[Format Failure Summary]
        FormatFail --> R_LLM[LLMService.generate_structured_json]
        R_LLM --> Filter[Drop non-test patches]
    end
    
    Filter --> W[WorkspacePatchStage]
    
    subgraph WorkspacePatchStage
        W --> WP[WorkspacePatchService.apply_patches]
        WP --> NewFileCheck{Is New File?}
        NewFileCheck -- Yes --> AST1[ast.parse]
        NewFileCheck -- No --> AppendReplace[Apply Diff]
        AppendReplace --> AST2[ast.parse]
        AST1 -- Passes --> Save[Write to Disk]
        AST2 -- Passes --> Save
    end
    
    Save --> LoopStart
    LoopStart -- No --> End
```

---

## Phase 4: Delivery
**Goal:** Generate a final report, commit the new tests, push to the remote, and open a Pull Request.

```mermaid
graph TD
    Start[Phase 4 Start] --> S8[GenerateDummyReportStage]
    
    subgraph GenerateDummyReportStage
        S8 --> IO[Write AI_REPORT.md to Workspace]
    end
    
    IO --> S9[CommitStage]
    
    subgraph CommitStage
        S9 --> G5[GitService.commit_changes]
        G5 --> G5_Add[git add A=True]
        G5_Add --> G5_Commit[git commit -m]
    end
    
    G5_Commit --> S10[PushBranchStage]
    
    subgraph PushBranchStage
        S10 --> G6[GitService.push_branch]
        G6 --> G6_Push[origin.push]
        G6_Push --> G6_FailCheck{Success?}
        G6_FailCheck -- No --> G6_Exception[Raise Exception]
    end
    
    G6_FailCheck -- Yes --> S11[CreatePullRequestStage]
    
    subgraph CreatePullRequestStage
        S11 --> GH[GithubService.create_pull_request]
        GH --> GH_API[POST to GitHub API]
    end
    
    GH_API --> End[Workflow Complete]
    G6_Exception --> End
```

---

## Core Dependencies and Data Transfer

### 1. The `WorkflowContext` Object
All stages are completely stateless. The only state is passed around inside the `WorkflowContext` dataclass, which grows as the pipeline progresses:
- **Phase 1 adds:** `workspace`, `changed_files`, `structured_diff`, `llm_context`
- **Phase 2 adds:** `engineering_session`, `generated_tests`, `workspace_changes`
- **Phase 3 updates:** `validation_report`, `iteration_count`, `iteration_history`, `merge_confidence`
- **Phase 4 uses:** The finalized context to build the PR description.

### 2. The `LLMService` (The AI Engine)
Both `EngineeringAgent` and `RepairAgent` strictly rely on `LLMService.generate_structured_json()`.
- Model is hardcoded to `openai/gpt-4o-mini`.
- Native `json_object` response format is mandated.
- Output is automatically mapped to strictly typed Pydantic models (e.g., `EngineeringSessionSchema`, `RepairSessionSchema`).
- Caching is enabled for Engineering but explicitly bypassed (`skip_cache=True`) for Repair loops to prevent poisoning.
