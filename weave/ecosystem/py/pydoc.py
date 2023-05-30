"""Pydoc browsing.

Improvements we could make:
- Give methods chainable names (by using @weave_class and methods for auto-naming)
- Fix inability to use .name() ops
- Add more stuff
- Access attributes with getattr instead of declaring named methods.
"""

import weave
import types
import inspect


class PyModule(weave.types.Type):
    instance_classes = types.ModuleType

    def instance_to_dict(self, obj):
        return {"module_name": obj.__name__}

    def instance_from_dict(self, d):
        return __import__(d["module_name"])


class PyClass(weave.types.Type):
    # TODO: Will registering this break stuff? Everything is type.
    instance_classes = type

    def instance_to_dict(self, obj):
        return {"module_name": obj.__module__.__name__, "class_name": obj.__name__}

    def instance_from_dict(self, d):
        return getattr(__import__(d["module_name"]), d["class_name"])


class PyFunction(weave.types.Type):
    # TODO: Will registering this break stuff? Everything is type.
    instance_classes = types.FunctionType

    def instance_to_dict(self, obj):
        return {"module_name": obj.__module__.__name__, "function_name": obj.__name__}

    def instance_from_dict(self, d):
        return getattr(__import__(d["module_name"]), d["function_name"])


@weave.op()
def module_name(module: types.ModuleType) -> str:
    return module.__name__


@weave.op()
def module_doc(module: types.ModuleType) -> weave.ops.Markdown:
    return weave.ops.Markdown(module.__doc__ or "")


@weave.op()
def module_classes(module: types.ModuleType) -> list[type]:
    return [m[1] for m in inspect.getmembers(module, predicate=inspect.isclass)]


@weave.op()
def module_class(module: types.ModuleType, class_name: str) -> type:
    # TODO: type check? or have __getattr__ work instead and provide
    # refinement
    return getattr(module, class_name)


@weave.op()
def module_functions(module: types.ModuleType) -> list[types.FunctionType]:
    def is_func(m):
        return inspect.isfunction(m) or inspect.isbuiltin(m)

    return [m[1] for m in inspect.getmembers(module, predicate=is_func)]


@weave.op()
def module_function(module: types.ModuleType, function_name: str) -> types.FunctionType:
    # TODO: type check? or have __getattr__ work instead and provide
    # refinement
    return getattr(module, function_name)


@weave.op(render_info={"type": "function"})
def pyclass(module_name: str, class_name: str) -> type:
    return getattr(__import__(module_name), class_name)


@weave.op()
def pyclass_module(pyclass: type) -> types.ModuleType:
    return __import__(pyclass.__module__)


@weave.op()
def pyclass_doc(pyclass: type) -> weave.ops.Markdown:
    return weave.ops.Markdown(pyclass.__doc__ or "")


@weave.op()
def class_name(pyclass: type) -> str:
    return pyclass.__name__


@weave.op()
def class_methods(pyclass: type) -> list[types.FunctionType]:
    def is_func(m):
        return inspect.ismethod(m) or inspect.isfunction(m)

    return [m[1] for m in inspect.getmembers(pyclass, predicate=is_func)]


@weave.op()
def class_method(pyclass: type, method_name: str) -> types.FunctionType:
    return getattr(pyclass, method_name)


@weave.op()
def pyfunction(module_name: str, function_name: str) -> types.FunctionType:
    return getattr(__import__(module_name), function_name)


@weave.op()
def function_name(pyfunction: types.FunctionType) -> str:
    return pyfunction.__name__


@weave.op()
def function_doc(pyfunction: types.FunctionType) -> weave.ops.Markdown:
    return weave.ops.Markdown(pyfunction.__doc__ or "")


@weave.type()
class ModulePanel(weave.Panel):
    id = "ModulePanel"
    input_node: weave.Node[types.ModuleType]

    @weave.op()
    def render(self) -> weave.panels.Card:
        module = self.input_node
        return weave.panels.Card(
            title=module.module_name(),  # type: ignore
            subtitle="python module",
            content=[
                weave.panels.CardTab(
                    name="Description",
                    content=weave.panels.PanelMarkdown(module.module_doc()),  # type: ignore
                ),
                weave.panels.CardTab(
                    name="Classes",
                    content=weave.panels.Table(
                        module.module_classes(),  # type: ignore
                        columns=[
                            lambda c: weave.panels.WeaveLink(
                                c.class_name(),
                                to=lambda inp: module.module_class(inp),  # type: ignore
                            )
                        ],
                    ),
                ),
                weave.panels.CardTab(
                    name="Functions",
                    content=weave.panels.Table(
                        module.module_functions(),  # type: ignore
                        columns=[
                            lambda c: weave.panels.WeaveLink(
                                c.function_name(),
                                to=lambda inp: module.module_function(inp),  # type: ignore
                            )
                        ],
                    ),
                ),
            ],
        )


@weave.type()
class ClassPanel(weave.Panel):
    id = "ClassPanel"
    input_node: weave.Node[type]

    @weave.op()
    def render(self) -> weave.panels.Card:
        cls = self.input_node
        return weave.panels.Card(
            title=cls.class_name(),  # type: ignore
            subtitle="python class",
            content=[
                weave.panels.CardTab(
                    name="Description",
                    content=weave.panels.PanelMarkdown(cls.pyclass_doc()),  # type: ignore
                ),
                weave.panels.CardTab(
                    name="Methods",
                    content=weave.panels.Table(
                        cls.class_methods(),  # type: ignore
                        columns=[
                            lambda m: weave.panels.WeaveLink(
                                m.function_name(),
                                to=lambda inp: cls.class_method(inp),  # type: ignore
                            )
                        ],
                    ),
                ),
            ],
        )


@weave.type()
class FunctionPanel(weave.Panel):
    id = "FunctionPanel"
    input_node: weave.Node[types.FunctionType]

    @weave.op()
    def render(self) -> weave.panels.Card:
        func = self.input_node
        return weave.panels.Card(
            title=func.function_name(),  # type: ignore
            subtitle="python function",
            content=[
                weave.panels.CardTab(
                    name="Description",
                    content=weave.panels.PanelMarkdown(func.function_doc()),  # type: ignore
                ),
            ],
        )
