from __future__ import annotations

import logging
import sqlite3
import uuid
from typing import TYPE_CHECKING, Any, Callable, Optional

from weave.flow.util import warn_once
from weave.trace.context import weave_client_context
from weave.trace.weave_client import Call

if TYPE_CHECKING:
    from autogen import Agent, ConversableAgent, OpenAIWrapper
    from autogen.logger.base_logger import LLMConfig
    from openai import AzureOpenAI, OpenAI
    from openai.types.chat import ChatCompletion

try:
    from autogen.logger.base_logger import BaseLogger
except ImportError:
    # If ag2 is not installed, create a stub BaseLogger
    class BaseLogger:
        pass


logger = logging.getLogger(__name__)


class WeaveLogger(BaseLogger):
    """A logger for ag2 that forwards all logging calls to Weave for tracing.

    This logger implements ag2's BaseLogger interface and can be passed to
    autogen.runtime_logging.start(logger=weave_logger) to enable Weave tracing.

    Example:
        import weave
        import autogen
        from weave.integrations.ag2 import WeaveLogger

        # Initialize weave
        weave.init("my-project")

        # Create weave logger and start ag2 logging
        weave_logger = WeaveLogger()
        session_id = autogen.runtime_logging.start(logger=weave_logger)

        # Your ag2 code - now traced with weave!
        assistant = autogen.AssistantAgent(...)
        # ... rest of workflow

        autogen.runtime_logging.stop()
    """

    def __init__(self):
        """Initialize the WeaveLogger.

        This logger will forward all ag2 logging calls to Weave operations
        for comprehensive tracing of agent workflows.
        """
        self.session_id: Optional[str] = None

        # Initialize weave client
        self.wc = None
        if wc := weave_client_context.get_weave_client():
            self.wc = wc
        else:
            warn_once(
                logger,
                "Weave client not initialized. AG2 tracing will be a no-op. "
                "Please call `weave.init(<project_name>)` to enable tracing.",
            )

        # Track mapping from ag2 entities to weave calls
        self._agent_calls: dict[str, Call] = {}  # agent_name -> Call
        self._wrapper_calls: dict[int, Call] = {}  # wrapper_id -> Call
        self._client_calls: dict[int, Call] = {}  # client_id -> Call

    def start(self) -> str:
        """Start the logger and return a session_id.

        Returns:
            str: A unique session identifier for this logging session.
        """
        self.session_id = str(uuid.uuid4())
        logger.info(f"Started WeaveLogger session: {self.session_id}")

        # Create a session call to group all ag2 activity
        if self.wc:
            self._session_call = self.wc.create_call(
                "ag2.session",
                inputs={"session_id": self.session_id},
                display_name="AG2 Session",
            )

        return self.session_id

    def log_chat_completion(
        self,
        invocation_id: uuid.UUID,
        client_id: int,
        wrapper_id: int,
        source: str | Agent,
        request: dict[str, float | str | list[dict[str, str]]],
        response: str | ChatCompletion,
        is_cached: int,
        cost: float,
        start_time: str,
    ) -> None:
        """Log a chat completion to Weave.

        Creates a Weave call for the LLM interaction, linking it to the appropriate
        agent or wrapper as parent.
        """
        if not self.wc:
            return

        # Determine parent call - prefer agent, fallback to wrapper, then session
        parent_call = None
        agent_name = (
            source if isinstance(source, str) else getattr(source, "name", str(source))
        )

        if agent_name in self._agent_calls:
            parent_call = self._agent_calls[agent_name]
        elif wrapper_id in self._wrapper_calls:
            parent_call = self._wrapper_calls[wrapper_id]
        elif hasattr(self, "_session_call"):
            parent_call = self._session_call

        # Extract model info from request
        model = (
            request.get("model", "unknown") if isinstance(request, dict) else "unknown"
        )

        # Create the chat completion call
        call = self.wc.create_call(
            "ag2.chat_completion",
            inputs={
                "invocation_id": str(invocation_id),
                "agent_name": agent_name,
                "model": model,
                "request": request,
                "is_cached": bool(is_cached),
            },
            parent=parent_call,
            display_name=f"Chat Completion ({agent_name})",
        )

        # Prepare outputs
        outputs = {
            "response": response,
            "cost": cost,
            "start_time": start_time,
        }

        # Extract usage information if available
        if hasattr(response, "usage") and response.usage:
            usage_data = {
                "prompt_tokens": getattr(response.usage, "prompt_tokens", 0),
                "completion_tokens": getattr(response.usage, "completion_tokens", 0),
                "total_tokens": getattr(response.usage, "total_tokens", 0),
            }
            outputs["usage"] = usage_data

            # Add usage to call summary
            if call.summary is None:
                call.summary = {}
            call.summary.update({"usage": {model: usage_data}})

        # Finish the call immediately since ag2 provides complete info
        self.wc.finish_call(call, outputs)

    def log_new_agent(self, agent: ConversableAgent, init_args: dict[str, Any]) -> None:
        """Log the creation of a new agent.

        Creates a Weave call for the agent that will serve as parent for
        the agent's subsequent actions.
        """
        if not self.wc:
            return

        agent_name = getattr(agent, "name", str(agent))
        agent_class = agent.__class__.__name__
        agent_module = agent.__class__.__module__

        # Create agent call as child of session
        parent_call = getattr(self, "_session_call", None)

        call = self.wc.create_call(
            "ag2.agent",
            inputs={
                "agent_name": agent_name,
                "agent_class": agent_class,
                "agent_module": agent_module,
                "init_args": init_args,
            },
            parent=parent_call,
            display_name=f"Agent ({agent_name})",
        )

        # Store the agent call for future parent relationships
        self._agent_calls[agent_name] = call

        # Keep this call open for child operations - it will be finished in stop()

    def log_event(
        self, source: str | Agent, name: str, **kwargs: dict[str, Any]
    ) -> None:
        """Log an agent event.

        Creates a Weave call for agent events like tool calls, messages, etc.
        """
        if not self.wc:
            return

        source_name = (
            source if isinstance(source, str) else getattr(source, "name", str(source))
        )

        # Find parent call - prefer agent, fallback to session
        parent_call = None
        if source_name in self._agent_calls:
            parent_call = self._agent_calls[source_name]
        elif hasattr(self, "_session_call"):
            parent_call = self._session_call

        # Create event call
        call = self.wc.create_call(
            "ag2.event",
            inputs={
                "source_name": source_name,
                "event_name": name,
                "event_data": kwargs,
            },
            parent=parent_call,
            display_name=f"Event: {name}",
        )

        # Events are typically instantaneous, so finish immediately
        self.wc.finish_call(call, {"status": "completed"})

    def log_new_wrapper(
        self, wrapper: OpenAIWrapper, init_args: dict[str, LLMConfig | list[LLMConfig]]
    ) -> None:
        """Log the creation of a new OpenAIWrapper.

        Creates a Weave call for the wrapper that can serve as parent for
        client operations.
        """
        if not self.wc:
            return

        wrapper_id = id(wrapper)
        wrapper_class = wrapper.__class__.__name__

        # Create wrapper call as child of session
        parent_call = getattr(self, "_session_call", None)

        call = self.wc.create_call(
            "ag2.wrapper",
            inputs={
                "wrapper_id": wrapper_id,
                "wrapper_class": wrapper_class,
                "init_args": init_args,
            },
            parent=parent_call,
            display_name=f"OpenAI Wrapper ({wrapper_class})",
        )

        # Store wrapper call for future parent relationships
        self._wrapper_calls[wrapper_id] = call

    def log_new_client(
        self,
        client: AzureOpenAI | OpenAI,
        wrapper: OpenAIWrapper,
        init_args: dict[str, Any],
    ) -> None:
        """Log the creation of a new OpenAI client.

        Creates a Weave call for the client linked to its wrapper.
        """
        if not self.wc:
            return

        client_id = id(client)
        client_class = client.__class__.__name__
        wrapper_id = id(wrapper)

        # Find parent - prefer wrapper, fallback to session
        parent_call = None
        if wrapper_id in self._wrapper_calls:
            parent_call = self._wrapper_calls[wrapper_id]
        elif hasattr(self, "_session_call"):
            parent_call = self._session_call

        call = self.wc.create_call(
            "ag2.client",
            inputs={
                "client_id": client_id,
                "client_class": client_class,
                "wrapper_id": wrapper_id,
                "init_args": init_args,
            },
            parent=parent_call,
            display_name=f"OpenAI Client ({client_class})",
        )

        # Store client call
        self._client_calls[client_id] = call

    def log_function_use(
        self,
        source: str | Agent,
        function: Callable,
        args: dict[str, Any],
        returns: Any,
    ) -> None:
        """Log the use of a registered function (tool).

        Creates a Weave call for function/tool execution.
        """
        if not self.wc:
            return

        source_name = (
            source if isinstance(source, str) else getattr(source, "name", str(source))
        )
        function_name = getattr(function, "__name__", str(function))

        # Find parent call - prefer agent, fallback to session
        parent_call = None
        if source_name in self._agent_calls:
            parent_call = self._agent_calls[source_name]
        elif hasattr(self, "_session_call"):
            parent_call = self._session_call

        # Create function call
        call = self.wc.create_call(
            "ag2.function",
            inputs={
                "source_name": source_name,
                "function_name": function_name,
                "args": args,
            },
            parent=parent_call,
            display_name=f"Function: {function_name}",
        )

        # Finish with results
        self.wc.finish_call(call, {"returns": returns})

    def stop(self) -> None:
        """Close the connection to the logging database, and stop logging.

        Finishes any open calls and cleans up.
        """
        if self.wc:
            # Finish any remaining agent calls
            for agent_name, call in self._agent_calls.items():
                try:
                    self.wc.finish_call(
                        call, {"status": "completed", "agent_name": agent_name}
                    )
                except Exception as e:
                    logger.warning(f"Failed to finish agent call for {agent_name}: {e}")

            # Finish any remaining wrapper calls
            for wrapper_id, call in self._wrapper_calls.items():
                try:
                    self.wc.finish_call(call, {"status": "completed"})
                except Exception as e:
                    logger.warning(
                        f"Failed to finish wrapper call for {wrapper_id}: {e}"
                    )

            # Finish any remaining client calls
            for client_id, call in self._client_calls.items():
                try:
                    self.wc.finish_call(call, {"status": "completed"})
                except Exception as e:
                    logger.warning(f"Failed to finish client call for {client_id}: {e}")

            # Finish session call
            if hasattr(self, "_session_call"):
                try:
                    # Provide summary of what happened in this session
                    agent_names = list(self._agent_calls.keys())
                    self.wc.finish_call(
                        self._session_call,
                        {
                            "session_id": self.session_id,
                            "agents_created": agent_names,
                            "num_agents": len(agent_names),
                            "status": "completed",
                        },
                    )
                except Exception as e:
                    logger.warning(f"Failed to finish session call: {e}")

        # Clear mappings
        self._agent_calls.clear()
        self._wrapper_calls.clear()
        self._client_calls.clear()

        if self.session_id:
            logger.info(f"Stopped WeaveLogger session: {self.session_id}")
        self.session_id = None

    def get_connection(self) -> None | sqlite3.Connection:
        """Return a connection to the logging database.

        WeaveLogger doesn't use a database connection, so this returns None.

        Returns:
            None: WeaveLogger doesn't use database connections
        """
        return None
