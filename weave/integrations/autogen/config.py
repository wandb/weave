from pydantic import BaseModel


class BasePatchClassConfig(BaseModel):
    """Configuration for patching a specific class in the autogen library.

    This model defines which methods of a class should be patched and whether
    to include the base class and/or its subclasses in the patching process.

    Attributes:
        class_name: The name of the class to patch.
        method_names: A list of method names in the class to patch.
        should_patch_base_class: Whether to patch the base class itself.
        should_patch_subclasses: Whether to patch subclasses of the base class.
    """

    class_name: str
    method_names: list[str]
    should_patch_base_class: bool = False
    should_patch_subclasses: bool = True


class BasePatchModuleConfig(BaseModel):
    """Configuration for patching classes within a specific module.

    This model defines which module contains the classes to be patched
    and the configuration for each class within that module.

    Attributes:
        module_path: The import path of the module containing classes to patch.
        classes: A list of class configurations defining which classes and methods to patch.
    """

    module_path: str
    classes: list[BasePatchClassConfig]


def _get_module_patch_configs() -> list[BasePatchModuleConfig]:
    """Creates the internal configuration for patching autogen components.

    This function defines which modules, classes, and methods in the autogen
    library should be patched with weave instrumentation. Each configuration
    specifies a module, the classes within it, and the methods to patch.

    Returns:
        A list of BasePatchModuleConfig objects defining the complete
        patching configuration for autogen components.
    """
    ## Autogen Agent Chat
    # Chat Agent Class
    base_chat_agent_config = BasePatchClassConfig(
        class_name="BaseChatAgent",
        method_names=["run", "run_stream", "on_messages", "on_messages_stream"],
        should_patch_base_class=True,
        should_patch_subclasses=True,
    )

    base_chat_agent_module_config = BasePatchModuleConfig(
        module_path="autogen_agentchat.agents._base_chat_agent",
        classes=[base_chat_agent_config],
    )

    # Task Runner Tool Class
    task_runner_tool_config = BasePatchClassConfig(
        class_name="TaskRunnerTool", method_names=["run"]
    )

    task_runner_tool_module_config = BasePatchModuleConfig(
        module_path="autogen_agentchat.tools._task_runner_tool",
        classes=[task_runner_tool_config],
    )

    # Team Class
    team_config = BasePatchClassConfig(
        class_name="BaseGroupChat",
        method_names=["run", "run_stream"],
        should_patch_base_class=True,
        should_patch_subclasses=True,
    )

    team_module_config = BasePatchModuleConfig(
        module_path="autogen_agentchat.teams._group_chat._base_group_chat",
        classes=[team_config],
    )

    ## Autogen Core
    # Base Agent Class
    base_agent_config = BasePatchClassConfig(
        class_name="BaseAgent",
        method_names=["on_message", "send_message", "publish_message"],
        should_patch_base_class=True,
        should_patch_subclasses=True,
    )

    base_agent_module_config = BasePatchModuleConfig(
        module_path="autogen_core._base_agent",
        classes=[base_agent_config],
    )
    # Agent Runtime Class
    agent_runtime_config = BasePatchClassConfig(
        class_name="AgentRuntime",
        method_names=["send_message", "publish_message"],
        should_patch_base_class=True,
        should_patch_subclasses=True,
    )

    agent_runtime_module_config = BasePatchModuleConfig(
        module_path="autogen_core._agent_runtime",
        classes=[agent_runtime_config],
    )
    # Base Tool Class
    base_tool_config = BasePatchClassConfig(
        class_name="BaseTool", method_names=["run", "run_json"]
    )

    base_tool_module_config = BasePatchModuleConfig(
        module_path="autogen_core.tools._base", classes=[base_tool_config]
    )

    # Chat Completion Client Class
    chat_completion_client_config = BasePatchClassConfig(
        class_name="ChatCompletionClient",
        method_names=["create", "create_stream", "_check_cache"],
        should_patch_base_class=True,
        should_patch_subclasses=True,
    )

    chat_completion_client_module_config = BasePatchModuleConfig(
        module_path="autogen_core.models._model_client",
        classes=[chat_completion_client_config],
    )

    # Memory Class
    memory_config = BasePatchClassConfig(
        class_name="Memory",
        method_names=["update_context", "query", "add", "clear"],
        should_patch_base_class=True,
        should_patch_subclasses=True,
    )

    memory_module_config = BasePatchModuleConfig(
        module_path="autogen_core.memory._base_memory",
        classes=[memory_config],
    )

    # Code Executor Class
    code_executor_config = BasePatchClassConfig(
        class_name="CodeExecutor",
        method_names=[
            "execute_code_blocks",
        ],
        should_patch_base_class=False,
        should_patch_subclasses=True,
    )

    code_executor_module_config = BasePatchModuleConfig(
        module_path="autogen_core.code_executor._base",
        classes=[code_executor_config],
    )

    cache_store_config = BasePatchClassConfig(
        class_name="CacheStore",
        method_names=["get", "set"],
        should_patch_base_class=False,
        should_patch_subclasses=True,
    )
    cache_store_module_config = BasePatchModuleConfig(
        module_path="autogen_core._cache_store",
        classes=[cache_store_config],
    )

    return [
        ## Autogen Agent Chat Modules
        base_chat_agent_module_config,
        task_runner_tool_module_config,
        team_module_config,
        ## Autogen Core Modules
        base_agent_module_config,
        agent_runtime_module_config,
        base_tool_module_config,
        chat_completion_client_module_config,
        memory_module_config,
        code_executor_module_config,
        cache_store_module_config,
    ]


def get_module_patch_configs() -> list[BasePatchModuleConfig]:
    """Returns the module patch configurations as dictionaries.

    This function converts the internal Pydantic models to dictionaries
    for easier consumption by the patching mechanism. This is the public
    API used by the autogen SDK to retrieve patching configurations.

    Returns:
        A list of dictionaries representing the module patch configurations.
        Each dictionary contains module paths and classes to patch.
    """
    return [item.model_dump() for item in _get_module_patch_configs()]
