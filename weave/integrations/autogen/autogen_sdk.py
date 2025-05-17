from __future__ import annotations

import importlib
import inspect
import logging
from functools import wraps
from typing import Any, Callable, Optional, Sequence, Type, TypeVar

import weave
from weave.integrations.autogen.config import get_module_patch_configs
from weave.integrations.patcher import MultiPatcher, NoOpPatcher, Patcher, SymbolPatcher
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.trace.op import Op, ProcessedInputs, _add_accumulator

logger = logging.getLogger(__name__)

_autogen_patcher: Optional[MultiPatcher] = None


T = TypeVar("T")
R = TypeVar("R")


def _accumulator(acc: Optional[Any], value: Any) -> Any:
    """Accumulates streamed values based on type."""
    if (
        hasattr(value, "type")
        and getattr(value, "type", None) == "ModelClientStreamingChunkEvent"
    ):
        if acc is None:
            return value

        if (
            hasattr(acc, "type")
            and getattr(acc, "type", None) == "ModelClientStreamingChunkEvent"
        ):
            combined_content = acc.content + value.content
            new_event = type(value)(
                source=value.source,
                content=combined_content,
                type=value.type,
                metadata=value.metadata,
            )
            return new_event
        else:
            return value

    if acc is None:
        if isinstance(value, str):
            return value
        else:
            return [value]

    if isinstance(value, str):
        if isinstance(acc, str):
            return acc + value
        elif isinstance(acc, list):
            return acc + [value]
    else:
        if isinstance(acc, list):
            acc.append(value)
            return acc
        else:
            return [acc, value]


def _should_use_accumulator(fn: Callable[..., Any]) -> bool:
    """Use accumulator if the function is an async generator (streaming)."""
    return inspect.isasyncgenfunction(fn)


def _on_finish_post_processor(value: Any) -> Any:
    """No-op post-processor for now, but can be extended for custom logic."""
    return value


def _on_input_handler(func: Op, args: tuple, kwargs: dict) -> Optional[ProcessedInputs]:
    # No special input processing for now, but placeholder for future use
    return None


def _get_fully_qualified_op_display_name(obj: Any, method_name: str) -> str:
    """Generate a simplified operation name using library name, class, and method names."""
    module_name = obj.__class__.__module__
    library_name = module_name.split(".")[0]
    class_name = obj.__class__.__name__
    return f"{library_name}.{class_name}.{method_name}"


def _setup_op_wrapper(
    fn: Callable[..., Any],
    args: Any,
    kwargs: Any,
    op_kwargs: dict,
    should_accumulate: bool = False,
) -> Op:
    """Common setup logic for creating a wrapped op."""
    self_obj = args[0]
    op_name = _get_fully_qualified_op_display_name(self_obj, fn.__name__)
    updated_kwargs = op_kwargs.copy()
    updated_kwargs["name"] = op_name
    op = weave.op(fn, **updated_kwargs)
    op._set_on_input_handler(_on_input_handler)

    inputs = {}
    if len(args) > 1:
        sig = inspect.signature(fn)
        param_names = list(sig.parameters.keys())
        for i, arg in enumerate(args[1:], 1):
            if i < len(param_names):
                inputs[param_names[i]] = arg
    inputs.update(kwargs)

    if should_accumulate:
        op = _add_accumulator(
            op,
            make_accumulator=lambda _: _accumulator,
            should_accumulate=lambda _: True,
            on_finish_post_processor=_on_finish_post_processor,
        )

    return op


