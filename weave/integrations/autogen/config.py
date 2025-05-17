from pydantic import BaseModel


class BasePatchClassConfig(BaseModel):
    class_name: str
    method_names: list[str]
    should_patch_base_class: bool = False
    should_patch_subclasses: bool = True


class BasePatchModuleConfig(BaseModel):
    module_path: str
    classes: list[BasePatchClassConfig]


def _get_module_patch_configs() -> list[BasePatchModuleConfig]:
    base_chat_agent_config = BasePatchClassConfig(
        class_name="BaseChatAgent",
        method_names=["run", "run_stream", "on_messages", "on_messages_stream"],
    )

    base_chat_agent_module_config = BasePatchModuleConfig(
        module_path="autogen_agentchat.agents._base_chat_agent",
        classes=[base_chat_agent_config],
    )

    task_runner_tool_config = BasePatchClassConfig(
        class_name="TaskRunnerTool", method_names=["run"]
    )

    task_runner_tool_module_config = BasePatchModuleConfig(
        module_path="autogen_agentchat.tools._task_runner_tool",
        classes=[task_runner_tool_config],
    )

    base_tool_config = BasePatchClassConfig(
        class_name="BaseTool", method_names=["run", "run_json"]
    )

    base_tool_module_config = BasePatchModuleConfig(
        module_path="autogen_core.tools._base", classes=[base_tool_config]
    )

    chat_completion_client_config = BasePatchClassConfig(
        class_name="ChatCompletionClient", method_names=["create", "create_stream"]
    )

    chat_completion_client_module_config = BasePatchModuleConfig(
        module_path="autogen_core.models._model_client",
        classes=[chat_completion_client_config],
    )
    return [
        base_chat_agent_module_config,
        task_runner_tool_module_config,
        base_tool_module_config,
        chat_completion_client_module_config,
    ]


def get_module_patch_configs() -> list[BasePatchModuleConfig]:
    return [item.model_dump() for item in _get_module_patch_configs()]
