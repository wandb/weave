from __future__ import annotations

import importlib
import inspect
import logging
from collections.abc import Sequence
from functools import wraps
from typing import Any, Callable, TypeVar

import weave
from weave.integrations.patcher import (
    MultiPatcher,
    NoOpPatcher,
    Patcher,
    SymbolPatcher,
)
from weave.trace.autopatch import IntegrationSettings, OpSettings
from weave.trace.op import Op, ProcessedInputs, _add_accumulator

from .config import get_module_patch_configs

logger = logging.getLogger(__name__)

_autogen_patcher: MultiPatcher | None = None


T = TypeVar("T")
R = TypeVar("R")


def _accumulator(acc: Any | None, value: Any) -> Any:
    """Accumulates streamed values based on their type.

    This function handles the accumulation of streamed values from autogen components,
    with special handling for ModelClientStreamingChunkEvent objects.

    Args:
        acc: The accumulated value so far, or None if this is the first value.
        value: The new value to accumulate.

    Returns:
        The updated accumulated value.
    """
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
    """Determines if a function should use an accumulator for results.

    We use accumulators for async generator functions which indicate streaming
    responses from autogen components.

    Args:
        fn: The function to check.

    Returns:
        True if the function is an async generator, False otherwise.
    """
    return inspect.isasyncgenfunction(fn)


def _on_finish_post_processor(value: Any) -> Any:
    """Post-processes the final accumulated value.

    Currently a no-op post-processor, but provides an extension point for
    custom logic in the future.

    Args:
        value: The final accumulated value.

    Returns:
        The processed value.
    """
    return value


def _on_input_handler(func: Op, args: tuple, kwargs: dict) -> ProcessedInputs | None:
    """Handles input processing for operations.

    A placeholder for future custom input processing logic.

    Args:
        func: The operation being executed.
        args: Positional arguments to the operation.
        kwargs: Keyword arguments to the operation.

    Returns:
        Processed inputs or None if no special processing is needed.
    """
    return None


def _get_fully_qualified_op_display_name(obj: Any, method_name: str) -> str:
    """Generates a simplified operation name for display.

    Creates a human-readable operation name using the library name,
    class name, and method name.

    Args:
        obj: The object instance the method belongs to.
        method_name: The name of the method.

    Returns:
        A string containing the library name, class name, and method name.
    """
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
    """Sets up a wrapped operation for a function call.

    Creates a weave operation wrapper around a function and configures it
    for tracing with appropriate naming and input handling.

    Args:
        fn: The function to wrap.
        args: Positional arguments to the function.
        kwargs: Keyword arguments to the function.
        op_kwargs: Additional keyword arguments for the operation.
        should_accumulate: Whether the operation should accumulate results.

    Returns:
        A configured weave operation.
    """
    self_obj = args[0]
    op_name = _get_fully_qualified_op_display_name(self_obj, fn.__name__)
    updated_kwargs = op_kwargs.copy()
    updated_kwargs["name"] = op_name
    op = weave.op(fn, **updated_kwargs)
    op._set_on_input_handler(_on_input_handler)

    # Extract inputs from args and kwargs for tracing
    inputs = {}
    if len(args) > 1:
        sig = inspect.signature(fn)
        param_names = list(sig.parameters.keys())
        for i, arg in enumerate(args[1:], 1):
            if i < len(param_names):
                inputs[param_names[i]] = arg
    inputs.update(kwargs)

    # Add accumulator for streaming operations if needed
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
    """Creates a wrapper for async generator functions.

    This wrapper is specifically designed for streaming methods that use
    async generators, like streamed LLM responses.

    Args:
        settings: Operation settings for the wrapper.

    Returns:
        A function that wraps async generator functions with weave tracing.
    """

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
                    f"{e}\nError in autogen async gen wrapper for {fn.__name__}",
                    stacklevel=2,
                )
                # Fall back to the original function if our instrumentation fails
                async for value in fn(*args, **kwargs):
                    yield value

        return _symbol_wrapper

    return wrapper


