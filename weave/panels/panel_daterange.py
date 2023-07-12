import dataclasses
import typing

import weave
from .. import panel
from .. import weave_internal
from .. import graph


@weave.type()
class DateRangeConfig:
    domain: weave.Node[list[str]] = dataclasses.field(
        default_factory=lambda: graph.VoidNode()
    )


@weave.type()
class DateRange(panel.Panel):
    id = "DateRange"
    config: typing.Optional[DateRangeConfig] = dataclasses.field(
        default_factory=DateRangeConfig
    )

    def __init__(
        self, input_node=graph.VoidNode(), vars=None, config=None, **options
    ) -> None:
        super().__init__(input_node=input_node, vars=vars)
        self.config = config
        if self.config is None:
            self.config = DateRangeConfig()
        if "domain" in options:
            self.config.domain = options["domain"]

    @weave.op()
    def value(self) -> float:
        return weave.use(self.input_node)
