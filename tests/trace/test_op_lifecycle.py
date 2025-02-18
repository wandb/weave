"""Tests for the Op lifecycle functionality."""

import pytest
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from unittest.mock import MagicMock

import weave
from weave.trace.op import (
    OpLifecycle,
    DefaultOpLifecycle,
    IteratorLifecycle,
    execute_op,
    Op,
)
from weave.trace.weave_client import Call, WeaveClient
from weave.trace.context import weave_client_context

# Mock Call for testing
@dataclass
class MockCall:
    """Mock Call object for testing."""
    inputs: Optional[Dict[str, Any]] = None
    output: Optional[Any] = None
    id: str = "test_id"
    trace_id: str = "test_trace"
    project_id: str = "test_project"
    parent_id: Optional[str] = None

    def update_inputs(self, inputs: Dict[str, Any]) -> None:
        self.inputs = inputs

    def update_output(self, output: Any) -> None:
        self.output = output

# Mock Client for testing
class MockWeaveClient(WeaveClient):
    def __init__(self):
        self.server = MagicMock()
        
    def create_call(self, *args, **kwargs):
        return MockCall()
        
    def finish_call(self, *args, **kwargs):
        pass

@pytest.fixture(autouse=True)
def setup_weave():
    """Setup weave client for testing."""
    client = MockWeaveClient()
    weave_client_context.set_weave_client_global(client)
    yield
    weave_client_context.set_weave_client_global(None)

