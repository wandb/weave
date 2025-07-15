"""Async operation decorator for Weave."""

from __future__ import annotations

import asyncio
import functools
import inspect
from typing import Any, Callable, Optional, TypeVar, Union

from weave.trace.op import Op, as_op

F = TypeVar("F", bound=Callable[..., Any])


def async_op(
    fn: Optional[F] = None,
    *,
    name: Optional[str] = None,
    display_name: Optional[str] = None,
    render_info: Optional[dict[str, Any]] = None,
    call_display_name: Optional[Union[str, Callable[[dict], str]]] = None,
) -> Union[F, Callable[[F], F]]:
    """Decorator to create an async Weave operation.
    
    This decorator works with async functions and handles tracing automatically.
    
    Args:
        fn: The function to decorate (when used without parentheses)
        name: Optional operation name override
        display_name: Optional display name for the operation
        render_info: Optional rendering information
        call_display_name: Optional callable or string for dynamic display names
    
    Returns:
        The decorated function that will be traced
    
    Example:
        ```python
        import asyncio
        from weave.trace.async_client import async_op, create_async_client
        
        @async_op
        async def my_async_function(x: int, y: int) -> int:
            await asyncio.sleep(0.1)  # Simulate async work
            return x + y
        
        async def main():
            # Initialize client
            async with await create_async_client("entity", "project") as client:
                # Call the decorated function
                result = await my_async_function(5, 3)
                print(result)  # 8
        
        asyncio.run(main())
        ```
    """
    def decorator(func: F) -> F:
        if not asyncio.iscoroutinefunction(func):
            # If it's not async, fall back to regular op decorator
            return as_op(func, name=name, render_info=render_info, call_display_name=call_display_name)
        
        # Create the Op object
        op_obj = Op(
            name=name or func.__name__,
            render_info=render_info,
            call_display_name=call_display_name,
        )
        op_obj._set_on_input_handler(func)
        
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Get current client from context (would need async context implementation)
            from weave.trace.context import weave_client_context
            client = weave_client_context.get_client()
            
            if client is None or not hasattr(client, 'create_call'):
                # No client available, just run the function
                return await func(*args, **kwargs)
            
            # For now, if we have a sync client, just run without tracing
            # In a full implementation, we'd check if it's an AsyncWeaveClient
            if not hasattr(client, '__aenter__'):
                return await func(*args, **kwargs)
            
            # Create the call
            call_id = None
            exception = None
            try:
                # Prepare inputs
                sig = inspect.signature(func)
                bound = sig.bind(*args, **kwargs)
                bound.apply_defaults()
                inputs = dict(bound.arguments)
                
                # Get display name
                disp_name = display_name
                if call_display_name:
                    if callable(call_display_name):
                        disp_name = call_display_name(inputs)
                    else:
                        disp_name = call_display_name
                
                # Start the call
                call_id, _ = await client.create_call(
                    op=op_obj,
                    inputs=inputs,
                    display_name=disp_name,
                )
                
                # Execute the function
                result = await func(*args, **kwargs)
                
                # Finish the call
                await client.finish_call(call_id, output=result)
                
                return result
                
            except Exception as e:
                exception = str(e)
                if call_id:
                    await client.finish_call(call_id, exception=exception)
                raise
        
        # Attach the op object to the wrapper
        async_wrapper._op = op_obj
        async_wrapper.__name__ = func.__name__
        async_wrapper.__qualname__ = func.__qualname__
        
        return async_wrapper
    
    # Handle being called with or without parentheses
    if fn is None:
        # Called with parentheses: @async_op()
        return decorator
    else:
        # Called without parentheses: @async_op
        return decorator(fn)