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