def _create_wrapper_async(
    settings: OpSettings,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Creates a wrapper for regular async functions.

    This wrapper is for non-streaming async methods that return a single value.

    Args:
        settings: Operation settings for the wrapper.

    Returns:
        A function that wraps async functions with weave tracing.
    """

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
                # Fall back to the original function if our instrumentation fails
                return await fn(*args, **kwargs)

        return _symbol_wrapper

    return wrapper


def _create_wrapper_sync(
    settings: OpSettings,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Creates a wrapper for regular synchronous functions.

    This wrapper is for non-async, non-generator methods that return a single value.

    Args:
        settings: Operation settings for the wrapper.

    Returns:
        A function that wraps sync functions with weave tracing.
    """

    def wrapper(fn: Callable[..., Any]) -> Callable[..., Any]:
        op_kwargs = settings.model_dump()

        @wraps(fn)
        def _symbol_wrapper(*args: Any, **kwargs: Any) -> Any:
            try:
                op = _setup_op_wrapper(
                    fn, args, kwargs, op_kwargs, should_accumulate=False
                )
                return op(*args, **kwargs)
            except Exception as e:
                logger.exception(
                    f"{e}\nError in autogen sync wrapper for {fn.__name__}",
                    stacklevel=2,
                )
                # Fall back to the original function if our instrumentation fails
                return fn(*args, **kwargs)

        return _symbol_wrapper

    return wrapper


def _create_symbol_wrapper(
    settings: OpSettings,
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Creates a wrapper factory for autogen methods.

    This is the main entry point for creating wrappers. It automatically
    determines if a method is a streaming method (async generator), a regular async method, or a sync method and creates the appropriate wrapper.

    Args:
        settings: Operation settings for the wrapper.

    Returns:
        A function that creates the appropriate wrapper based on the
        function signature.
    """

    def wrapper(fn: Callable[..., Any]) -> Callable[..., Any]:
        if _should_use_accumulator(fn):
            return _create_wrapper_async_generator(settings)(fn)
        elif inspect.iscoroutinefunction(fn):
            return _create_wrapper_async(settings)(fn)
        else:
            return _create_wrapper_sync(settings)(fn)

    return wrapper


def _get_symbol_patcher(
    module_path: str, class_name: str, method_name: str, settings: OpSettings
) -> SymbolPatcher | None:
    """Creates a SymbolPatcher for a specific method.

    Attempts to find and create a patcher for a specific method in a class,
    with error handling for missing modules, classes, or methods.

    Args:
        module_path: The import path of the module.
        class_name: The name of the class.
        method_name: The name of the method to patch.
        settings: Operation settings for the patcher.

    Returns:
        A SymbolPatcher if successful, None otherwise.
    """
    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError as e:
        logger.warning(
            f"Module {module_path} not found, skipping patching for {class_name}: {e}"
        )
        return None
    except ImportError as e:
        logger.warning(
            f"Could not import module {module_path}, skipping patching for {class_name}: {e}"
        )
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
) -> list[SymbolPatcher | None]:
    """Creates patchers for a class and its subclasses.

    This function handles the complexity of patching both a base class and all its
    subclasses, with careful handling of method inheritance and ownership.

    Args:
        module_path: The import path of the module.
        class_name: The name of the base class.
        method_names: List of method names to patch.
        settings: Operation settings for the patchers.
        should_patch_base_class: Whether to patch the base class itself.
        should_patch_subclasses: Whether to patch subclasses.

    Returns:
        A list of patchers for the specified methods across classes.
    """
    patchers: list[SymbolPatcher | None] = []

    try:
        module = importlib.import_module(module_path)
    except ModuleNotFoundError as e:
        logger.warning(
            f"Module {module_path} not found, skipping patching for {class_name}: {e}"
        )
        return patchers  # Return empty list, skip patching for this module
    except ImportError as e:
        logger.warning(
            f"Could not import module {module_path}, skipping patching for {class_name}: {e}"
        )
        return patchers

    try:
        base_class = getattr(module, class_name)

        classes_to_patch: list[type] = []
        if should_patch_base_class:
            classes_to_patch.append(base_class)

        if should_patch_subclasses:
            # Recursively collect all subclasses
            def collect_subclasses(cls: type) -> None:
                direct_subclasses = cls.__subclasses__()
                classes_to_patch.extend(direct_subclasses)
                for subclass in direct_subclasses:
                    collect_subclasses(subclass)

            collect_subclasses(base_class)

        # Track methods we've already patched to avoid duplicates
        patched_methods: set[tuple[str, str]] = set()

        for cls in classes_to_patch:
            cls_module_path = cls.__module__
            cls_name = cls.__name__

            for method_name in method_names:
                method = getattr(cls, method_name, None)
                if method is None:
                    continue

                # Skip methods that are inherited from another class without being
                # overridden in the current class
                if hasattr(method, "__qualname__"):
                    qualname = method.__qualname__
                    if "." in qualname:
                        owner_name = qualname.split(".")[0]
                        # Allow patching inherited methods for base_class if explicitly requested
                        if owner_name != cls_name and not (
                            cls is base_class and should_patch_base_class
                        ):
                            continue

                # Skip methods we've already patched
                method_key = (cls_module_path, method_name)
                if method_key in patched_methods:
                    continue

                patched_methods.add(method_key)

                patcher = _get_symbol_patcher(
                    cls_module_path, cls_name, method_name, settings
                )
                if patcher is not None:
                    patchers.append(patcher)

    except AttributeError as e:
        logger.warning(f"Class {class_name} not found in {module_path}, skipping: {e}")
        return patchers
    except Exception as e:
        logger.exception(
            f"Unexpected error creating patchers for {module_path}.{class_name}: {e}",
            stacklevel=2,
        )
        return patchers

    return patchers


def _preload_autogen_extensions() -> None:
    """Preloads autogen extension modules.

    This function ensures that autogen-ext modules are properly imported
    before patching to ensure that all subclasses are properly discovered.
    This is important because patching relies on the Python class hierarchy.
    """
    try:
        import importlib.util
        import pkgutil

        if importlib.util.find_spec("autogen_ext") is None:
            logger.info("autogen-ext package not found, skipping extension preloading")
            return

        import autogen_ext

        for _, name, _ in pkgutil.walk_packages(
            autogen_ext.__path__, autogen_ext.__name__ + "."
        ):
            try:
                importlib.import_module(name)
            except (ImportError, ModuleNotFoundError) as e:
                # Only log at debug level, and don't include stack trace
                logger.debug(f"Optional extension module not loaded: {name} ({e})")
            except Exception as e:
                # Unexpected errors should still be logged as warnings
                logger.exception(
                    f"Unexpected error loading extension module {name}: {e}",
                    stacklevel=2,
                )

    except Exception as e:
        # Don't fail if preloading fails
        logger.warning(f"Error preloading autogen extensions: {e}", stacklevel=2)


def get_autogen_patcher(
    settings: IntegrationSettings | None = None,
) -> MultiPatcher | NoOpPatcher:
    """Creates and returns a patcher for autogen-agentchat.

    This is the main entry point for the autogen integration. It creates
    a patcher that can be used to instrument autogen's methods with weave
    tracing capabilities.

    Args:
        settings: Integration settings, including whether the integration
            is enabled and operation-specific settings.

    Returns:
        Either a MultiPatcher containing all the patchers for autogen methods,
        or a NoOpPatcher if the integration is disabled.
    """
    if settings is None:
        settings = IntegrationSettings()

    if not settings.enabled:
        return NoOpPatcher()

    global _autogen_patcher
    if _autogen_patcher is not None:
        return _autogen_patcher

    try:
        if importlib.util.find_spec("autogen_agentchat") is None:
            logger.debug("autogen_agentchat package not found, skipping patching")
            return NoOpPatcher()

        # Preload autogen-ext modules to ensure subclasses are properly discovered
        _preload_autogen_extensions()

        base_settings = settings.op_settings
        op_patch_settings = base_settings.model_copy(
            update={"name": base_settings.name or "autogen.component"}
        )

        patchers: list[SymbolPatcher | None] = []
        patch_configs = get_module_patch_configs()

        # Create patchers for each class and method specified in the configuration
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

        # Filter out None entries and create the MultiPatcher
        valid_patchers: Sequence[Patcher] = [p for p in patchers if p is not None]
        _autogen_patcher = MultiPatcher(valid_patchers)
    except Exception:
        logger.exception("Failed to create autogen patcher", stacklevel=2)
        return NoOpPatcher()
    else:
        return _autogen_patcher
