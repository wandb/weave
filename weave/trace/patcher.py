from __future__ import annotations

import logging
from collections.abc import Sequence
from typing import Any, Callable

from weave.trace.context.tests_context import get_raise_on_captured_errors

logger = logging.getLogger(__name__)


class Patcher:
    def attempt_patch(self) -> bool:
        raise NotImplementedError()

    def undo_patch(self) -> bool:
        raise NotImplementedError()


class NoOpPatcher(Patcher):
    def attempt_patch(self) -> bool:
        return True

    def undo_patch(self) -> bool:
        return True


class MultiPatcher(Patcher):
    def __init__(self, patchers: Sequence[Patcher]) -> None:
        self.patchers = patchers

    def attempt_patch(self) -> bool:
        all_successful = True
        for patcher in self.patchers:
            try:
                all_successful = all_successful and patcher.attempt_patch()
            except Exception as e:
                if get_raise_on_captured_errors():
                    raise
                logger.exception(f"Error patching - some logs may not be captured: {e}")
                all_successful = False
        return all_successful

    def undo_patch(self) -> bool:
        all_successful = True
        for patcher in self.patchers:
            try:
                all_successful = all_successful and patcher.undo_patch()
            except Exception as e:
                if get_raise_on_captured_errors():
                    raise
                logger.exception(f"Error unpatching: {e}")
                all_successful = False
        return all_successful


class _SymbolTarget:
    def __init__(self, base_symbol: Any, attr: str) -> None:
        self.base_symbol = base_symbol
        self.attr = attr


class SymbolPatcher(Patcher):
    _get_base_symbol: Callable
    _attribute_name: str
    _make_new_value: Callable
    _original_value: Any = None

    def __init__(
        self, get_base_symbol: Callable, attribute_name: str, make_new_value: Callable
    ) -> None:
        self._get_base_symbol = get_base_symbol
        self._attribute_name = attribute_name
        self._make_new_value = make_new_value

    def _get_symbol_target(self) -> _SymbolTarget | None:
        try:
            base_symbol = self._get_base_symbol()
        except Exception:
            return None
        if base_symbol is None:
            return None
        parts = self._attribute_name.split(".")
        for part in parts[:-1]:
            try:
                base_symbol = getattr(base_symbol, part)
            except AttributeError:
                return None
        attr = parts[-1]
        return _SymbolTarget(base_symbol, attr)

    def attempt_patch(self) -> bool:
        if self._original_value:
            return True
        target = self._get_symbol_target()
        if target is None:
            return False
        original_value = getattr(target.base_symbol, target.attr)
        try:
            new_val = self._make_new_value(original_value)
        except Exception:
            logger.exception(f"Failed to patch {self._attribute_name}")
            return False
        setattr(
            target.base_symbol,
            target.attr,
            new_val,
        )
        self._original_value = original_value
        return True

    def undo_patch(self) -> bool:
        if not self._original_value:
            return False
        target = self._get_symbol_target()
        if target is None:
            return False

        setattr(target.base_symbol, target.attr, self._original_value)
        self._original_value = None
        return True