def _create_wrapper_async_generator(
    settings: OpSettings,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def wrapper(fn: Callable[..., Any]) -> Callable[..., Any]:
        op_kwargs = settings.model_dump()

        @wraps(fn)
        async def _symbol_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                op = _setup_op_wrapper(
                    fn, args, kwargs, op_kwargs, should_accumulate=True
                )
                agen = op(*args, **kwargs)

                async for value in agen:
                    yield value
            except Exception as e:
                logger.exception(
                    f"{e}\nError in autogen asyncgen wrapper for {fn.__name__}",
                    stacklevel=2,
                )
                async for value in fn(*args, **kwargs):
                    yield value

        return _symbol_wrapper

    return wrapper


def _create_wrapper_async(
    settings: OpSettings,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    def wrapper(fn: Callable[..., Any]) -> Callable[..., Any]:
        op_kwargs = settings.model_dump()

        @wraps(fn)
        async def _symbol_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                op = _setup_op_wrapper(
                    fn, args, kwargs, op_kwargs, should_accumulate=False
                )
                return await op(*args, **kwargs)
            except Exception as e:
                logger.exception(
                    f"{e}\nError in autogen async wrapper for {fn.__name__}",
                    stacklevel=2,
                )
                return await fn(*args, **kwargs)

        return _symbol_wrapper

    return wrapper


def _create_symbol_wrapper(
    settings: OpSettings,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Create a wrapper for BaseChatAgent methods that captures inputs and outputs.
    Automatically handles both regular methods and streaming methods (AsyncGenerators).
    """

    def wrapper(fn: Callable[..., Any]) -> Callable[..., Any]:
        if _should_use_accumulator(fn):
            return _create_wrapper_async_generator(settings)(fn)
        else:
            return _create_wrapper_async(settings)(fn)

    return wrapper


def _get_symbol_patcher(
    module_path: str, class_name: str, method_name: str, settings: OpSettings
) -> Optional[SymbolPatcher]:
    """Create a SymbolPatcher for a specific module.class.method combination."""
    try:
        module = importlib.import_module(module_path)
    except ImportError:
        logger.exception(f"Could not import module {module_path}", stacklevel=2)
        return None

    if not hasattr(module, class_name):
        logger.error(f"Class {class_name} not found in {module_path}")
        return None

    cls = getattr(module, class_name)

    if not hasattr(cls, method_name):
        logger.error(f"Method {method_name} not found in {module_path}.{class_name}")
        return None

    display_name = f"{module_path}.{class_name}.{method_name}"

    wrapper_factory = _create_symbol_wrapper(
        settings.model_copy(update={"display_name": display_name})
    )
    return SymbolPatcher(lambda: module, f"{class_name}.{method_name}", wrapper_factory)


def _get_class_and_subclass_patchers(
    module_path: str,
    class_name: str,
    method_names: list[str],
    settings: OpSettings,
    should_patch_base_class: bool = False,
    should_patch_subclasses: bool = True,
) -> list[Optional[SymbolPatcher]]:
    """Generate patchers for a class and all its subclasses for specified methods."""
    patchers: list[Optional[SymbolPatcher]] = []

    try:
        module = importlib.import_module(module_path)
        base_class = getattr(module, class_name)

        classes_to_patch: list[Type] = []
        if should_patch_base_class:
            classes_to_patch.append(base_class)

        if should_patch_subclasses:

            def collect_subclasses(cls: Type) -> None:
                direct_subclasses = cls.__subclasses__()
                classes_to_patch.extend(direct_subclasses)
                for subclass in direct_subclasses:
                    collect_subclasses(subclass)

            collect_subclasses(base_class)

        patched_methods: set[tuple[str, str]] = set()

        for cls in classes_to_patch:
            cls_module_path = cls.__module__
            cls_name = cls.__name__

            for method_name in method_names:
                method = getattr(cls, method_name, None)
                if method is None:
                    continue
                if hasattr(method, "__qualname__"):
                    qualname = method.__qualname__
                    if "." in qualname:
                        owner_name = qualname.split(".")[0]
                        if owner_name != cls_name:
                            if not (cls is base_class and should_patch_base_class):
                                continue

                method_key = (cls_module_path, method_name)
                if method_key in patched_methods:
                    continue

                patched_methods.add(method_key)

                patcher = _get_symbol_patcher(
                    cls_module_path, cls_name, method_name, settings
                )
                if patcher is not None:
                    patchers.append(patcher)

    except (ImportError, AttributeError):
        logger.exception(
            f"Error creating patchers for {module_path}.{class_name}", stacklevel=2
        )

    return patchers


def get_patcher(
    settings: Optional[IntegrationSettings] = None,
) -> MultiPatcher | NoOpPatcher:
    """Create and return a patcher for autogen-agentchat"""
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    try:
        global _autogen_patcher
        if _autogen_patcher is not None:
            return _autogen_patcher

        base_settings = settings.op_settings
        op_patch_settings = base_settings.model_copy(
            update={"name": base_settings.name or "autogen_agentchat.agent"}
        )

        patchers: list[Optional[SymbolPatcher]] = []
        patch_configs = get_module_patch_configs()

        for module_config in patch_configs:
            for class_config in module_config["classes"]:
                try:
                    class_patchers = _get_class_and_subclass_patchers(
                        module_path=module_config["module_path"],
                        class_name=class_config["class_name"],
                        method_names=class_config["method_names"],
                        settings=op_patch_settings,
                        should_patch_base_class=class_config["should_patch_base_class"],
                        should_patch_subclasses=class_config["should_patch_subclasses"],
                    )
                    patchers.extend(class_patchers)
                except Exception as e:
                    logger.exception(
                        f"{e}\nFailed to create patchers for {module_config['module_path']}.{class_config['class_name']}",
                        stacklevel=2,
                    )

        valid_patchers: Sequence[Patcher] = [p for p in patchers if p is not None]
        _autogen_patcher = MultiPatcher(valid_patchers)

        return _autogen_patcher
    except Exception:
        logger.exception("Failed to create autogen_agentchat patcher", stacklevel=2)
        return NoOpPatcher()
