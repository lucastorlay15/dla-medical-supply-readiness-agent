# Project Instructions

These instructions apply to all agents working in this repository.

## Running Shell Commands In Project

**IMPORTANT**: All shell commands must be executed from the project root directory.

## Run Project Locally

Run the following shell commands to run the project locally (agent + backend + frontend)

```shell
dr run dev
```

# Agent Development Instructions


> **Framework (NAT):** See [docs/agent/frameworks/nat.md](../docs/agent/frameworks/nat.md), the [custom-tool checklist](../docs/agent/frameworks/nat.md#checklist-every-custom-nat_tool-must-appear-in-functions-do-not-skip), and [NAT `workflow.yaml` requirements](../docs/agent/frameworks/nat.md#nat-workflowyaml-requirements-read-this-first). Each `nat_tool` needs a matching `functions` entry in `workflow.yaml` and its name in `workflow.tool_names`. The generated template ships a blog tool-calling workflow (`planner`, `writer`, `mcp_tools`); for a tool-less assistant, follow [Tool-less `chat_completion` workflow](#tool-less-chat_completion-workflow) below. When implementing from `agent_spec.md`, every `workflow.yaml` edit must be **syntactically valid YAML** (see §3). The template imports `agent.register` from `myagent.py` so new `nat_tool` registrations run at import time; you can move that import to `agent/__init__.py` if you prefer.


## Dependencies Installation

The following command should be run after agent code modification:

```shell
dr task run agent:install
```

> **Warning:** When using a custom Docker context (`DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT` is unset and an `agent/docker_context/` folder is present), modifying `pyproject.toml` or `uv.lock` triggers a full execution environment rebuild on the next deployment. This rebuild can take **10–20 minutes** depending on the number of dependencies. When using the default DataRobot execution environment (the default configuration), dependency changes do not trigger a rebuild.

## Agent Structure

Agent application code must be implemented in the `agent/agent` directory. The NAT orchestration file `workflow.yaml` lives at the agent component root (`agent/workflow.yaml`), not inside `agent/agent/`. NAT framework agents require that file.

For detailed documentation, see [docs/agent/README.md](../docs/agent/README.md). When upgrading layouts that still have `agent/agent/workflow.yaml`, see [workflow.yaml path migration](../docs/agent/migration-workflow-yaml-path.md).



Agent must implement the following components:

### 1. Class Definition

```python
from pathlib import Path

from datarobot_genai.nat.agent import NatAgent

import agent.register  # noqa: F401 - matches generated myagent.py; ensures nat_tool side effects load

class MyAgent(NatAgent):
    def __init__(
        self,
        *args,
        workflow_path: Path = Path(__file__).parent.parent / "workflow.yaml",
        **kwargs,
    ):
        super().__init__(*args, workflow_path=workflow_path, **kwargs)
```

**Important**: `MyAgent` class should NOT be renamed!

### 2. Agent Workflow

All agent logic is defined declaratively in `workflow.yaml`. Functions, LLMs, tools, and orchestration are all configured in YAML:

```yaml
functions:
  planner:
    _type: chat_completion
    llm_name: datarobot_llm
    system_prompt: |
      You are a content planner...

workflow:
  _type: per_user_tool_calling_agent
  llm_name: datarobot_llm
  tool_names:
    - planner
    - writer
    - mcp_tools
  system_prompt: |
    You are a blog content orchestrator...
```

### 3. Tool-less `chat_completion` workflow

The default `agent/workflow.yaml` uses a `per_user_tool_calling_agent` with `planner`, `writer`, and `mcp_tools`. **NAT rejects an empty `tool_names` list on tool-calling workflows** — if you do not need built-in or MCP tools, replace that layout with a root `chat_completion` workflow (edit `workflow.yaml` directly; do not leave `tool_names: []` on a tool-calling type).

**YAML:** Whenever you generate or change `agent/workflow.yaml`, write **syntactically valid YAML** only: double-quote strings that contain special characters (`?`, `:`, `#`, commas); prefer block lists (`- item`) over inline `[...]` sequences; keep indentation consistent. Do not add `examples` from `agent_spec.md` — omit `skills[].examples` and any other example blocks. After editing, re-read the full file and confirm it would parse as YAML with no syntax errors before `dr run dev`. NAT workflow schema rules are in [NAT `workflow.yaml` requirements](../docs/agent/frameworks/nat.md#nat-workflowyaml-requirements-read-this-first).

**Steps:**

1. Remove the entire `functions:` block (`planner`, `writer`, and any other function entries).
2. Remove `function_groups:` (including `mcp_tools` and `datarobot_mcp_auth` if unused).
3. Keep `authentication.datarobot_auth`, `llms`, and `general`; set `workflow.system_prompt` and A2A name/description/skills from `agent_spec.md`. Omit `examples` — do not add `skills[].examples` or other example blocks.
4. Replace the `workflow:` section with:

```yaml
workflow:
  _type: chat_completion
  llm_name: datarobot_llm
  system_prompt: |
    You are a helpful assistant. Answer clearly and concisely. Use markdown when it improves readability.
```

When updating `general.front_end.a2a`, set name, description, and skills from `agent_spec.md` but omit `examples` — do not add `skills[].examples` or other example blocks (see **YAML** above). Re-read `agent/workflow.yaml` for parse errors before `dr run dev`.

### 4. Custom Tools

Register custom Python tools by calling **`nat_tool(fn, tool_name, ...)`** from `datarobot_genai.dragent.tool` at module level in `register.py` (not `@nat_tool()` with no arguments). For **each** tool name, add a matching `functions.<name>` entry in `workflow.yaml` with `_type: <name>` and a `description`, include the name in `workflow.tool_names`, and ensure `register.py` is imported (see class definition above). In `agent/tools.py`, avoid `from __future__ import annotations` together with `dict[str, Any]` return types on multi-parameter tools — NAT fails at runtime with `NameError: name 'Any' is not defined` (see [NAT workflow.yaml requirements](../docs/agent/frameworks/nat.md#nat-workflowyaml-requirements-read-this-first)). See the [checklist](../docs/agent/frameworks/nat.md#checklist-every-custom-nat_tool-must-appear-in-functions-do-not-skip) and [Custom local tools](../docs/agent/frameworks/nat.md#custom-local-tools) in [docs/agent/frameworks/nat.md](../docs/agent/frameworks/nat.md).

For detailed NAT documentation, see [docs/agent/frameworks/nat.md](../docs/agent/frameworks/nat.md).

## Agent Testing

Review and update the tests in the `agent/tests` directory after code changes were made to the agent.
Run the following shell commands to run the tests:

```shell
dr task run agent:lint
```

```shell
dr task run agent:test
```

## Post Deployment Validation

Run the following shell command to validate the agent after deployment. If the response has no errors then the deployment is successful.

```shell
dr task run agent:cli -- -- execute-deployment --user_prompt "Agent specific prompt to validate that it's working" --deployment_id <deployment_id>
```

## Setting up custom metric and report values

Refer to [Custom metrics](../docs/agent/custom-metrics.md) page for how to set up and report values to custom metrics.

## Migrations

### 11.9.3 — `workflow.yaml` location

Agent component 11.9.3 moved `workflow.yaml` from `agent/agent/workflow.yaml` to `agent/workflow.yaml`. NAT framework agents load this file. See [workflow.yaml path migration](../docs/agent/migration-workflow-yaml-path.md).

### 11.8.8 — New agent format (class-based → factory-based)

Starting with agent component version 11.8.8 ([af-component-agent#474](https://github.com/datarobot-community/af-component-agent/pull/474)), agent templates (except `base`) no longer require defining agents within a `MyAgent` class. Agents are now defined using native framework primitives at module level and converted to `MyAgent` via a helper function (`datarobot_agent_class_from_*`). The LLM is also decoupled from the agent class and injected via `get_llm()`.

If you are upgrading an existing agent from a version prior to 11.8.8, follow the migration guide for your framework:

- [LangGraph migration](../docs/agent/frameworks/migration-to-11.8.8-langgraph.md)
- [CrewAI migration](../docs/agent/frameworks/migration-to-11.8.8-crewai.md)
- [LlamaIndex migration](../docs/agent/frameworks/migration-to-11.8.8-llamaindex.md)
- [Base agent migration](../docs/agent/frameworks/migration-to-11.8.8-base.md)
- [NAT agent migration](../docs/agent/frameworks/migration-to-11.8.8-nat.md)
- [workflow.yaml path migration (11.9.3)](../docs/agent/migration-workflow-yaml-path.md)
# MCP Server Development Instructions

The MCP server MUST be implemented in the `mcp_server/` directory.
By default it provides tools for DataRobot operations, but can be extended with custom tools for any domain.

## MCP Server Development Guidelines

IMPORTANT: Do NOT import code from `agent/` or `fastapi_server/` directories. The MCP server has independent dependencies to avoid conflicts. 
IMPORTANT: The MCP server runs as an independent service. Agents connect to it via MCP protocol (HTTP), not direct Python imports.

- You may modify files ONLY inside `mcp_server/` directory.
- The MCP server is a standard FastMCP application:
  * Tools live in `mcp_server/app/tools/`
  * Prompts live in `mcp_server/app/prompts/`
  * Resources live in `mcp_server/app/resources/`
  * Configuration is in `mcp_server/app/core/`
  * Tests are in `mcp_server/app/tests/`
- Read `mcp_server/docs` to further understand the existing structure.

## Tool Development Architecture

The MCP server uses auto-discovery for tools:

1. **Tool Definition** (`mcp_server/app/tools/{domain}_tools.py`): Define tools with `@dr_mcp_tool` decorator
2. **Auto-Discovery**: Server automatically loads all tools from `mcp_server/app/tools/` on startup
3. **MCP Protocol**: Agents discover and call tools via HTTP (no imports needed)

**When adding new tools:**
- Create tool functions in `app/tools/{domain}_tools.py`
- Use `@dr_mcp_tool(tags={"category", "action"})` decorator
- Define parameters with `Annotated[type, "description"]`
- Return `ToolResult(structured_content={...})`
- Tools are automatically discovered - no registration needed

**CRITICAL - Tool Implementation Requirements:**

All tool functions MUST be `async def` and return `ToolResult`. Example:

```python
from typing import Annotated
from datarobot_genai.drmcp import dr_mcp_tool
from fastmcp.tools.tool import ToolResult

@dr_mcp_tool(tags={"domain", "action"})
async def tool_name(
    param: Annotated[str, "Parameter description for LLM"],
) -> ToolResult:
    """
    Tool description that the LLM will see.
    Be clear and specific about what the tool does.
    """
    # Your implementation here
    result = {"key": "value"}
    return ToolResult(structured_content=result)
```

## MCP Server Security

- NEVER hardcode API keys or secrets in tool code. Use environment variables or runtime parameters.
- Store credentials in `.env` file (never commit to git)
- Access config via `app/core/user_config.py`
- Use DataRobot credentials management for production deployments

## Installing MCP Server packages

Before making any changes to the mcp_server code, install dependencies by running shell command:

```shell
dr task run mcp_server:install
```

## MCP Server Testing

```shell
dr task run mcp_server:lint
```

```shell
dr task run mcp_server:test
```

# Backend Development Instructions

The agent application template includes a backend implementation in `fastapi_server/`.
By default it ships a backend implementing APIs endpoints for the frontend application.

## Backend Development Guidelines

- The FastAPI backend in `fastapi_server/` already serves the chat API at `/api/v1/`.
  If the user's frontend needs new data endpoints, add them in `fastapi_server/app/api/v1/`.
- The entry point for the backend can be found at `fastapi_server/app/main.py`
- For POST endpoints accepting JSON body, use Pydantic models (not function parameters). Query params go in function signature, body params go in Pydantic model.

## Application persistence

`USE_APPLICATION_MEMORY_SPACE` controls where the FastAPI backend stores application data: chats, messages, OAuth identities, and user profiles. It is separate from agent-side memory runtime parameters on the agent deployment.

> [!NOTE]
> `USE_APPLICATION_MEMORY_SPACE=true` is currently experimental.

| Setting | Persistence | Provisioned by |
|---------|-------------|--------------|
| `false` (default) | SQLite (`database_uri` in `fastapi_server/app/config.py`) | Local file at `.data/database.sqlite` |
| `true` | DataRobot Memory Space (`APPLICATION_MEMORY_SPACE_ID`) | Pulumi in `infra/infra/fastapi_server.py` |

To enable Memory Space persistence:

1. Ensure the organization has agentic memory API access (`ENABLE_AGENTIC_MEMORY_API`).
2. Set `USE_APPLICATION_MEMORY_SPACE=true` in the project `.env` (see `.env.template`).
3. Run `task deploy-dev`. Pulumi provisions a memory space and wires `USE_APPLICATION_MEMORY_SPACE` and `APPLICATION_MEMORY_SPACE_ID` on the FastAPI custom application runtime (not the agent deployment).
4. After changing this flag, rerun `task deploy-dev` before `task dev` so infrastructure and runtime parameters stay in sync with `.env`.

Repository wiring happens in `fastapi_server/app/deps.py`: when both the flag and `APPLICATION_MEMORY_SPACE_ID` are set, Memory Space repositories are used; otherwise SQLite repositories are used. API and service code should depend on the `*RepositoryLike` types in `fastapi_server/app/repo_types.py`, not concrete implementations.

### Which files to edit

**Configuration and infrastructure** (any change to the flag or provisioning):

- `.env` / `.env.template` — set `USE_APPLICATION_MEMORY_SPACE`
- `fastapi_server/app/config.py` — runtime parameter definitions
- `infra/infra/fastapi_server.py` — Pulumi Memory Space provisioning and runtime parameter wiring

**When `USE_APPLICATION_MEMORY_SPACE=false` (SQLite)** — edit SQLite-backed repositories and schema:

- `fastapi_server/app/chats/__init__.py` — `Chat` model and `ChatRepository`
- `fastapi_server/app/messages/__init__.py` — `Message` model and `MessageRepository`
- `fastapi_server/app/users/user.py` — `User` model and `UserRepository`
- `fastapi_server/app/users/identity.py` — identity model and `IdentityRepository`
- `fastapi_server/migrations/` — Alembic migrations for schema changes
- `fastapi_server/app/db.py` — database context (only if changing DB behavior)

**When `USE_APPLICATION_MEMORY_SPACE=true` (Memory Space)** — edit Memory Space-backed repositories:

- `fastapi_server/app/memory/repos.py` — `MemoryChatRepository`, `MemoryMessageRepository`
- `fastapi_server/app/memory/user_repos.py` — `MemoryUserRepository`
- `fastapi_server/app/memory/identity_repos.py` — `MemoryIdentityRepository`
- `fastapi_server/app/memory/registry.py`, `user_registry.py`, `identity_registry.py` — session registries
- `fastapi_server/app/memory/metadata_keys.py`, `participant.py` — metadata keys and participant IDs

**Shared regardless of setting** — edit when adding or changing persisted entities:

- `fastapi_server/app/deps.py` — wire the correct repository implementation
- `fastapi_server/app/repo_types.py` — union types consumed by API and services
- `fastapi_server/app/api/v1/` — use `*RepositoryLike` types from `deps`, not SQLite- or Memory-specific classes

**Tests:**

- SQLite path: `fastapi_server/tests/ag_ui/test_storage.py` and other tests using in-memory SQLite fixtures
- Memory space path: `fastapi_server/tests/memory/`
- End-to-end memory space behavior: `tests/e2e/test_memory.py` (requires `USE_APPLICATION_MEMORY_SPACE=true`)

When adding a new persisted entity, implement both a SQLite repository (with migration) and a Memory Space repository, then register both in `deps.py` and `repo_types.py`. See [docs/fastapi_server/README.md](../docs/fastapi_server/README.md) for setup details.

## Installing backend packages

Before making any changes to the backend code, install dependencies by running shell command:

```shell
dr task run fastapi_server:install
```

## Backend Testing

```shell
dr task run fastapi_server:lint
```

```shell
dr task run fastapi_server:test
```

# Frontend Development Instructions

The agent application frontend MUST be implemented in the following location withing the `frontend_web/`.
The technology stack is TypeScript + React + Vite + Tailwind CSS + shadcn/ui.
By default it ships a chat UI, but it can reimplemented to contain dashboards, multi-page apps, or other custom UIs.

## Frontend Development Guidelines

IMPORTANT: Do NOT replace this stack with a different framework (e.g. Next.js, Vue, Angular, Svelte). If the user asks to switch frameworks, because deployment pipeline and infrastructure depend on the current stack. 
IMPORTANT: The frontend depends on backend API endpoints and agent tool outputs being in place.

- You may modify files ONLY inside `frontend_web/` and `fastapi_server/` for the frontend work.
- The frontend is a standard Vite + React + TypeScript project:
  * Pages live in `frontend_web/src/pages/`
  * Routes are defined in `frontend_web/src/routesConfig.tsx`
  * Reusable components are in `frontend_web/src/components/`
  * UI primitives (shadcn/ui) are in `frontend_web/src/components/ui/`
  * API hooks and requests are in `frontend_web/src/api/`
  * Theming is in `frontend_web/src/theme/`
- Read `frontend_web/README.md` to further understand the existing structure.

### API Architecture

The frontend uses a three-layer architecture for API calls:

1. **API Client** (`src/api/apiClient.ts`): Pre-configured axios instance with base URL
2. **API Requests** (`src/api/{feature}/api-requests.ts`): Functions that make HTTP calls using `apiClient`
3. **React Query Hooks** (`src/api/{feature}/hooks.ts`): Hooks that wrap requests with React Query for caching/state
4. **Pages**: Import and use the hooks

**When adding new API endpoints:**
- Create request functions in `src/api/{feature}/api-requests.ts` using `apiClient` (MUST use default import: `import apiClient from '@/api/apiClient'`)
- Wrap them in React Query hooks in `src/api/{feature}/hooks.ts`
- Import and use the hooks in your pages/components
- Never call `fetch()` or create new axios instances - always use the configured `apiClient`

**CRITICAL - API Path Requirements:**

`apiClient` is already configured with `baseURL` that includes `/api`. Therefore:

Including `/api` in the path will cause **double `/api/api/` URLs** and result in 404/405 errors.

## Frontend  Security
- NEVER embed API keys, secrets, or credentials in frontend code. If the frontend needs to call
  external services, route those calls through `fastapi_server/` endpoints. Do not make direct external API
  calls from browser-side code as this exposes secrets and creates CORS issues.

## Installing frontend packages

Before making any changes to the frontend code, install dependencies (npm packages) by running shell command:

```shell
dr task run frontend_web:install
```

- To install new npm packages, use shell to run `npm install <package>` from the `frontend_web/` directory.

## Installing shadcn/ui components

**CRITICAL**: Before writing ANY code that imports a shadcn/ui component, you MUST first verify the component file exists.

**MANDATORY WORKFLOW:**
1. **BEFORE** writing any import statement for a shadcn/ui component (e.g. `Select`, `Tabs`, `Table`, `Popover`, `DatePicker`, `Dialog`, `Accordion`, etc.)
2. Check if the file exists: `frontend_web/src/components/ui/{component}.tsx`
3. If the file does NOT exist, you MUST run: `npx --yes shadcn@latest add {component} --overwrite` from the `frontend_web/` directory
4. Wait for the installation to complete
5. ONLY THEN write code that imports the component

## Frontend Testing

```shell
dr task run frontend_web:lint
```

```shell
dr task run frontend_web:test
```

## Project Deployment

Run the following shell commands to deploy the project:

```shell
dr task run infra:up-yes
```

In case the deployment process fails, you can try deleting it by running the following command:

```shell
dr task run infra:down-yes
```

## Local Development

One-time setup (deploys backing infrastructure):

```shell
dr start
```

## Pre-deploy Checklist

Before running `dr task run infra:up-yes`, ask the user to ensure their environment is configured. The following variables must be set:

- `DATAROBOT_API_TOKEN` and `DATAROBOT_ENDPOINT`
- `PULUMI_CONFIG_PASSPHRASE`
- `SESSION_SECRET_KEY` (required if using the FastAPI component)
- `DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT` (required if your agent uses a custom execution environment)

If the user hasn't set up their environment yet, ask them to run:

```shell
dr start
```

or

```shell
dr dotenv setup
```

## Troubleshooting

**Deploy exits with code 1 but a Custom Application URL appears in the output**
The app is live — the non-zero exit came from a post-deploy cleanup step, not the app itself. Run the following to reconcile Pulumi state:

```shell
dr task run infra:refresh -- -y
```

Do not re-deploy.

**422 error when deleting ApplicationSource**
The source is still attached to a live application. Reconcile Pulumi state and retry:

```shell
dr task run infra:refresh -- -y
```

**Docker context error on first deploy**
Set `DATAROBOT_DEFAULT_EXECUTION_ENVIRONMENT` in your `.env` file to point to an existing execution environment.

**Container fails to install dependencies at startup**
If your app depends on a local package (e.g. `core/`), ensure it is included in the application bundle before deploying.

## Expected Deploy Times

| Operation | Duration |
|---|---|
| First deploy | ~10–15 min |
| Re-deploy | ~5–10 min |
| `task refresh` | ~1–2 min |
