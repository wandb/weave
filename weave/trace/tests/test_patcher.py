import importlib

from weave.trace.patcher import SymbolPatcher


def test_symbol_patcher():
    from .test_patcher_module.example_class import ExampleClass

    patcher = SymbolPatcher(
        lambda: importlib.import_module(
            "weave.trace.tests.test_patcher_module.example_class"
        ),
        "ExampleClass.example_fn",
        lambda original_fn: lambda self: 43,
    )

    obj = ExampleClass()
    assert obj.example_fn() == 42
    patcher.attempt_patch()
    obj = ExampleClass()
    assert obj.example_fn() == 43
    patcher.undo_patch()
    obj = ExampleClass()
    assert obj.example_fn() == 42


def test_symbol_patcher_invalid_module():
    patcher = SymbolPatcher(
        lambda: importlib.import_module("INVALID_MODULE"),
        "ExampleClass.example_fn",
        lambda original_fn: lambda self: 43,
    )
    # Should not raise, but should fail to patch
    assert not patcher.attempt_patch()
    assert not patcher.undo_patch()


def test_symbol_patcher_invalid_attr():
    patcher = SymbolPatcher(
        lambda: importlib.import_module(
            "weave.trace.tests.test_patcher_module.example_class"
        ),
        "NotARealExampleClass.example_fn",
        lambda original_fn: lambda self: 43,
    )
    # Should not raise, but should fail to patch
    assert not patcher.attempt_patch()
    assert not patcher.undo_patch()


def test_symbol_patcher_invalid_patching():
    from .test_patcher_module.example_class import ExampleClass

    patcher = SymbolPatcher(
        lambda: importlib.import_module(
            "weave.trace.tests.test_patcher_module.example_class"
        ),
        "ExampleClass.example_fn",
        lambda original_fn: [] + 42,
    )
    # Should not raise, but should fail to patch
    assert not patcher.attempt_patch()
    assert not patcher.undo_patch()
    obj = ExampleClass()
    assert obj.example_fn() == 42