# Test Lifecycle Implementation
@dataclass
class TestLifecycle:
    """Test lifecycle implementation that tracks hook calls."""
    before_call_called: bool = field(default=False)
    process_inputs_called: bool = field(default=False)
    on_yield_called: bool = field(default=False)
    process_output_called: bool = field(default=False)
    on_error_called: bool = field(default=False)
    on_finish_called: bool = field(default=False)
    after_call_called: bool = field(default=False)
    
    def before_call(self, call: Call) -> None:
        self.before_call_called = True
        
    def process_inputs_for_logging(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        self.process_inputs_called = True
        return inputs
        
    def on_yield(self, value: Any) -> Any:
        self.on_yield_called = True
        return value
        
    def process_output(self, output: Any) -> Any:
        self.process_output_called = True
        return output
        
    def on_error(self, error: Exception) -> None:
        self.on_error_called = True
        
    def on_finish(self, error: Optional[Exception]) -> None:
        self.on_finish_called = True
        
    def after_call(self, call: Call) -> None:
        self.after_call_called = True

# Test Functions
def test_sync_function():
    """Test lifecycle hooks for sync function."""
    lifecycle = TestLifecycle()
    
    # Create test op
    @weave.op()
    def test_fn(x: int) -> int:
        return x * 2
        
    # Override lifecycle
    test_fn.lifecycle = lifecycle
    
    # Execute
    result, call = execute_op(test_fn, MockCall(), (2,), {})
    
    # Verify result
    assert result == 4
    
    # Verify hook calls
    assert lifecycle.before_call_called
    assert lifecycle.process_inputs_called
    assert lifecycle.process_output_called
    assert lifecycle.on_finish_called
    assert lifecycle.after_call_called

    # Verify call inputs were processed
    assert isinstance(call.inputs, dict)
    assert call.inputs == {"arg0": 2}

def test_async_function():
    """Test lifecycle hooks for async function."""
    lifecycle = TestLifecycle()
    
    # Create test op
    @weave.op()
    async def test_fn(x: int) -> int:
        return x * 2
        
    # Override lifecycle
    test_fn.lifecycle = lifecycle
    
    # Execute
    import asyncio
    result, call = asyncio.run(execute_op(test_fn, MockCall(), (2,), {}))
    
    # Verify result
    assert result == 4
    
    # Verify hook calls
    assert lifecycle.before_call_called
    assert lifecycle.process_inputs_called
    assert lifecycle.process_output_called
    assert lifecycle.on_finish_called
    assert lifecycle.after_call_called

    # Verify call inputs were processed
    assert isinstance(call.inputs, dict)
    assert call.inputs == {"arg0": 2}

def test_sync_iterator():
    """Test lifecycle hooks for sync iterator."""
    lifecycle = TestLifecycle()
    
    # Create test op
    @weave.op()
    def test_fn():
        yield 1
        yield 2
        
    # Override lifecycle
    test_fn.lifecycle = lifecycle
    
    # Execute
    result, call = execute_op(test_fn, MockCall(), (), {})
    
    # Consume iterator
    values = list(result)
    assert values == [1, 2]
    
    # Verify hook calls
    assert lifecycle.before_call_called
    assert lifecycle.process_inputs_called
    assert lifecycle.on_yield_called
    assert lifecycle.on_finish_called
    assert lifecycle.after_call_called

    # Verify call inputs were processed
    assert isinstance(call.inputs, dict)
    assert call.inputs == {}

def test_async_iterator():
    """Test lifecycle hooks for async iterator."""
    lifecycle = TestLifecycle()
    
    # Create test op
    @weave.op()
    async def test_fn():
        yield 1
        yield 2
        
    # Override lifecycle
    test_fn.lifecycle = lifecycle
    
    # Execute
    import asyncio
    result, call = asyncio.run(execute_op(test_fn, MockCall(), (), {}))
    
    # Consume iterator
    async def consume():
        values = []
        async for value in result:
            values.append(value)
        return values
        
    values = asyncio.run(consume())
    assert values == [1, 2]
    
    # Verify hook calls
    assert lifecycle.before_call_called
    assert lifecycle.process_inputs_called
    assert lifecycle.on_yield_called
    assert lifecycle.on_finish_called
    assert lifecycle.after_call_called

    # Verify call inputs were processed
    assert isinstance(call.inputs, dict)
    assert call.inputs == {}

async def consume_async_iterator(ait):
    """Helper function to consume an async iterator."""
    values = []
    async for value in ait:
        values.append(value)
    return values

def test_error_handling():
    """Test lifecycle hooks for error handling."""
    lifecycle = TestLifecycle()
    
    # Create test op
    @weave.op()
    def test_fn():
        raise ValueError("test error")
        
    # Override lifecycle
    test_fn.lifecycle = lifecycle
    
    # Execute
    with pytest.raises(ValueError):
        execute_op(test_fn, MockCall(), (), {}, should_raise=True)
    
    # Verify hook calls
    assert lifecycle.before_call_called
    assert lifecycle.process_inputs_called
    assert lifecycle.on_error_called
    assert lifecycle.on_finish_called
    assert lifecycle.after_call_called

def test_iterator_lifecycle():
    """Test IteratorLifecycle accumulator functionality."""
    # Create accumulator
    def make_accumulator(inputs):
        def accumulator(state, value):
            if state is None:
                state = []
            state.append(value)
            return state
        return accumulator
    
    # Create lifecycle
    lifecycle = IteratorLifecycle[List[int]]()
    lifecycle._accumulator = make_accumulator({})
    
    # Create test op
    @weave.op()
    def test_fn():
        yield 1
        yield 2
        
    # Override lifecycle
    test_fn.lifecycle = lifecycle
    
    # Execute
    result, call = execute_op(test_fn, MockCall(), (), {})
    
    # Consume iterator
    values = list(result)
    assert values == [1, 2]
    
    # Verify accumulated state
    assert lifecycle._state == [1, 2]

def test_default_lifecycle():
    """Test DefaultOpLifecycle maintains compatibility."""
    lifecycle = DefaultOpLifecycle()
    
    # Create test op
    @weave.op()
    def test_fn(x: int) -> int:
        return x * 2
        
    # Override lifecycle
    test_fn.lifecycle = lifecycle
    
    # Execute
    result, call = execute_op(test_fn, MockCall(), (2,), {})
    
    # Verify result
    assert result == 4
    
    # Verify call inputs were processed
    assert isinstance(call.inputs, dict)
    assert call.inputs == {"arg0": 2} 