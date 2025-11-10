# ADK Documentation for AI Agents

This document provides essential information for an AI agent to build agents using the Agent Development Kit (ADK).

## Core Philosophy & Architecture

- **Code-First**: All agent logic, tools, and orchestration are defined in Python for versioning, testing, and IDE support.
- **Modularity & Composition**: Complex multi-agent systems are built by composing smaller, specialized agents.
- **Deployment-Agnostic**: An agent's core logic is separate from its deployment environment. The same agent definition can be run locally, served via an API, or deployed to the cloud.

## Foundational Abstractions

- **Agent**: The blueprint that defines an agent's identity, instructions, and tools. It is a declarative configuration object.
- **Tool**: A capability that an agent can call to interact with the world (e.g., a Python function for a search or an API call).
- **Runner**: The engine that orchestrates the "Reason-Act" loop, manages LLM calls, and executes tools.
- **Session**: The conversation state, holding the history for a single, continuous dialogue.
- **Memory**: Provides long-term recall for an agent across different sessions.
- **Artifact Service**: Manages non-textual data, such as files.

## Canonical Project Structure

To ensure compatibility with ADK tooling, all agent projects must follow this structure:

```
my_adk_project/
└── src/
    └── my_app/
        ├── agents/
        │   ├── my_agent/
        │   │   ├── __init__.py   # Must contain: from . import agent
        │   │   └── agent.py      # Must contain: root_agent = Agent(...)
        │   └── another_agent/
        │       ├── __init__.py
        │       └── agent.py
```

- **agent.py**: This file must define the agent and assign it to a variable named `root_agent`. This is how ADK's tools discover the agent.
- **`__init__.py`**: In each agent directory, this file must contain `from . import agent` to make the agent discoverable.

## Agent Definition

There are two primary ways to define an agent:

### Option 1 - Simple Agent

This pattern is for basic agents without plugins.

```python
from google.adk.agents import Agent
from google.adk.tools import google_search

root_agent = Agent(
    name="search_assistant",
    model="gemini-2.5-flash",
    instruction="You are a helpful assistant.",
    description="An assistant that can search the web.",
    tools=[google_search]
)
```

### Option 2 - App Pattern

This pattern is used when you need plugins, event compaction, or custom configuration.

```python
from google.adk import Agent
from google.adk.apps import App
from google.adk.plugins import ContextFilterPlugin

root_agent = Agent(
    name="my_agent",
    model="gemini-2.5-flash",
    instruction="You are a helpful assistant.",
    tools=[...],
)

app = App(
    name="my_app",
    root_agent=root_agent,
    plugins=[
        ContextFilterPlugin(num_invocations_to_keep=3),
    ],
)
```

## Agent's Thought Process

The ADK provides a way to view the agent's thought process, which can be useful for debugging and understanding how the agent is making decisions. This is done by using the `ThinkingConfig` object in the `BuiltInPlanner`.

To enable the thought process, you need to set the `include_thoughts` parameter to `True` in the `ThinkingConfig` object.

Here is an example of how to enable the thought process for an agent:

```python
from google.adk.agents import Agent
from google.adk.planners.built_in_planner import BuiltInPlanner
from google.genai import types

root_agent = Agent(
    name="thinking_agent",
    model="gemini-2.5-flash",
    instruction="You are a helpful assistant.",
    planner=BuiltInPlanner(
        thinking_config=types.ThinkingConfig(
            include_thoughts=True,
        ),
    ),
)
```

When you run an agent with the thought process enabled, you will see the agent's thoughts in the output. This can help you to understand how the agent is interpreting the user's input and how it is choosing which tools to use.

**Note on model compatibility:** With newer models, such as Gemini 2.5, "thinking" is a default and constant feature. In these cases, explicitly setting `thinking_config` may not be necessary and could even cause errors. The `ThinkingConfig` is still useful for older models, and you can experiment with it if you are using a different model.

## Custom Tool Definition

You can create custom tools by wrapping a Python function with the `FunctionTool` class. This allows you to extend the capabilities of your agents with your own logic.

```python
from google.adk.tools import FunctionTool

def my_custom_function(param1: str, param2: int) -> str:
    """
    This is a custom tool that does something cool.

    Args:
        param1: The first parameter.
        param2: The second parameter.

    Returns:
        A string with the result.
    """
    # Your tool logic here
    return f"Result: {param1}, {param2}"

my_custom_tool = FunctionTool(my_custom_function)

# You can then add this tool to your agent's tool list
# root_agent = Agent(..., tools=[my_custom_tool])
```

## Running Agents Locally

