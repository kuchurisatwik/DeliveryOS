# DeliveryOS

An AI-powered autonomous software delivery engineer that watches your GitHub repository, generates tests for every push, validates them, self-repairs failures, and opens a Pull Request — all without human intervention.

---

## How It Works

```
GitHub Push → Webhook → Clone & Branch → Index Repo (AST → SQLite)
    → Decompose Commit into Feature Tasks
    → For each task:
        → Retrieve Context (symbols, deps, existing tests)
        → Assemble Focused Prompt (~15KB)
        → AI generates tests (Engineering Agent)
        → Validation Loop (up to 5 iterations):
            → Run pytest, check syntax, imports, coverage
            → If failing → AI rewrites entire file (Repair Agent)
            → Workspace Writer validates (AST, duplicates, size)
    → Score Merge Confidence
    → Commit → Push → Open Pull Request
```

## Architecture

```
app/
├── github/routes.py          # Webhook endpoint & workflow orchestration
├── agents/
│   ├── engineering/agent.py   # Unified AI agent (analysis + planning + generation)
│   └── repair/agent.py        # AI repair agent (reads failures, rewrites tests)
├── services/
│   ├── git_service.py         # Clone, diff, branch, commit, push
│   ├── github_service.py      # PR creation via GitHub API
│   ├── llm_service.py         # OpenRouter API calls (gpt-4o-mini)
│   ├── validators.py          # Syntax, import, test execution, coverage checks
│   ├── workspace_writer.py    # File I/O with AST/duplicate/size validation
│   └── repository/
│       ├── db.py              # SQLite schema for repo index
│       ├── indexer.py         # AST parser → SQLite indexer
│       ├── retriever.py       # Context retrieval from SQLite
│       ├── prompter.py        # Prompt assembly engine
│       └── planner.py         # Feature planner (commit → task queue)
├── workflows/
│   ├── orchestrator.py        # Sequential stage runner
│   ├── context.py             # Shared state (WorkflowContext)
│   ├── stages.py              # Git stages (clone, branch, commit, push, PR)
│   ├── intelligence_stages.py # Diff, index, retrieve, assemble stages
│   ├── engineering_stage.py   # Engineering agent stage
│   ├── quality_stages.py      # Validation & writer stages
│   ├── repair_stage.py        # Repair agent stage
│   └── iteration.py           # Iteration controller (stagnation detection)
├── schemas/                   # Pydantic models for all data structures
├── prompts/                   # Markdown prompt templates
└── config/settings.py         # Environment configuration
```

## Setup

### Prerequisites

- Python 3.12+
- Git
- A GitHub repository with webhook configured
- An [OpenRouter](https://openrouter.ai) API key

### Installation

```bash
git clone https://github.com/kuchurisatwik/ai-delivery.git
cd ai-delivery
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux
pip install -r requirements.txt
```

### Environment Variables

Create a `.env` file in the project root:

```env
GITHUB_TOKEN=ghp_your_github_personal_access_token
WEBHOOK_SECRET=your_webhook_secret
OPENROUTER_API_KEY=sk-or-your_openrouter_key
```

| Variable | Required | Description |
|----------|----------|-------------|
| `GITHUB_TOKEN` | Yes | GitHub PAT with `repo` scope for cloning, pushing, and PR creation |
| `WEBHOOK_SECRET` | No | Secret for HMAC signature verification (skip validation if unset) |
| `OPENROUTER_API_KEY` | Yes | API key for LLM calls via OpenRouter |

### Running

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Exposing to GitHub (Local Tunnel)

Since the app runs locally, you need a tunnel so GitHub can reach your webhook endpoint:

```bash
npx localtunnel --port 8000
```

Then configure your GitHub repository webhook:
- **Payload URL:** `https://your-subdomain.loca.lt/github/webhook`
- **Content type:** `application/json`
- **Events:** Push events

## Key Design Decisions

### "Search Engine, Not Chatbot"
Instead of dumping the entire repository into an LLM prompt, we index the codebase into SQLite using AST parsing, then deterministically retrieve only the symbols, dependencies, and test patterns relevant to the specific changed files. This keeps prompts under ~15KB.

### Feature Decomposition
A single commit touching 15 files across 5 features gets decomposed into 5 independent `EngineeringTask` objects. Each task gets its own isolated context retrieval and AI call, producing focused, high-quality tests instead of scattered, hallucinated ones.

### Full File Regeneration (Not Patching)
When the AI repair loop needs to fix a failing test, it rewrites the **entire file** from scratch rather than applying incremental search/replace patches. This prevents the duplicate code accumulation problem that plagued the earlier patch-based approach.

### Deterministic Validation Gates
Before any AI-generated file is written to disk, it passes through 4 hard gates:
1. Content is not empty
2. File is a `.py` file
3. File size hasn't shrunk by more than 50% (catches accidental deletion)
4. AST parses successfully with no duplicate top-level class/function definitions

### Stagnation Detection
If the repair loop's test pass count doesn't improve for 2 consecutive iterations, it aborts early instead of wasting API credits on the same failure.

## Running Tests

```bash
pytest tests/ -v
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/github/webhook` | GitHub webhook receiver |

## Tech Stack

| Component | Technology |
|-----------|-----------|
| Web Framework | FastAPI |
| LLM Provider | OpenRouter (gpt-4o-mini) |
| Git Operations | GitPython |
| GitHub API | PyGithub |
| Repository Index | SQLite + Python AST |
| Validation | pytest, pytest-cov |
| Schema Validation | Pydantic v2 |

## License

Private — All rights reserved.
