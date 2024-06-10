import importlib

import weave

from weave.trace.patcher import SymbolPatcher, MultiPatcher


patched_methods = [
    SymbolPatcher(
        get_base_symbol=lambda: importlib.import_module("crewai"),
        attribute_name="Crew.kickoff",
        make_new_value=weave.op(),
    ),
    SymbolPatcher(
        get_base_symbol=lambda: importlib.import_module("crewai"),
        attribute_name="Agent.execute_task",
        make_new_value=weave.op(),
    ),
    SymbolPatcher(
        get_base_symbol=lambda: importlib.import_module("crewai"),
        attribute_name="Task.execute",
        make_new_value=weave.op(),
    ),
]

crewai_patcher = MultiPatcher(patched_methods)