- **Interactive UI (adk web)**: The primary tool for debugging. It provides a web-based UI to inspect the full execution trace of your agent.
  ```bash
  adk web path/to/your/agent/directory
  ```
- **CLI (adk run)**: For quick, stateless functional checks in the terminal.
  ```bash
  adk run path/to/your/agent
  ```
- **API Server (adk api_server)**: To expose your agent as a production-ready API using FastAPI.
  ```bash
  adk api_server path/to/your/agent/directory
  ```

## Deployment

The ADK provides a command-line interface to deploy your agents to Google Cloud Run or Vertex AI Agent Engine.

```bash
adk deploy
```

## Session Management

The `Session` object holds the conversation state. You can access it within your tools to get information about the current conversation. The `tool_context` parameter provides access to the session.

```python
from google.adk.tools import FunctionTool, ToolContext

def my_tool_with_session_access(tool_context: ToolContext) -> str:
    """
    A tool that accesses the session.
    """
    session_id = tool_context.session_id
    # You can access the full history of events in the session
    # events = tool_context.session.list_events()
    return f"The current session ID is: {session_id}"

my_session_tool = FunctionTool(my_tool_with_session_access)
```

## Memory

The `Memory` object provides long-term recall for an agent across different sessions. You can use the `load_memory_tool` and `preload_memory_tool` to interact with the memory.

```python
from google.adk.agents import Agent
from google.adk.tools import load_memory_tool, preload_memory_tool

# This tool allows the agent to load information from memory during a conversation
load_memory = load_memory_tool()

# This tool allows you to preload information into memory before a conversation starts
preload_memory = preload_memory_tool()

root_agent = Agent(
    name="memory_agent",
    model="gemini-2.5-flash",
    instruction="You are an agent with memory.",
    tools=[load_memory, preload_memory]
)
```

## Testing & Evaluation

- **Unit Tests**: Test individual `Tool` functions in isolation using `pytest`.
- **Integration Tests**: Test the agent's internal logic and interaction with tools, often with mocked LLMs or services.
- **Evaluation Tests**: Assess end-to-end performance with a live LLM using the ADK Evaluation Framework.

## Advanced Extensibility

The ADK provides several ways to extend its functionality to meet the specific needs of your application.

### Plugins

Plugins provide a structured way to intercept and modify agent, tool, and LLM behaviors at critical execution points in a callback manner. They are ideal for adding custom behaviors like logging, monitoring, caching, or modifying requests and responses at key stages.

To create a plugin, you need to create a class that inherits from `BasePlugin` and implement one or more of the available callback methods.

Here is an example of a simple plugin that logs every tool call:

```python
from google.adk.plugins import BasePlugin
from google.adk.tools import BaseTool, ToolContext
from typing import Any

class ToolLoggerPlugin(BasePlugin):
    def __init__(self):
        super().__init__(name="tool_logger")

    async def before_tool_callback(
        self, *, tool: BaseTool, tool_args: dict[str, Any], tool_context: ToolContext
    ):
        print(f"[{self.name}] Calling tool '{tool.name}' with args: {tool_args}")

    async def after_tool_callback(
        self, *, tool: BaseTool, tool_args: dict, tool_context: ToolContext, result: dict
    ):
        print(f"[{self.name}] Tool '{tool.name}' finished with result: {result}")

# To use this plugin, you would add it to your App object:
# app = App(..., plugins=[ToolLoggerPlugin()])
```

### Middleware

Middleware allows you to intercept and modify the Reason-Act loop itself. This is a powerful feature that can be used to implement custom logic that is not tied to a specific agent or tool.

### LifeCycleHooks

LifeCycleHooks are callbacks for specific events in the agent's lifecycle, such as `on_session_start`. They can be used to perform actions at specific points in the conversation.

## Examples

### Single Agent Example

```python
from google.adk.agents import Agent
from google.adk.tools import google_search

root_agent = Agent(
    name="search_assistant",
    model="gemini-2.5-flash", # Or your preferred Gemini model
    instruction="You are a helpful assistant. Answer user questions using Google Search when needed.",
    description="An assistant that can search the web.",
    tools=[google_search]
)
```

### Multi-Agent System Example

```python
from google.adk.agents import LlmAgent

# Define individual agents
greeter = LlmAgent(name="greeter", model="gemini-2.5-flash", instruction="You are a friendly greeter.")
task_executor = LlmAgent(name="task_executor", model="gemini-2.5-flash", instruction="You are a task execution agent.")

# Create a parent agent to coordinate the sub-agents
coordinator = LlmAgent(
    name="Coordinator",
    model="gemini-2.5-flash",
    description="I coordinate greetings and tasks.",
    sub_agents=[
        greeter,
        task_executor
    ]
)
```
